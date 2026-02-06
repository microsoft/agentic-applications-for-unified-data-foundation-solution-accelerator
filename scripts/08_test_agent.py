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
from azure.ai.projects import AIProjectClient
import pyodbc
import requests

# ============================================================================
# Configuration
# ============================================================================

ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")

# SQL Configuration
FABRIC_WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID")
SQL_SERVER = os.getenv("SQLDB_SERVER")
SQL_DATABASE = os.getenv("SQLDB_DATABASE")

if not ENDPOINT:
    print("ERROR: AZURE_AI_PROJECT_ENDPOINT not set")
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

# Get agent name
AGENT_NAME = args.agent_name or agent_ids.get("agent_name")
if not AGENT_NAME:
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
print(f"Agent: {AGENT_NAME}")
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

project_client = AIProjectClient(
    endpoint=ENDPOINT,
    credential=credential
)

# Get OpenAI client from project
openai_client = project_client.get_openai_client()

print("-" * 60)

# ============================================================================
# Sample Questions - Load from config or use defaults
# ============================================================================

def load_sample_questions_from_file(config_dir):
    """Load sample questions from config folder if available"""
    questions_path = os.path.join(config_dir, "sample_questions.txt")
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
            elif line.startswith('- '):
                question = line[2:].strip()
                if current_section == 'sql':
                    sql_questions.append(question)
                elif current_section == 'doc':
                    doc_questions.append(question)
                elif current_section == 'combined':
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

def chat(user_message: str):
    """Send a message to the agent and handle function calls."""
    
    try:
        # Initial request to the agent
        response = openai_client.responses.create(
            input=user_message,
            extra_body={"agent": {"name": AGENT_NAME, "type": "agent_reference"}}
        )
        
        # Process response - handle function calls if any
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Check for function calls and tool uses in output
            function_calls = []
            text_output = ""
            search_results = []
            
            for item in response.output:
                item_type = getattr(item, 'type', None)
                
                if item_type == 'function_call':
                    function_calls.append(item)
                elif item_type == 'message':
                    for content in item.content:
                        if hasattr(content, 'text'):
                            text_output += content.text
                        # Check for annotations (citations from search)
                        if hasattr(content, 'annotations'):
                            for ann in content.annotations:
                                if hasattr(ann, 'url_citation'):
                                    search_results.append(ann.url_citation)
                                elif hasattr(ann, 'file_citation'):
                                    search_results.append(getattr(ann.file_citation, 'file_id', str(ann.file_citation)))
                # Handle search tool call (request)
                elif item_type == 'azure_ai_search_call':
                    if VERBOSE:
                        # Extract the search query from arguments
                        args_str = getattr(item, 'arguments', '{}')
                        try:
                            args = json.loads(args_str) if args_str else {}
                            query = args.get('query', 'unknown')
                        except:
                            query = args_str
                        print(f"\n🔍 AI Search: \"{query}\"")
                # Handle search tool output (result) - results are internal to the agent
                elif item_type == 'azure_ai_search_call_output':
                    if VERBOSE:
                        # Native AI Search doesn't expose raw results in API response
                        # The agent uses results internally and includes citations in the answer
                        print(f"   ✓ Search completed (results used internally by agent)")
                # Handle other tool result types
                elif item_type in ['tool_call']:
                    if VERBOSE:
                        print(f"\n🔧 Tool called: {getattr(item, 'name', 'unknown')}")
                        
                # Catch-all for other tool results
                elif item_type and 'search' in str(item_type).lower():
                    print(f"\n🔍 Search result (type: {item_type})")
                    print(f"   {str(item)[:500]}")
            
            # Print search citations if any (verbose only)
            if search_results and VERBOSE:
                print(f"\n📚 Search Citations:")
                for citation in search_results[:5]:  # Show up to 5 citations
                    print(f"   - {citation}")
            
            # If no function calls, we're done
            if not function_calls:
                if text_output:
                    print(f"\nAssistant: {text_output}")
                return text_output
            
            # Handle function calls
            tool_outputs = []
            for fc in function_calls:
                func_name = fc.name
                func_args = json.loads(fc.arguments)
                
                if VERBOSE:
                    print(f"\n🔧 Calling {func_name}...")
                
                if func_name == "execute_sql":
                    sql_query = func_args.get("sql_query", "")
                    if VERBOSE:
                        print(f"\n   📝 SQL Query:")
                        print(f"   {'-'*50}")
                        print(f"   {sql_query}")
                        print(f"   {'-'*50}")
                    result = execute_sql(sql_query)
                    if VERBOSE:
                        print(f"\n   📊 SQL Result:")
                        print(f"   {'-'*50}")
                        for line in result.split('\n'):
                            print(f"   {line}")
                        print(f"   {'-'*50}")
                else:
                    result = f"Unknown function: {func_name}"
                
                tool_outputs.append({
                    "type": "function_call_output",
                    "call_id": fc.call_id,
                    "output": result
                })
            
            # Submit tool outputs and get next response
            response = openai_client.responses.create(
                input=tool_outputs,
                extra_body={
                    "agent": {"name": AGENT_NAME, "type": "agent_reference"},
                    "previous_response_id": response.id
                }
            )
        
        print("\nWarning: Max iterations reached")
        return None
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return None


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
        
        chat(user_input)
        
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        break
    except EOFError:
        print("\nGoodbye!")
        break
