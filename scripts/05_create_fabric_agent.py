"""
05 - Create Fabric Data Agent
Creates a Data Agent in Fabric workspace and links it to the Ontology.

Usage:
    python 05_create_fabric_agent.py

Prerequisites:
    - Run 02_create_fabric_items.py (creates Lakehouse and Ontology)
    - Run 03_load_fabric_data.py (loads data to tables)

What this script does:
    1. Creates a Data Agent in Fabric workspace
    2. Updates its definition to use the Ontology as data source
"""

import os
import sys
import json
import time
import base64

# Get script directory for relative paths
script_dir = os.path.dirname(os.path.abspath(__file__))

# Load environment from azd + project .env
from load_env import load_all_env
load_all_env()

from azure.identity import AzureCliCredential
import requests

# ============================================================================
# Configuration
# ============================================================================

# Project settings - from .env
WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID")
DATA_FOLDER = os.getenv("DATA_FOLDER")

if not WORKSPACE_ID:
    print("ERROR: FABRIC_WORKSPACE_ID not set in .env")
    sys.exit(1)

if not DATA_FOLDER:
    print("ERROR: DATA_FOLDER not set in .env")
    print("       Run 01_generate_sample_data.py first")
    sys.exit(1)

data_dir = os.path.abspath(DATA_FOLDER)

# Set up paths for new folder structure
config_dir = os.path.join(data_dir, "config")
if not os.path.exists(config_dir):
    config_dir = data_dir  # Fallback to old structure

# Load fabric_ids.json
fabric_ids_path = os.path.join(config_dir, "fabric_ids.json")
if not os.path.exists(fabric_ids_path):
    print(f"ERROR: fabric_ids.json not found")
    print("       Run 02_create_fabric_items.py first")
    sys.exit(1)

with open(fabric_ids_path) as f:
    fabric_ids = json.load(f)

ONTOLOGY_ID = fabric_ids["ontology_id"]
SOLUTION_NAME = fabric_ids["solution_name"]
DATA_AGENT_NAME = f"{SOLUTION_NAME}_dataagent"

FABRIC_API = "https://api.fabric.microsoft.com/v1"

print(f"\n{'='*60}")
print("Creating Fabric Data Agent")
print(f"{'='*60}")
print(f"Workspace ID: {WORKSPACE_ID}")
print(f"Ontology ID: {ONTOLOGY_ID}")
print(f"Data Agent Name: {DATA_AGENT_NAME}")

# ============================================================================
# Authentication
# ============================================================================

credential = AzureCliCredential()

def get_headers():
    """Get fresh headers with token"""
    token = credential.get_token("https://api.fabric.microsoft.com/.default").token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def make_request(method, url, **kwargs):
    """Make request with retry logic for 429 rate limiting"""
    max_retries = 5
    for attempt in range(max_retries):
        response = requests.request(method, url, headers=get_headers(), **kwargs)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 30))
            print(f"  Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        return response
    return response

def wait_for_lro(operation_url, operation_name="Operation", timeout=300):
    """Wait for long-running operation to complete"""
    start = time.time()
    while time.time() - start < timeout:
        resp = make_request("GET", operation_url)
        if resp.status_code == 200:
            result = resp.json()
            status = result.get("status", "Unknown")
            if status in ["Succeeded", "succeeded"]:
                print(f"  [OK] {operation_name} completed")
                return result
            elif status in ["Failed", "failed"]:
                print(f"  [FAIL] {operation_name} failed: {result}")
                return None
        time.sleep(3)
    print(f"  [FAIL] {operation_name} timed out")
    return None

def encode_to_base64(data):
    """Encode data to base64 string"""
    if isinstance(data, dict):
        data = json.dumps(data)
    return base64.b64encode(data.encode('utf-8')).decode('utf-8')

# ============================================================================
# Load Schema and Ontology Config for Instructions
# ============================================================================

# Load ontology config for scenario-specific instructions
config_path = os.path.join(config_dir, "ontology_config.json")
if os.path.exists(config_path):
    with open(config_path) as f:
        ontology_config = json.load(f)
    scenario_name = ontology_config.get("name", "Business Data")
    scenario_desc = ontology_config.get("description", "")
    tables = list(ontology_config.get("tables", {}).keys())
    print(f"\nScenario: {scenario_name}")
else:
    ontology_config = {}
    scenario_name = "Business Data"
    scenario_desc = ""
    tables = []

prompt_path = os.path.join(config_dir, "schema_prompt.txt")
if os.path.exists(prompt_path):
    with open(prompt_path) as f:
        schema_prompt = f.read()
    print(f"Loaded schema prompt ({len(schema_prompt)} chars)")
else:
    schema_prompt = ""

# Build scenario-specific instructions
def build_agent_instructions(config, schema):
    """Build agent instructions based on scenario"""
    scenario = config.get("scenario", "")
    name = config.get("name", "Business Data")
    desc = config.get("description", "")
    tables = config.get("tables", {})
    relationships = config.get("relationships", [])
    
    # Build entity descriptions
    entity_list = []
    for table_name, table_def in tables.items():
        cols = ", ".join(table_def.get("columns", []))
        entity_list.append(f"- {table_name.title()}: {cols}")
    
    # Build relationship descriptions
    rel_list = []
    for rel in relationships:
        rel_list.append(f"- {rel['from'].title()} -> {rel['to'].title()} (via {rel['fromKey']})")
    
    instructions = f"""You are a helpful assistant that answers questions about {name} data.

{desc}

You have access to an Ontology containing:
{chr(10).join(entity_list)}

Relationships:
{chr(10).join(rel_list) if rel_list else "- None defined"}

When answering questions:
1. Use the data to provide accurate answers
2. Support aggregations and group by operations  
3. Provide clear, concise answers based on the data
4. If you cannot find the answer, explain what data would be needed

{schema}

Support group by in GQL."""
    
    return instructions

# ============================================================================
# Step 1: Create Data Agent
# ============================================================================

print(f"\n[1/2] Creating Data Agent...")

# Check if Data Agent already exists
url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/items?type=DataAgent"
resp = make_request("GET", url)
existing_agent = None
if resp.status_code == 200:
    for item in resp.json().get("value", []):
        if item["displayName"] == DATA_AGENT_NAME:
            existing_agent = item
            break

data_agent_id = None
final_agent_name = DATA_AGENT_NAME

if existing_agent:
    data_agent_id = existing_agent["id"]
    print(f"  [OK] Using existing Data Agent: {DATA_AGENT_NAME} ({data_agent_id})")
else:
    # Try to create Data Agent, with suffix retry if name not available
    max_suffix = 10
    for suffix in range(max_suffix + 1):
        if suffix == 0:
            agent_name = DATA_AGENT_NAME
        else:
            agent_name = f"{DATA_AGENT_NAME}_{suffix}"
        
        payload = {
            "displayName": agent_name,
            "type": "DataAgent",
            "description": f"Data Agent for {SOLUTION_NAME} Ontology"
        }
        
        url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/items/"
        resp = make_request("POST", url, json=payload)
        
        if resp.status_code == 201:
            data_agent_id = resp.json()["id"]
            final_agent_name = agent_name
            print(f"  [OK] Created Data Agent: {agent_name} ({data_agent_id})")
            break
        elif resp.status_code == 202:
            result = wait_for_lro(resp.headers.get("Location"), "Data Agent creation")
            if result:
                resource_location = result.get("resourceLocation")
                if resource_location:
                    res_resp = make_request("GET", resource_location)
                    data_agent_id = res_resp.json()["id"]
                    final_agent_name = agent_name
                    print(f"  [OK] Created Data Agent: {agent_name} ({data_agent_id})")
                    break
        elif resp.status_code == 400:
            error_data = resp.json()
            if error_data.get("errorCode") == "ItemDisplayNameNotAvailableYet":
                print(f"  Name '{agent_name}' not available, trying with suffix...")
                continue
            else:
                print(f"  [FAIL] Failed to create Data Agent: {resp.status_code}")
                print(f"    Response: {resp.text}")
                sys.exit(1)
        else:
            print(f"  [FAIL] Failed to create Data Agent: {resp.status_code}")
            print(f"    Response: {resp.text}")
            sys.exit(1)
    
    if not data_agent_id:
        print(f"  [FAIL] Failed to create Data Agent after {max_suffix} retries")
        sys.exit(1)

# ============================================================================
# Step 2: Update Data Agent Definition with Ontology Source
# ============================================================================

print(f"\n[2/2] Configuring Data Agent with Ontology source...")

# Build scenario-specific instructions
agent_instructions = build_agent_instructions(ontology_config, schema_prompt)

# Data Agent configuration
data_agent_config = {
    "version": "1.0",
    "instructions": agent_instructions,
    "dataSources": [
        {
            "type": "Ontology",
            "workspaceId": WORKSPACE_ID,
            "itemId": ONTOLOGY_ID
        }
    ]
}

update_payload = {
    "definition": {
        "parts": [
            {
                "path": "dataAgent.json",
                "payload": encode_to_base64(data_agent_config),
                "payloadType": "InlineBase64"
            }
        ]
    }
}

url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/items/{data_agent_id}/updateDefinition"
resp = make_request("POST", url, json=update_payload)

if resp.status_code in [200, 202]:
    if resp.status_code == 202:
        wait_for_lro(resp.headers.get("Location"), "Definition update")
    print(f"  [OK] Data Agent configured with Ontology source")
else:
    print(f"  ⚠ Could not update Data Agent definition via API: {resp.status_code}")
    print(f"    Response: {resp.text}")
    print("    You may need to configure the Ontology source manually in Fabric portal:")
    print(f"    1. Go to workspace and open '{final_agent_name}'")
    print(f"    2. Add Ontology as data source")

# ============================================================================
# Save Data Agent ID
# ============================================================================

fabric_ids["data_agent_id"] = data_agent_id
fabric_ids["data_agent_name"] = final_agent_name
with open(fabric_ids_path, "w") as f:
    json.dump(fabric_ids, f, indent=2)

# Update .env with FABRIC_AGENT_ID
env_path = os.path.join(script_dir, "..", ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        env_content = f.read()
    
    lines = env_content.split("\n")
    updated = False
    for i, line in enumerate(lines):
        if line.startswith("FABRIC_AGENT_ID="):
            lines[i] = f"FABRIC_AGENT_ID={data_agent_id}"
            updated = True
            break
    
    if updated:
        with open(env_path, "w") as f:
            f.write("\n".join(lines))
        print(f"[OK] Updated .env with FABRIC_AGENT_ID={data_agent_id}")

# ============================================================================
# Summary
# ============================================================================

print(f"""
{'='*60}
Fabric Data Agent Created!
{'='*60}

Data Agent Name: {final_agent_name}
Data Agent ID: {data_agent_id}
Ontology Source: {ONTOLOGY_ID}

IDs saved to: {fabric_ids_path}

Next steps:
  Option A - Create AI Foundry agent with Fabric connection:
    1. In AI Foundry, add a Fabric connection to this Data Agent
    2. Create an agent that uses the fabric_dataagent tool
    3. Run 06_test_fabric_agent.py

  Option B - Use Foundry Agent directly (simpler):
    python scripts/07_create_foundry_agent.py
    python scripts/08_test_foundry_agent.py
""")


