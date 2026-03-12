"""
08_test_agent.py - Test AI Foundry Agent with SQL + Native AI Search
Unified test script that automatically detects SQL backend from agent config.

Modes:
    - Fabric mode: Executes SQL against Fabric Lakehouse
    - Azure SQL mode: Executes SQL against Azure SQL Database
    - Both modes: Native AI Search handles document queries automatically

Usage:
    python 08_test_agent.py           # Clean output (default)
    python 08_test_agent.py -v         # Verbose: show SQL queries, search details
    python 08_test_agent.py --agent-name <name>

The script reads sql_mode from agent_ids.json to determine which SQL backend to use.
"""

import os
import sys
import json
import struct
import argparse
import asyncio
import logging
import traceback

# Parse arguments first
parser = argparse.ArgumentParser()
parser.add_argument("--agent-name", type=str, help="Agent name to test")
parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed SQL queries, search calls, and results")
args = parser.parse_args()

VERBOSE = args.verbose

# Load environment from azd + project .env
from load_env import load_all_env, get_data_folder
load_all_env()

from azure.identity import DefaultAzureCredential
from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
from azure.ai.projects.aio import AIProjectClient
from agent_framework.azure import AzureAIProjectAgentProvider
import pyodbc
import requests

# Suppress informational warnings from agent_framework about runtime
# tool/structured_output overrides not being supported by AzureAIClient.
agent_log_level = os.getenv("AGENT_FRAMEWORK_LOG_LEVEL", "ERROR").upper()
logging.getLogger("agent_framework.azure").setLevel(getattr(logging, agent_log_level, logging.ERROR))

# ============================================================================
# Configuration
# ============================================================================

ENDPOINT = os.getenv("AZURE_AI_AGENT_ENDPOINT")

# SQL Configuration
FABRIC_WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID")
SQL_SERVER = os.getenv("SQLDB_SERVER")
SQL_DATABASE = os.getenv("SQLDB_DATABASE")

if not ENDPOINT:
    print("ERROR: AZURE_AI_AGENT_ENDPOINT not set")
    sys.exit(1)

# Get data folder with proper path resolution
try:
    data_dir = get_data_folder()
except ValueError:
    print("ERROR: DATA_FOLDER not set in .env")
    sys.exit(1)

config_dir = os.path.join(data_dir, "config")
if not os.path.exists(config_dir):
    config_dir = data_dir

# Load agent config
agent_ids_path = os.path.join(config_dir, "agent_ids.json")
if not os.path.exists(agent_ids_path):
    print("ERROR: agent_ids.json not found")
    print("       Run 07_create_agent.py first")
    sys.exit(1)

with open(agent_ids_path) as f:
    agent_ids = json.load(f)

# Get chat agent name
CHAT_AGENT_NAME = args.agent_name or agent_ids.get("chat_agent_name")
if not CHAT_AGENT_NAME:
    print("ERROR: No agent name found")
    print("       Run 07_create_agent.py first or provide --agent-name")
    sys.exit(1)

# Determine SQL mode from saved config
SQL_MODE = agent_ids.get("sql_mode", "azure_sql")
USE_FABRIC = SQL_MODE == "fabric"

# For Fabric mode, load additional config
LAKEHOUSE_NAME = None
LAKEHOUSE_ID = None
SQL_ENDPOINT = None

if USE_FABRIC:
    fabric_ids_path = os.path.join(config_dir, "fabric_ids.json")
    if os.path.exists(fabric_ids_path):
        with open(fabric_ids_path) as f:
            fabric_ids = json.load(f)
        LAKEHOUSE_NAME = fabric_ids.get("lakehouse_name")
        LAKEHOUSE_ID = fabric_ids.get("lakehouse_id")
else:
    # Use Azure SQL config from agent_ids or environment
    SQL_SERVER = agent_ids.get("sql_server") or SQL_SERVER
    SQL_DATABASE = agent_ids.get("sql_database") or SQL_DATABASE

if not USE_FABRIC and (not SQL_SERVER or not SQL_DATABASE):
    print("ERROR: Azure SQL not configured")
    print("       Set SQLDB_SERVER and SQLDB_DATABASE")
    sys.exit(1)

# ============================================================================
# Print Configuration
# ============================================================================

print(f"\n{'='*60}")
if USE_FABRIC:
    print("AI Agent Chat (Fabric SQL + Native Search)")
else:
    print("AI Agent Chat (Azure SQL + Native Search)")
print(f"{'='*60}")
print(f"Chat Agent: {CHAT_AGENT_NAME}")
if USE_FABRIC:
    print(f"SQL Mode: Fabric Lakehouse")
    print(f"Lakehouse: {LAKEHOUSE_NAME}")
else:
    print(f"SQL Mode: Azure SQL Database")
    print(f"SQL Server: {SQL_SERVER}")
    print(f"SQL Database: {SQL_DATABASE}")
print("Type 'quit' to exit, 'help' for sample questions\n")

# ============================================================================
# SQL Connection Functions
# ============================================================================

credential = DefaultAzureCredential()

def get_fabric_sql_endpoint():
    """Get the SQL analytics endpoint for the Fabric Lakehouse"""
    if not FABRIC_WORKSPACE_ID or not LAKEHOUSE_ID:
        return None
    
    try:
        token = credential.get_token("https://api.fabric.microsoft.com/.default")
        headers = {"Authorization": f"Bearer {token.token}"}
        url = f"https://api.fabric.microsoft.com/v1/workspaces/{FABRIC_WORKSPACE_ID}/lakehouses/{LAKEHOUSE_ID}"
        
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            props = data.get("properties", {})
            sql_props = props.get("sqlEndpointProperties", {})
            return sql_props.get("connectionString")
    except Exception as e:
        print(f"Warning: Could not get Fabric SQL endpoint: {e}")
    return None


def get_azure_sql_connection():
    """Get a connection to Azure SQL Server using DefaultAzureCredential."""
    driver18 = "ODBC Driver 18 for SQL Server"
    driver17 = "ODBC Driver 17 for SQL Server"
    
    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-LE")
    token_struct = struct.pack(
        f"<I{len(token_bytes)}s",
        len(token_bytes),
        token_bytes
    )
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    
    try:
        connection_string = f"DRIVER={{{driver18}}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
        conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
        return conn
    except Exception:
        connection_string = f"DRIVER={{{driver17}}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
        conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
        return conn


def get_fabric_sql_connection():
    """Get a connection to Fabric Lakehouse SQL endpoint."""
    global SQL_ENDPOINT
    if not SQL_ENDPOINT:
        SQL_ENDPOINT = get_fabric_sql_endpoint()
    
    if not SQL_ENDPOINT:
        raise Exception("Could not get Fabric SQL endpoint")
    
    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-LE")
    token_struct = struct.pack(
        f"<I{len(token_bytes)}s",
        len(token_bytes),
        token_bytes
    )
    SQL_COPT_SS_ACCESS_TOKEN = 1256
    
    connection_string = f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={SQL_ENDPOINT};DATABASE={LAKEHOUSE_NAME};Encrypt=yes;TrustServerCertificate=no"
    conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
    return conn


def execute_sql(sql_query: str) -> str:
    """Execute SQL query and return results."""
    try:
        if USE_FABRIC:
            conn = get_fabric_sql_connection()
        else:
            conn = get_azure_sql_connection()
        
        cursor = conn.cursor()
        cursor.execute(sql_query)
        
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        
        # Format results as markdown table
        result_lines = []
        result_lines.append("| " + " | ".join(columns) + " |")
        result_lines.append("|" + "|".join(["---"] * len(columns)) + "|")
        
        for row in rows[:50]:  # Limit to 50 rows
            values = [str(v) if v is not None else "NULL" for v in row]
            result_lines.append("| " + " | ".join(values) + " |")
        
        if len(rows) > 50:
            result_lines.append(f"\n... and {len(rows) - 50} more rows")
        
        result_lines.append(f"\n({len(rows)} rows returned)")
        
        conn.close()
        return "\n".join(result_lines)
        
    except Exception as e:
        return f"SQL Error: {str(e)}"


# ============================================================================
# Initialize Client
# ============================================================================


# ============================================================================
# Sample Questions - Load from config or use defaults
# ============================================================================

def load_sample_questions_from_file(config_dir):
    """Load sample questions from config folder if available"""
    questions_path = os.path.join(config_dir, "sample_questions.txt")
    print(questions_path)
    if os.path.exists(questions_path):
        with open(questions_path) as f:
            content = f.read()
        
        # Parse the structured questions file
        sql_questions = []
        doc_questions = []
        combined_questions = []
        
        current_section = None
        for line in content.split('\n'):
            line = line.strip()
            if 'SQL QUESTIONS' in line:
                current_section = 'sql'
            elif 'DOCUMENT QUESTIONS' in line:
                current_section = 'doc'
            elif 'COMBINED' in line:
                current_section = 'combined'
            else:
                # Match "- question" or "1. question" / "2. question" etc.
                question = None
                if line.startswith('- '):
                    question = line[2:].strip()
                elif len(line) > 2 and line[0].isdigit() and '. ' in line:
                    question = line.split('. ', 1)[1].strip()
                if question and current_section == 'sql':
                    sql_questions.append(question)
                elif question and current_section == 'doc':
                    doc_questions.append(question)
                elif question and current_section == 'combined':
                    combined_questions.append(question)
        
        # Return a mix of questions: 2 SQL, 1 doc, 1 combined
        result = []
        if sql_questions:
            result.extend(sql_questions[:2])
        if doc_questions:
            result.append(doc_questions[0])
        if combined_questions:
            result.append(combined_questions[0])
        return result
    return None

# Try to load from file, fallback to defaults
sample_questions = load_sample_questions_from_file(config_dir)
if not sample_questions:
    sample_questions = [
        "How many records are in the database?",
        "What is the total count by category?",
        "What are the policies for this scenario?",
        "Which records exceed the thresholds defined in our policy?",
    ]

def show_help():
    print("\nSample questions to try:")
    for i, q in enumerate(sample_questions, 1):
        print(f"  {i}. {q}")
    print("\n  SQL questions use execute_sql tool")
    print("  Search questions use AI Search automatically")
    print("  Combined questions use both tools")
    print()

# ============================================================================
# Chat Loop
# ============================================================================

async def chat(user_message: str, conversation_id: str, agent):
    """Send a message to the agent and handle function calls.
    
    Args:
        user_message: The user's input message
        conversation_id: The conversation ID to maintain context across turns
        agent: The agent instance from AzureAIProjectAgentProvider
    """
    
    try:
        text_output = ""
        citations: list[dict] = []

        async for chunk in agent.run(user_message, stream=True, conversation_id=conversation_id):
            # Collect citations from Azure AI Search responses
            for content in getattr(chunk, "contents", []):
                annotations = getattr(content, "annotations", [])
                if annotations:
                    citations.extend(annotations)

            chunk_text = str(chunk.text) if chunk.text else ""
            if chunk_text:
                text_output += chunk_text

        if text_output:
            print(f"\nAssistant: {text_output}")

        # # Print search citations
        # if citations:
        #     print("\n📚 Search Citations:")
        #     seen_doc_ids = set()
        #     print("   (Showing unique documents cited in this response)")
        #     print("   " + "-"*40)
        #     for citation in citations:
        #         # URL is directly on the citation object, fallback to additional_properties.get_url
        #         url = citation.get("url") or (citation.get("additional_properties") or {}).get("get_url", "N/A")
        #         title = citation.get("title", "N/A")
        #         if title not in seen_doc_ids:
        #             seen_doc_ids.add(title)
        #             print(f"   - {title}: {url}")

        return text_output
        
    except Exception as e:
        print(f"\nError: {e}")
        traceback.print_exc()
        return None


async def main():
    async with (
        AsyncDefaultAzureCredential() as async_credential,
        AIProjectClient(endpoint=ENDPOINT, credential=async_credential) as project_client,
    ):
        # Create provider for agent management
        provider = AzureAIProjectAgentProvider(project_client=project_client)

        # Get agent with tools using provider
        agent = await provider.get_agent(
            name=CHAT_AGENT_NAME,
            tools=execute_sql
        )

        # Create conversation for context continuity
        openai_client = project_client.get_openai_client()
        conversation = await openai_client.conversations.create()

        print("-" * 60)

        # Main chat loop
        while True:
            try:
                user_input = input("\nYou: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                
                if user_input.lower() == 'help':
                    show_help()
                    continue
                
                # Check for numbered question shortcuts
                if user_input.isdigit():
                    idx = int(user_input) - 1
                    if 0 <= idx < len(sample_questions):
                        user_input = sample_questions[idx]
                        print(f"  → {user_input}")
                
                # Pass the persistent conversation ID to maintain context
                await chat(user_input, conversation.id, agent)
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except EOFError:
                print("\nGoodbye!")
                break

        # Cleanup conversation when done
        try:
            await openai_client.conversations.delete(conversation_id=conversation.id)
            print("\nConversation cleaned up.")
        except Exception:
            pass  # Ignore cleanup errors

asyncio.run(main())
