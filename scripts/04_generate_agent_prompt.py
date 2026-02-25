"""
04 - Generate Optimized Prompt from Ontology
Reads ontology schema and generates an optimized prompt for NL2SQL agents.

Usage:
    python 04_generate_agent_prompt.py [--from-fabric] [--from-config]

Options:
    --from-fabric   Fetch schema from Fabric Ontology API (requires Fabric setup)
    --from-config   Generate from local ontology_config.json (default, no API calls)

Output:
    - data/<folder>/schema_prompt.txt - Optimized schema prompt for agents
"""

import argparse
import os
import sys
import json

# Load environment from azd + project .env
from load_env import load_all_env, get_data_folder
load_all_env()

# ============================================================================
# Configuration
# ============================================================================

p = argparse.ArgumentParser(description="Generate optimized schema prompt")
p.add_argument("--from-fabric", action="store_true", help="Fetch from Fabric API")
p.add_argument("--from-config", action="store_true", help="Use local config (default)")
p.add_argument("--data-folder", help="Path to data folder (default: from .env)")
args = p.parse_args()

# Default to config if neither specified
if not args.from_fabric:
    args.from_config = True

# Get data folder - use arg if provided, else from .env with proper path resolution
if args.data_folder:
    data_dir = os.path.abspath(args.data_folder)
else:
    try:
        data_dir = get_data_folder()
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

# Set up paths for new folder structure
config_dir = os.path.join(data_dir, "config")
if not os.path.exists(config_dir):
    config_dir = data_dir  # Fallback to old structure

print(f"\n{'='*60}")
print("Generating Optimized Schema Prompt")
print(f"{'='*60}")

# ============================================================================
# Load Schema
# ============================================================================

schema_data = None

if args.from_config:
    print("\nSource: Local ontology_config.json")
    config_path = os.path.join(config_dir, "ontology_config.json")
    
    if not os.path.exists(config_path):
        print(f"ERROR: Config not found at {config_path}")
        print("       Run 01_generate_sample_data.py first")
        sys.exit(1)
    
    with open(config_path) as f:
        config = json.load(f)
    
    # Convert config to schema format
    schema_data = {
        "name": config["name"],
        "description": config["description"],
        "tables": {},
        "relationships": config.get("relationships", [])
    }
    
    for table_name, table_def in config["tables"].items():
        schema_data["tables"][table_name] = {
            "columns": [
                {"name": col, "type": table_def["types"].get(col, "String")}
                for col in table_def["columns"]
            ],
            "key": table_def["key"]
        }

elif args.from_fabric:
    print("\nSource: Fabric Ontology API")
    
    # Check for fabric_ids.json
    ids_path = os.path.join(config_dir, "fabric_ids.json")
    if not os.path.exists(ids_path):
        print(f"ERROR: fabric_ids.json not found")
        print("       Run 02_create_fabric_items.py first")
        sys.exit(1)
    
    with open(ids_path) as f:
        fabric_ids = json.load(f)
    
    # Fetch from Fabric API
    from azure.identity import AzureCliCredential
    import requests
    import time
    import base64
    
    WORKSPACE_ID = fabric_ids["workspace_id"]
    ONTOLOGY_ID = fabric_ids["ontology_id"]
    FABRIC_API = "https://api.fabric.microsoft.com/v1"
    
    credential = AzureCliCredential()
    token = credential.get_token("https://api.fabric.microsoft.com/.default").token
    headers = {"Authorization": f"Bearer {token}"}
    
    # Use POST to getDefinition (async operation)
    url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/ontologies/{ONTOLOGY_ID}/getDefinition"
    resp = requests.post(url, headers=headers)
    
    # Handle async operation (202)
    if resp.status_code == 202:
        location = resp.headers.get("Location")
        retry_after = int(resp.headers.get("Retry-After", 2))
        print(f"  Waiting for async operation...")
        
        for attempt in range(15):
            time.sleep(retry_after)
            poll_resp = requests.get(location, headers=headers)
            
            if poll_resp.status_code == 200:
                poll_data = poll_resp.json()
                if poll_data.get("status") == "Succeeded":
                    resp = poll_resp
                    break
                elif poll_data.get("status") == "Failed":
                    print(f"ERROR: Operation failed: {poll_data}")
                    sys.exit(1)
            elif poll_resp.status_code != 202:
                print(f"ERROR: Poll failed: {poll_resp.status_code} {poll_resp.text}")
                sys.exit(1)
    
    # Parse definition parts
    parts = []
    if resp.status_code == 200:
        definition = resp.json().get("definition", {})
        parts = definition.get("parts", [])
    
    # If no parts from API, fall back to local config
    if not parts:
        print("  Note: Ontology API didn't return definition parts, using local config")
        config_path = os.path.join(data_dir, "ontology_config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
            
            schema_data = {
                "name": config["name"],
                "description": config["description"],
                "tables": {},
                "relationships": config.get("relationships", [])
            }
            
            for table_name, table_def in config["tables"].items():
                schema_data["tables"][table_name] = {
                    "columns": [
                        {"name": col, "type": table_def["types"].get(col, "String")}
                        for col in table_def["columns"]
                    ],
                    "key": table_def["key"]
                }
        else:
            print(f"ERROR: No ontology_config.json found")
            sys.exit(1)
    else:
        # Parse Fabric ontology definition from parts
        schema_data = {"name": "", "description": "", "tables": {}, "relationships": []}
        
        for part in parts:
            path = part.get("path", "")
            payload = base64.b64decode(part.get("payload", "")).decode("utf-8")
            
            try:
                content = json.loads(payload)
            except:
                continue
            
            # EntityType definition (Ontology format uses numeric IDs in path)
            if "/definition.json" in path and "EntityTypes/" in path:
                entity_name = content.get("name", "")
                table_name = entity_name.lower()
                
                columns = []
                key_prop_id = content.get("entityIdParts", [None])[0]
                key = None
                
                for prop in content.get("properties", []):
                    col_type = prop.get("valueType", "String")
                    columns.append({
                        "name": prop["name"],
                        "type": col_type
                    })
                    if prop.get("id") == key_prop_id:
                        key = prop["name"]
                
                if columns:
                    schema_data["tables"][table_name] = {"columns": columns, "key": key}
            
            # RelationshipType definition
            elif "/definition.json" in path and "RelationshipTypes/" in path:
                schema_data["relationships"].append({
                    "name": content.get("name"),
                    "from": content.get("source", {}).get("entityTypeId", ""),
                    "to": content.get("target", {}).get("entityTypeId", "")
                })
    
    print(f"  Fetched ontology: {fabric_ids['ontology_name']}")

# ============================================================================
# Generate Optimized Prompt
# ============================================================================

def build_optimized_prompt(schema):
    """Build token-efficient schema prompt"""
    lines = []
    lines.append("=== DATABASE SCHEMA ===")
    lines.append("")
    
    # Tables and columns in compact format
    for table_name, table_def in schema["tables"].items():
        cols = []
        for col in table_def["columns"]:
            type_abbrev = {
                "String": "str",
                "BigInt": "int", 
                "Double": "num",
                "Boolean": "bool",
                "DateTime": "date"
            }.get(col["type"], col["type"][:3].lower())
            
            key_marker = "*" if col["name"] == table_def.get("key") else ""
            cols.append(f"{col['name']}{key_marker}:{type_abbrev}")
        
        lines.append(f"{table_name}({', '.join(cols)})")
    
    # Relationships
    if schema.get("relationships"):
        lines.append("")
        lines.append("JOINS:")
        for rel in schema["relationships"]:
            lines.append(f"  {rel['from']}.{rel['fromKey']} -> {rel['to']}.{rel['toKey']}")
    
    # SQL hints
    lines.append("")
    lines.append("RULES:")
    lines.append("- Use T-SQL syntax")
    lines.append("- Key columns marked with *")
    lines.append("- Types: str=string, int=integer, num=decimal")
    
    return "\n".join(lines)

prompt_text = build_optimized_prompt(schema_data)

# Save prompt
prompt_path = os.path.join(config_dir, "schema_prompt.txt")
with open(prompt_path, "w") as f:
    f.write(prompt_text)

# Also save full schema as JSON for reference
schema_path = os.path.join(config_dir, "schema.json")
with open(schema_path, "w") as f:
    json.dump(schema_data, f, indent=2)

# ============================================================================
# Summary
# ============================================================================

print(f"\nGenerated prompt ({len(prompt_text)} chars):")
print("-" * 40)
print(prompt_text)
print("-" * 40)

print(f"""
Files saved:
  - {prompt_path} (for agent instructions)
  - {schema_path} (full schema JSON)

Token estimate: ~{len(prompt_text.split())} tokens

Next steps:
  - Run 05_create_fabric_agent.py to create Foundry agent with Fabric Data Agent tool
  - Or run 07_create_sql_agent.py to create agent with pyodbc SQL tool
""")
