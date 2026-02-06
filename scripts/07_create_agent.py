"""
07_create_agent.py - Create AI Foundry Agent with SQL + Native AI Search
Unified script that automatically selects the SQL backend based on configuration.

Modes:
    - Fabric mode: Uses Fabric Lakehouse SQL endpoint (requires FABRIC_WORKSPACE_ID)
    - Azure SQL mode: Uses Azure SQL Database (--azure-only or no Fabric configured)
    - Both modes always use Native AzureAISearchTool for document search

Usage:
    python 07_create_agent.py              # Auto-detect (Fabric if configured, else Azure SQL)
    python 07_create_agent.py --azure-only # Force Azure SQL mode

Prerequisites:
    - Run 01_generate_sample_data.py (creates data and ontology_config.json)
    - Run 06_upload_to_search.py (uploads PDFs to AI Search)
    - For Fabric mode: Run 02/03 scripts to set up Fabric Lakehouse
    - For Azure SQL mode: Run 06a_upload_to_sql.py

Environment Variables (from azd):
    - AZURE_AI_PROJECT_ENDPOINT: Azure AI Project endpoint
    - AZURE_CHAT_MODEL: Model deployment name
    - AZURE_AI_SEARCH_CONNECTION_NAME: AI Search connection name
    - AZURE_AI_SEARCH_INDEX: AI Search index name
    - SQLDB_SERVER, SQLDB_DATABASE: Azure SQL (for azure-only mode)
    - FABRIC_WORKSPACE_ID: Fabric workspace (for Fabric mode)
"""

import os
import sys
import json
import argparse

# Parse arguments first
parser = argparse.ArgumentParser()
parser.add_argument("--azure-only", action="store_true",
                    help="Use Azure SQL Database instead of Fabric Lakehouse")
parser.add_argument("--connection-name", type=str,
                    help="Azure AI Search connection name (overrides env)")
parser.add_argument("--index-name", type=str,
                    help="Azure AI Search index name (overrides env)")
args = parser.parse_args()

# Get script directory for relative paths
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load environment from azd + project .env
from load_env import load_all_env, get_data_folder
load_all_env()

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    FunctionTool,
    AzureAISearchAgentTool,
    AzureAISearchToolResource,
    AISearchIndexResource,
)

# ============================================================================
# Configuration
# ============================================================================

# Azure services - from azd environment
ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
MODEL = os.getenv("AZURE_CHAT_MODEL") or os.getenv("AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")
SEARCH_CONNECTION_NAME = args.connection_name or os.getenv("AZURE_AI_SEARCH_CONNECTION_NAME")

# SQL Configuration - determine mode
FABRIC_WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID")
SQL_SERVER = os.getenv("SQLDB_SERVER")
SQL_DATABASE = os.getenv("SQLDB_DATABASE")

# Determine SQL mode
if args.azure_only:
    USE_FABRIC = False
elif FABRIC_WORKSPACE_ID:
    USE_FABRIC = True
else:
    USE_FABRIC = False

# Project settings - from .env
SOLUTION_NAME = os.getenv("SOLUTION_NAME") or os.getenv("AZURE_ENV_NAME", "demo")

# Validation
if not ENDPOINT:
    print("ERROR: AZURE_AI_PROJECT_ENDPOINT not set")
    print("       Run 'azd up' to deploy Azure resources")
    sys.exit(1)

# Get data folder with proper path resolution
try:
    DATA_FOLDER = get_data_folder()
except ValueError:
    print("ERROR: DATA_FOLDER not set in .env")
    print("       Run 01_generate_data.py first")
    sys.exit(1)
    sys.exit(1)

if not SEARCH_CONNECTION_NAME:
    print("ERROR: Azure AI Search connection name not set")
    print("       Set AZURE_AI_SEARCH_CONNECTION_NAME in azd env or pass --connection-name")
    sys.exit(1)

if not USE_FABRIC and (not SQL_SERVER or not SQL_DATABASE):
    print("ERROR: Azure SQL not configured and Fabric not available")
    print("       Set SQLDB_SERVER and SQLDB_DATABASE in azd environment")
    print("       Or configure FABRIC_WORKSPACE_ID for Fabric mode")
    sys.exit(1)

data_dir = DATA_FOLDER  # Already absolute from get_data_folder()

# Set up paths for folder structure
config_dir = os.path.join(data_dir, "config")
if not os.path.exists(config_dir):
    config_dir = data_dir

# ============================================================================
# Load Ontology Config
# ============================================================================

config_path = os.path.join(config_dir, "ontology_config.json")
if not os.path.exists(config_path):
    print(f"ERROR: ontology_config.json not found")
    print("       Run 01_generate_sample_data.py first")
    sys.exit(1)

with open(config_path) as f:
    ontology_config = json.load(f)

scenario = ontology_config.get("scenario", "retail")
scenario_name = ontology_config.get("name", "Business Data")
scenario_desc = ontology_config.get("description", "")
tables = list(ontology_config.get("tables", {}).keys())

# Load schema prompt
prompt_path = os.path.join(config_dir, "schema_prompt.txt")
if os.path.exists(prompt_path):
    with open(prompt_path) as f:
        schema_prompt = f.read()
else:
    # Generate basic schema from ontology config
    schema_lines = ["## Database Schema:"]
    for table_name, table_config in ontology_config.get("tables", {}).items():
        columns = table_config.get("columns", [])
        types = table_config.get("types", {})
        col_defs = [f"{col} ({types.get(col, 'String')})" for col in columns]
        schema_lines.append(f"- {table_name}: {', '.join(col_defs)}")
    schema_prompt = "\n".join(schema_lines)

# Load Fabric IDs if in Fabric mode
LAKEHOUSE_NAME = None
LAKEHOUSE_ID = None
if USE_FABRIC:
    fabric_ids_path = os.path.join(config_dir, "fabric_ids.json")
    if os.path.exists(fabric_ids_path):
        with open(fabric_ids_path) as f:
            fabric_ids = json.load(f)
        LAKEHOUSE_NAME = fabric_ids.get("lakehouse_name")
        LAKEHOUSE_ID = fabric_ids.get("lakehouse_id")
    else:
        print("ERROR: fabric_ids.json not found for Fabric mode")
        print("       Run 02_create_fabric_items.py first, or use --azure-only")
        sys.exit(1)

# Load Search Index: CLI arg > environment variable > search_ids.json
if args.index_name:
    INDEX_NAME = args.index_name
elif os.getenv("AZURE_AI_SEARCH_INDEX"):
    INDEX_NAME = os.getenv("AZURE_AI_SEARCH_INDEX")
else:
    search_ids_path = os.path.join(config_dir, "search_ids.json")
    if os.path.exists(search_ids_path):
        with open(search_ids_path) as f:
            search_ids = json.load(f)
        INDEX_NAME = search_ids.get("index_name", f"{SOLUTION_NAME}-documents")
    else:
        INDEX_NAME = f"{SOLUTION_NAME}-documents"

# Agent name
AGENT_NAME = f"{SOLUTION_NAME}-agent"

# ============================================================================
# Print Configuration
# ============================================================================

print(f"\n{'='*60}")
if USE_FABRIC:
    print("Creating AI Foundry Agent (Fabric SQL + Native AI Search)")
else:
    print("Creating AI Foundry Agent (Azure SQL + Native AI Search)")
print(f"{'='*60}")
print(f"Endpoint: {ENDPOINT}")
print(f"Model: {MODEL}")
print(f"Scenario: {scenario_name}")
print(f"Tables: {', '.join(tables)}")
if USE_FABRIC:
    print(f"SQL Mode: Fabric Lakehouse")
    print(f"Workspace: {FABRIC_WORKSPACE_ID}")
    print(f"Lakehouse: {LAKEHOUSE_NAME}")
else:
    print(f"SQL Mode: Azure SQL Database")
    print(f"SQL Server: {SQL_SERVER}")
    print(f"SQL Database: {SQL_DATABASE}")
print(f"Search Connection: {SEARCH_CONNECTION_NAME}")
print(f"Search Index: {INDEX_NAME}")

# ============================================================================
# Build Agent Instructions
# ============================================================================

def load_sample_questions(config_dir):
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
        
        return {
            'sql': sql_questions[:3],  # Take top 3 of each
            'doc': doc_questions[:3],
            'combined': combined_questions[:2]
        }
    return None


def generate_example_questions(tables_config):
    """Generate example questions from table schema when no sample_questions.txt exists"""
    sql_examples = []
    
    for table_name, table_config in tables_config.items():
        columns = table_config.get("columns", [])
        # Find date columns for time-based questions
        date_cols = [c for c in columns if 'date' in c.lower() or 'time' in c.lower()]
        # Find numeric columns for aggregation questions
        numeric_types = ['Int', 'BigInt', 'Float', 'Double', 'Decimal']
        types = table_config.get("types", {})
        numeric_cols = [c for c in columns if types.get(c) in numeric_types]
        
        # Generate questions
        sql_examples.append(f"How many records are in {table_name}?")
        if date_cols:
            sql_examples.append(f"Show {table_name} from the last 30 days")
        if numeric_cols and len(numeric_cols) > 0:
            sql_examples.append(f"What is the average {numeric_cols[0]} in {table_name}?")
    
    return {
        'sql': sql_examples[:3],
        'doc': ["What are the policies for this scenario?", "What procedures should be followed?"],
        'combined': ["Which records exceed the thresholds defined in our policies?"]
    }


def build_agent_instructions(config, schema_text, use_fabric, config_dir):
    """Build agent instructions based on SQL mode and scenario"""
    scenario_name = config.get("name", "Business Data")
    scenario_desc = config.get("description", "")
    tables_config = config.get("tables", {})
    relationships = config.get("relationships", [])
    
    table_names = list(tables_config.keys())
    
    # Load or generate sample questions
    sample_questions = load_sample_questions(config_dir)
    if not sample_questions:
        sample_questions = generate_example_questions(tables_config)
    
    # Format example questions for instructions
    sql_examples = "\n".join([f"  - {q}" for q in sample_questions.get('sql', [])])
    doc_examples = "\n".join([f"  - {q}" for q in sample_questions.get('doc', [])])
    
    # Build relationship descriptions for JOINs
    join_hints = []
    for rel in relationships:
        from_table = rel.get("from")
        to_table = rel.get("to")
        from_key = rel.get("fromKey")
        to_key = rel.get("toKey")
        join_hints.append(f"{from_table}.{from_key} = {to_table}.{to_key}")
    
    if use_fabric:
        sql_source = "Fabric Lakehouse"
        table_format = "Use table names directly (no schema prefix)"
    else:
        sql_source = "Azure SQL Database"
        table_format = "Use [dbo].[table_name] format"
    
    # Get primary table for examples
    primary_table = table_names[0] if table_names else "records"
    
    return f"""You are a helpful data analyst assistant that answers questions about {scenario_name}.

{scenario_desc}

You have access to TWO tools. Choose the correct tool based on the question type.

## Tool 1: execute_sql (REQUIRED for data questions)
**USE THIS TOOL** for any question about:
- Numbers, counts, totals, averages, sums
- "How many...", "What is the total...", "What is the average..."
- "List all...", "Show me...", "Which..."
- Any question that requires querying database tables

Database: {sql_source}
Tables: {', '.join(table_names)}
{table_format}
{schema_text}

Example SQL questions:
{sql_examples}

## Tool 2: Azure AI Search (for document/policy questions)
Use for questions about:
- Policies, procedures, guidelines, rules
- "What is the policy for...", "How should we...", "What are the rules..."

Example document questions:
{doc_examples}

## Decision Rules:
1. Data questions (numbers, lists, specific records) → execute_sql
2. Policy/procedure questions → Azure AI Search
3. Combined questions → Use BOTH tools

## SQL Guidelines:
- Use T-SQL syntax
- {table_format}
- Available tables: {', '.join(table_names)}
- For JOINs: {'; '.join(join_hints) if join_hints else 'check schema for foreign keys'}
- Use TOP N instead of LIMIT

IMPORTANT: The search index contains ONLY policy documents, NOT database records. For data queries, always use execute_sql."""

instructions = build_agent_instructions(ontology_config, schema_prompt, USE_FABRIC, config_dir)
print(f"\nBuilt instructions ({len(instructions)} chars)")

# ============================================================================
# Tool Definitions
# ============================================================================

agent_tools = []

# SQL Execution Tool
if USE_FABRIC:
    sql_description = f"Execute a SQL query against Fabric Lakehouse. Use table names directly without schema prefix. Available tables: {', '.join(tables)}."
else:
    sql_description = f"Execute a SQL query against Azure SQL Database. Use [dbo].[table_name] format. Available tables: {', '.join(tables)}."

execute_sql_tool = FunctionTool(
    name="execute_sql",
    description=sql_description,
    parameters={
        "type": "object",
        "properties": {
            "sql_query": {
                "type": "string",
                "description": f"The T-SQL query to execute. Available tables: {', '.join(tables)}."
            }
        },
        "required": ["sql_query"],
        "additionalProperties": False
    },
    strict=True
)
agent_tools.append(execute_sql_tool)

# Azure AI Search Tool (native - always included)
search_tool = AzureAISearchAgentTool(
    azure_ai_search=AzureAISearchToolResource(
        indexes=[
            AISearchIndexResource(
                project_connection_id=SEARCH_CONNECTION_NAME,
                index_name=INDEX_NAME,
                query_type="simple",
            )
        ]
    )
)
agent_tools.append(search_tool)

# ============================================================================
# Create the Agent
# ============================================================================

print("\nInitializing AI Project Client...")
credential = DefaultAzureCredential()

try:
    project_client = AIProjectClient(
        endpoint=ENDPOINT,
        credential=credential
    )
    print("[OK] AI Project Client initialized")
except Exception as e:
    print(f"[FAIL] Failed to initialize client: {e}")
    sys.exit(1)

try:
    with project_client:
        # Delete existing agent if it exists
        print(f"\nChecking if agent '{AGENT_NAME}' already exists...")
        try:
            existing_agent = project_client.agents.get(AGENT_NAME)
            if existing_agent:
                print(f"  Found existing agent, deleting...")
                project_client.agents.delete(AGENT_NAME)
                print(f"[OK] Deleted existing agent")
        except Exception:
            print(f"  No existing agent found")

        # Create agent
        sql_mode = "Fabric SQL" if USE_FABRIC else "Azure SQL"
        print(f"\nCreating agent with {sql_mode} + Native AI Search tools...")
        agent_definition = PromptAgentDefinition(
            model=MODEL,
            instructions=instructions,
            tools=agent_tools
        )
        
        agent = project_client.agents.create(
            name=AGENT_NAME,
            definition=agent_definition
        )
        
        print(f"\n[OK] Agent created successfully!")
        print(f"  Agent ID: {agent.id}")
        print(f"  Agent Name: {agent.name}")
        
except Exception as e:
    print(f"\n[FAIL] Failed to create agent: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# Save Agent Configuration
# ============================================================================

agent_ids_path = os.path.join(config_dir, "agent_ids.json")
agent_ids = {}
if os.path.exists(agent_ids_path):
    with open(agent_ids_path) as f:
        agent_ids = json.load(f)

# Save agent-specific info
agent_ids["agent_id"] = agent.id
agent_ids["agent_name"] = agent.name
agent_ids["search_index"] = INDEX_NAME
agent_ids["sql_mode"] = "fabric" if USE_FABRIC else "azure_sql"
if not USE_FABRIC:
    agent_ids["sql_server"] = SQL_SERVER
    agent_ids["sql_database"] = SQL_DATABASE

with open(agent_ids_path, "w") as f:
    json.dump(agent_ids, f, indent=2)

print(f"\n[OK] Agent config saved to: {agent_ids_path}")

# ============================================================================
# Summary
# ============================================================================

sql_mode = "Fabric Lakehouse" if USE_FABRIC else "Azure SQL Database"

# Load sample questions for summary
sample_questions = load_sample_questions(config_dir)
if not sample_questions:
    sample_questions = generate_example_questions(ontology_config.get("tables", {}))

sql_example = sample_questions.get('sql', [''])[0] if sample_questions.get('sql') else "How many records are there?"
doc_example = sample_questions.get('doc', [''])[0] if sample_questions.get('doc') else "What are the policies?"
combined_example = sample_questions.get('combined', [''])[0] if sample_questions.get('combined') else "How do records compare to policies?"

print(f"""
{'='*60}
AI Foundry Agent Created Successfully!
{'='*60}

Agent ID: {agent.id}
Agent Name: {agent.name}
Model: {MODEL}
Scenario: {scenario_name}

Tools:
  1. execute_sql (function) - Query {sql_mode}
  2. AzureAISearchTool (native) - Document search with citations

Sample questions:
  SQL: "{sql_example}"
  Search: "{doc_example}"
  Combined: "{combined_example}"

Next step:
  python scripts/08_test_agent.py
""")
