"""
07_test_agent.py - Test AI Foundry Agent with SQL + Native AI Search
Unified test script that automatically detects SQL backend from agent config.

Modes:
    - Fabric Data Agent mode: All SQL handled by MCP tool (no local SQL needed)
    - Fabric mode: Executes SQL against Fabric Lakehouse
    - Azure SQL mode: Executes SQL against Azure SQL Database
    - Both modes: Native AI Search handles document queries automatically

Usage:
    python 07_test_agent.py           # Clean output (default)
    python 07_test_agent.py -v         # Verbose: show SQL queries, search details
    python 07_test_agent.py --agent-name <name>

The script reads sql_mode from agent_ids.json to determine which SQL backend to use.
"""

import os
import sys
import json
import re
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
from agent_framework.foundry import FoundryAgent
import requests

# ============================================================================
# Configuration
# ============================================================================

ENDPOINT = os.getenv("AZURE_AI_AGENT_ENDPOINT")

# SQL Configuration
FABRIC_WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID")
# Support both new and legacy environment variable names for backward compatibility
SQL_SERVER = os.getenv("AZURE_SQLDB_SERVER") or os.getenv("SQLDB_SERVER")
SQL_DATABASE = os.getenv("AZURE_SQLDB_DATABASE") or os.getenv("SQLDB_DATABASE")

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
    print("       Run 06_create_agent.py first")
    sys.exit(1)

with open(agent_ids_path) as f:
    agent_ids = json.load(f)

# Get chat agent name
CHAT_AGENT_NAME = args.agent_name or agent_ids.get("chat_agent_name")
if not CHAT_AGENT_NAME:
    print("ERROR: No agent name found")
    print("       Run 06_create_agent.py first or provide --agent-name")
    sys.exit(1)

# Determine SQL mode from saved config
SQL_MODE = agent_ids.get("sql_mode", "azure_sql")
USE_FABRIC = SQL_MODE in ("fabric", "fabric_data_agent")
USE_DATA_AGENT = SQL_MODE == "fabric_data_agent"

# For Fabric mode, load additional config
LAKEHOUSE_NAME = None
LAKEHOUSE_ID = None
SQL_ENDPOINT = None

if USE_FABRIC and not USE_DATA_AGENT:
    fabric_ids_path = os.path.join(config_dir, "fabric_ids.json")
    if os.path.exists(fabric_ids_path):
        with open(fabric_ids_path) as f:
            fabric_ids = json.load(f)
        LAKEHOUSE_NAME = fabric_ids.get("lakehouse_name")
        LAKEHOUSE_ID = fabric_ids.get("lakehouse_id")
elif not USE_FABRIC and not USE_DATA_AGENT:
    # Use Azure SQL config from agent_ids or environment
    SQL_SERVER = agent_ids.get("sql_server") or SQL_SERVER
    SQL_DATABASE = agent_ids.get("sql_database") or SQL_DATABASE

# Only require SQL config when not using Data Agent (MCP handles SQL server-side)
if not USE_DATA_AGENT and not USE_FABRIC and (not SQL_SERVER or not SQL_DATABASE):
    print("ERROR: Azure SQL not configured")
    print("       Set AZURE_SQLDB_SERVER (or legacy SQLDB_SERVER) and AZURE_SQLDB_DATABASE (or legacy SQLDB_DATABASE)")
    sys.exit(1)

# Only import pyodbc when needed (not in Data Agent mode)
if not USE_DATA_AGENT:
    import pyodbc

# ============================================================================
# Print Configuration
# ============================================================================

print(f"\n{'='*60}")
if USE_DATA_AGENT:
    print("AI Agent Chat (Fabric Data Agent MCP + Native Search)")
elif USE_FABRIC:
    print("AI Agent Chat (Fabric SQL + Native Search)")
else:
    print("AI Agent Chat (Azure SQL + Native Search)")
print(f"{'='*60}")
print(f"Chat Agent: {CHAT_AGENT_NAME}")
if USE_DATA_AGENT:
    print(f"SQL Mode: Fabric Data Agent (MCP)")
    print(f"Data Agent: {agent_ids.get('data_agent_name', 'N/A')}")
    print(f"MCP Endpoint: {agent_ids.get('data_agent_mcp_endpoint', 'N/A')}")
elif USE_FABRIC:
    print("SQL Mode: Fabric Lakehouse")
    print(f"Lakehouse: {LAKEHOUSE_NAME}")
else:
    print("SQL Mode: Azure SQL Database")
    print(f"SQL Server: {SQL_SERVER}")
    print(f"SQL Database: {SQL_DATABASE}")
print("Type 'quit' to exit, 'help' for sample questions\n")

# ============================================================================
# SQL Connection Functions (not used in Data Agent mode)
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
        elif VERBOSE:
            print(f"[Fabric] API error response: {resp.text}")
    except Exception as e:
        print(f"Warning: Could not get Fabric SQL endpoint: {e}")
        traceback.print_exc()
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
        return pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
    except Exception as e:
        if VERBOSE:
            print(f"[Azure SQL] {driver18} failed: {e}")
            print(f"[Azure SQL] Falling back to {driver17}...")
        try:
            connection_string = f"DRIVER={{{driver17}}};SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
            conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
            if VERBOSE:
                print(f"[Azure SQL] Connected successfully using {driver17}")
            return conn
        except Exception as e2:
            print(f"[Azure SQL] {driver17} also failed: {e2}")
            traceback.print_exc()
            raise


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
    try:
        conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
        return conn
    except Exception as e:
        if VERBOSE:
            print(f"[Fabric SQL] Connection failed: {e}")
            traceback.print_exc()
        raise


def execute_sql(sql_query: str) -> str:
    """Execute SQL query and return results."""
    if VERBOSE:
        print(f"\n[SQL] Executing query:\n{sql_query}")
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
        result = "\n".join(result_lines)
        if VERBOSE:
            print(f"\n[SQL] Results:\n{result}")
        return result
        
    except Exception as e:
        traceback.print_exc()
        return f"SQL Error: {str(e)}"


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
    if USE_DATA_AGENT:
        print("\n  SQL questions use Fabric Data Agent (MCP) tool")
    else:
        print("\n  SQL questions use execute_sql tool")
    print("  Search questions use AI Search automatically")
    print("  Combined questions use both tools")
    print()

# ============================================================================
# Chat Loop
# ============================================================================

# Compiled regex for MCP citation markers: 【N:M†source】
_MARKER_RE = re.compile(r'【\d+:(\d+)†([^】]*)】')


def _parse_mcp_docs(mcp_text: str, mcp_docs: dict):
    """Parse JSON document blocks from MCP output text keyed by section index."""
    sections = re.split(r'【\d+:(\d+)†[^】]*】', mcp_text)
    for i in range(1, len(sections) - 1, 2):
        sec_idx = sections[i]
        sec_content = sections[i + 1]
        json_match = re.search(r'\{[^{}]*"id"\s*:\s*"[^"]*"[^{}]*\}', sec_content)
        if json_match:
            try:
                doc = json.loads(json_match.group())
                if "id" in doc:
                    mcp_docs[sec_idx] = doc
            except (json.JSONDecodeError, ValueError):
                pass  # Skip malformed JSON fragments; parsing continues


def _extract_mcp_from_raw(raw_repr, mcp_docs: dict):
    """Extract MCP docs from any raw_representation type."""
    raw_output = getattr(raw_repr, "output", None)
    if raw_output and isinstance(raw_output, str):
        _parse_mcp_docs(raw_output, mcp_docs)
        return
    response = getattr(raw_repr, "response", None)
    if response:
        for item in getattr(response, "output", None) or []:
            item_output = getattr(item, "output", None)
            if item_output and isinstance(item_output, str):
                _parse_mcp_docs(item_output, mcp_docs)


async def chat(user_message: str, agent, conversation_id: str = None):
    """Send a message to the agent and stream the response."""
    try:
        text_output = ""
        mcp_docs = {}

        run_kwargs = {"stream": True}
        if conversation_id:
            run_kwargs["options"] = {"conversation_id": conversation_id}

        async for chunk in agent.run(user_message, **run_kwargs):
            for content in getattr(chunk, "contents", []) or []:
                raw_repr = getattr(content, "raw_representation", None)
                if raw_repr:
                    _extract_mcp_from_raw(raw_repr, mcp_docs)

            chunk_text = str(chunk.text) if chunk.text else ""
            if chunk_text:
                text_output += chunk_text

        if text_output:
            # Collect non-summary markers, then replace in text
            original_markers = [
                m for m in _MARKER_RE.finditer(text_output)
                if m.group(1) != "0"
            ]

            # Always strip section-0 and renumber rest sequentially
            citation_idx = 0
            def _replace_marker(m):
                nonlocal citation_idx
                if m.group(1) == "0":
                    return ""
                citation_idx += 1
                return f"[{citation_idx}]"
            text_output = _MARKER_RE.sub(_replace_marker, text_output)

            print(f"\nAssistant: {text_output}")

            # Display citations — sequential [1],[2],[3] matching markers in text
            if original_markers:
                print("\n  Citations:")
                for i, m in enumerate(original_markers, 1):
                    sec_idx = m.group(1)
                    marker_source = m.group(2)
                    mcp_doc = mcp_docs.get(sec_idx, {})
                    doc_source = mcp_doc.get("source") or marker_source or f"source_{sec_idx}"
                    doc_id = mcp_doc.get("id", "")

                    if doc_id:
                        print(f"    [{i}] {doc_source} ({doc_id})")
                    else:
                        print(f"    [{i}] {doc_source}")

        return text_output
        
    except Exception as e:
        print(f"\nError: {e}")
        traceback.print_exc()
        return None


async def main():
    # Build tools list - only pass execute_sql when not using Data Agent
    tools = [execute_sql] if not USE_DATA_AGENT else None

    agent = FoundryAgent(
        project_endpoint=ENDPOINT,
        agent_name=CHAT_AGENT_NAME,
        credential=DefaultAzureCredential(),
        tools=tools,
    )

    print("-" * 60)

    project_client = AIProjectClient(
        endpoint=ENDPOINT,
        credential=AsyncDefaultAzureCredential(),
    )
    openai_client = project_client.get_openai_client()
    conv = await openai_client.conversations.create()
    conversation_id = conv.id

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
            
            await chat(user_input, agent, conversation_id)
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except EOFError:
            print("\nGoodbye!")
            break

    # Cleanup: delete the conversation
    try:
        await openai_client.conversations.delete(conversation_id=conversation_id)
        print(f"Conversation {conversation_id} deleted.")
    except Exception as e:
        print(f"Warning: Could not delete conversation: {e}")

    # Close async client to avoid unclosed session warnings
    await project_client.close()

asyncio.run(main())
