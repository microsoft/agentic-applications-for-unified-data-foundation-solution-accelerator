"""
02 - Setup Fabric Lakehouse and Ontology
Creates Lakehouse and Ontology with data bindings (no data upload).

Usage:
    python 02_create_fabric_items.py [--data-folder <PATH>]

Prerequisites:
    - Run 01_generate_sample_data.py first (sets DATA_FOLDER in .env)
    - Azure CLI logged in (az login)
    - Fabric workspace with capacity assigned

What this script does:
    1. Creates a Lakehouse (or reuses existing)
    2. Creates Ontology with EntityTypes matching CSV schema
    3. Adds DataBindings to connect Ontology to Lakehouse tables
    4. Creates Relationships between entities
    
Note: Data upload is handled by 03_load_fabric_data.py
"""

import argparse
import os
import sys
import json
import time
import base64
import uuid
from datetime import datetime

# Load environment from azd + project .env
from load_env import load_all_env, get_data_folder
load_all_env()

# Azure imports
from azure.identity import AzureCliCredential
import requests

# ============================================================================
# Configuration
# ============================================================================

p = argparse.ArgumentParser(description="Setup Fabric Lakehouse and Ontology")
p.add_argument("--data-folder", help="Path to data folder (default: from .env)")
p.add_argument("--solutionname", default=os.getenv("SOLUTION_NAME") or os.getenv("SOLUTION_PREFIX") or os.getenv("AZURE_ENV_NAME", "demo"),
               help="Solution name prefix (default: from SOLUTION_NAME or SOLUTION_PREFIX)")
p.add_argument("--clean", action="store_true",
               help="Delete and recreate Lakehouse and Ontology (use when switching scenarios)")
args = p.parse_args()

WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID")
if not WORKSPACE_ID:
    print("ERROR: FABRIC_WORKSPACE_ID not set in .env")
    sys.exit(1)

# Get data folder - use arg if provided, else from .env with proper path resolution
if args.data_folder:
    data_dir = os.path.abspath(args.data_folder)
else:
    try:
        data_dir = get_data_folder()
    except ValueError:
        print("ERROR: DATA_FOLDER not set.")
        print("       Run 01_generate_data.py first, or pass --data-folder")
        sys.exit(1)

# Set up paths for new folder structure (config/, tables/, documents/)
config_dir = os.path.join(data_dir, "config")

# Check for config dir (new structure) or fallback to old structure
if not os.path.exists(config_dir):
    config_dir = data_dir

config_path = os.path.join(config_dir, "ontology_config.json")

if not os.path.exists(data_dir):
    print(f"ERROR: Data folder not found: {data_dir}")
    sys.exit(1)

if not os.path.exists(config_path):
    print(f"ERROR: ontology_config.json not found")
    print("       Run 01_generate_sample_data.py first")
    sys.exit(1)

SOLUTION_NAME = args.solutionname
FABRIC_API = "https://api.fabric.microsoft.com/v1"

with open(config_path) as f:
    ontology_config = json.load(f)

print(f"\n{'='*60}")
print(f"Setting up Fabric for: {SOLUTION_NAME}")
print(f"{'='*60}")
print(f"Workspace ID: {WORKSPACE_ID}")
print(f"Scenario: {ontology_config['name']}")
print(f"Tables: {', '.join(ontology_config['tables'].keys())}")

# ============================================================================
# Authentication
# ============================================================================

credential = AzureCliCredential()

def get_headers():
    """Get fresh headers with token"""
    token = credential.get_token("https://api.fabric.microsoft.com/.default").token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# ============================================================================
# Helper Functions
# ============================================================================

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

def wait_for_lro(operation_url, timeout=300):
    """Wait for long-running operation to complete"""
    start = time.time()
    while time.time() - start < timeout:
        resp = make_request("GET", operation_url)
        if resp.status_code == 200:
            result = resp.json()
            status = result.get("status", "Unknown")
            if status in ["Succeeded", "succeeded"]:
                # Try to get the resource from resourceLocation
                resource_location = result.get("resourceLocation")
                if resource_location:
                    res_resp = make_request("GET", resource_location)
                    if res_resp.status_code == 200:
                        return res_resp.json()
                return result
            elif status in ["Failed", "failed"]:
                raise Exception(f"Operation failed: {result}")
        time.sleep(3)
    raise TimeoutError("Operation timed out")

def find_item(item_type, display_name):
    """Find a Fabric item by type and name"""
    url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/items?type={item_type}"
    resp = make_request("GET", url)
    if resp.status_code == 200:
        for item in resp.json().get("value", []):
            if item["displayName"] == display_name:
                return item
    return None

def find_ontology(display_name):
    """Find an ontology by name using the ontologies endpoint"""
    url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/ontologies"
    resp = make_request("GET", url)
    if resp.status_code == 200:
        for ont in resp.json().get("value", []):
            if ont["displayName"] == display_name:
                return ont
    return None

def delete_item(item_type, item_id, item_name):
    """Delete a Fabric item"""
    url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/{item_type.lower()}s/{item_id}"
    resp = make_request("DELETE", url)
    if resp.status_code in [200, 202, 204]:
        print(f"  [OK] Deleted {item_type}: {item_name}")
        return True
    else:
        print(f"  [WARN] Could not delete {item_type} {item_name}: {resp.status_code}")
        return False

def delete_ontology(ontology_id, ontology_name):
    """Delete an ontology"""
    url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/ontologies/{ontology_id}"
    resp = make_request("DELETE", url)
    if resp.status_code in [200, 202, 204]:
        print(f"  [OK] Deleted Ontology: {ontology_name}")
        return True
    else:
        print(f"  [WARN] Could not delete Ontology {ontology_name}: {resp.status_code}")
        return False

def b64encode(content):
    """Encode content to base64"""
    if isinstance(content, dict):
        content = json.dumps(content)
    if isinstance(content, str):
        content = content.encode("utf-8")
    return base64.b64encode(content).decode("utf-8")

# ============================================================================
# Step 0: Determine lakehouse/ontology names (use local tracking, minimize API calls)
# ============================================================================

# Track suffix in a GLOBAL file (scripts folder) to persist across data folder changes
script_dir = os.path.dirname(os.path.abspath(__file__))
suffix_file = os.path.join(script_dir, "fabric_suffix.txt")

if os.path.exists(suffix_file):
    with open(suffix_file, "r") as f:
        current_suffix = int(f.read().strip())
else:
    current_suffix = 1

if args.clean:
    # Just increment suffix - don't bother deleting (Fabric will clean up old ones eventually)
    new_suffix = current_suffix + 1
    print(f"\n[0/4] Using new suffix: {new_suffix} (previous: {current_suffix})")
else:
    new_suffix = current_suffix

# Save new suffix
with open(suffix_file, "w") as f:
    f.write(str(new_suffix))

lakehouse_name = f"{SOLUTION_NAME}_lakehouse_{new_suffix}"
ontology_name = f"{SOLUTION_NAME}_ontology_{new_suffix}"

# ============================================================================
# Step 1: Create Lakehouse
# ============================================================================

print(f"\n[1/3] Creating Lakehouse...")

existing_lakehouse = find_item("Lakehouse", lakehouse_name)
if existing_lakehouse:
    lakehouse_id = existing_lakehouse["id"]
    print(f"  [OK] Using existing Lakehouse: {lakehouse_name} ({lakehouse_id})")
else:
    url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/items"
    payload = {"displayName": lakehouse_name, "type": "Lakehouse"}
    resp = make_request("POST", url, json=payload)
    
    if resp.status_code == 201:
        lakehouse_id = resp.json()["id"]
        print(f"  [OK] Created Lakehouse: {lakehouse_name} ({lakehouse_id})")
    elif resp.status_code == 202:
        # Long-running operation
        operation_url = resp.headers.get("Location")
        result = wait_for_lro(operation_url)
        lakehouse_id = result.get("id")
        print(f"  [OK] Created Lakehouse: {lakehouse_name} ({lakehouse_id})")
    else:
        print(f"  [FAIL] Failed to create Lakehouse: {resp.status_code} {resp.text}")
        sys.exit(1)

# Wait for Lakehouse to be ready
time.sleep(5)

# ============================================================================
# Step 2: Create Ontology (using dedicated ontologies API)
# ============================================================================

print(f"\n[2/3] Creating Ontology...")

existing_ontology = find_ontology(ontology_name)
if existing_ontology:
    ontology_id = existing_ontology["id"]
    print(f"  [OK] Using existing Ontology: {ontology_name} ({ontology_id})")
else:
    # Generate unique IDs for entities, properties, relationships
    base_ts = int(time.time() * 1000) % 10000000000
    entity_ids = {}
    property_ids = {}
    databinding_ids = {}
    
    for i, (table_name, table_def) in enumerate(ontology_config["tables"].items()):
        entity_id = str(base_ts + i * 1000)
        entity_ids[table_name] = entity_id
        databinding_ids[table_name] = str(uuid.uuid4())
        
        property_ids[table_name] = {}
        for j, col in enumerate(table_def["columns"]):
            property_ids[table_name][col] = str(base_ts + 100000000 + i * 1000 + j)
    
    # Build platform metadata
    platform_metadata = {
        "metadata": {
            "type": "Ontology",
            "displayName": ontology_name
        }
    }
    
    # Empty definition.json
    definition_json = {}
    
    # Build definition parts
    definition_parts = [
        {
            "path": ".platform",
            "payload": b64encode(platform_metadata),
            "payloadType": "InlineBase64"
        },
        {
            "path": "definition.json",
            "payload": b64encode(definition_json),
            "payloadType": "InlineBase64"
        }
    ]
    
    # Type mapping
    type_map = {
        "String": "String",
        "BigInt": "BigInt",
        "Double": "Double",
        "Boolean": "Boolean",
        "DateTime": "DateTime"
    }
    
    # Add EntityTypes and DataBindings for each table
    for table_name, table_def in ontology_config["tables"].items():
        entity_id = entity_ids[table_name]
        entity_name = table_name.title().replace("_", "")
        key_col = table_def["key"]
        key_prop_id = property_ids[table_name][key_col]
        
        # Build properties
        properties = []
        for col in table_def["columns"]:
            col_type = table_def["types"].get(col, "String")
            properties.append({
                "id": property_ids[table_name][col],
                "name": col,
                "redefines": None,
                "baseTypeNamespaceType": None,
                "valueType": type_map.get(col_type, "String")
            })
        
        # Entity Type definition
        entity_type = {
            "id": entity_id,
            "namespace": "usertypes",
            "baseEntityTypeId": None,
            "name": entity_name,
            "entityIdParts": [key_prop_id],
            "displayNamePropertyId": key_prop_id,
            "namespaceType": "Custom",
            "visibility": "Visible",
            "properties": properties,
            "timeseriesProperties": []
        }
        
        definition_parts.append({
            "path": f"EntityTypes/{entity_id}/definition.json",
            "payload": b64encode(entity_type),
            "payloadType": "InlineBase64"
        })
        
        # Data Binding - use dataBindingConfiguration structure
        property_bindings = []
        for col in table_def["columns"]:
            property_bindings.append({
                "sourceColumnName": col,
                "targetPropertyId": property_ids[table_name][col]
            })
        
        data_binding = {
            "id": databinding_ids[table_name],
            "dataBindingConfiguration": {
                "dataBindingType": "NonTimeSeries",
                "propertyBindings": property_bindings,
                "sourceTableProperties": {
                    "sourceType": "LakehouseTable",
                    "workspaceId": WORKSPACE_ID,
                    "itemId": lakehouse_id,
                    "sourceTableName": table_name
                }
            }
        }
        
        definition_parts.append({
            "path": f"EntityTypes/{entity_id}/DataBindings/{databinding_ids[table_name]}.json",
            "payload": b64encode(data_binding),
            "payloadType": "InlineBase64"
        })
        
        print(f"  + Entity: {entity_name} ({len(properties)} properties)")
    
    # Add Relationships
    for i, rel in enumerate(ontology_config.get("relationships", [])):
        from_table = rel["from"]
        to_table = rel["to"]
        from_entity_id = entity_ids[from_table]
        to_entity_id = entity_ids[to_table]
        rel_id = str(base_ts + 900000 + i)
        contextualization_id = str(uuid.uuid4())
        
        # Relationship Type
        relationship_type = {
            "id": rel_id,
            "namespace": "usertypes",
            "name": rel["name"],
            "namespaceType": "Custom",
            "source": {"entityTypeId": from_entity_id},
            "target": {"entityTypeId": to_entity_id}
        }
        
        definition_parts.append({
            "path": f"RelationshipTypes/{rel_id}/definition.json",
            "payload": b64encode(relationship_type),
            "payloadType": "InlineBase64"
        })
        
        # Relationship Contextualization (how to join the data)
        # The dataBindingTable should be the table that contains the foreign key
        # For a relationship from A -> B where B has a FK to A:
        #   - dataBindingTable = B (the table with the FK column)
        #   - sourceKeyRefBindings = maps FK column to source entity's PK property
        #   - targetKeyRefBindings = maps target's PK column to target entity's PK property
        
        from_key = ontology_config["tables"][from_table]["key"]  # PK of source entity (e.g., drivers.id)
        from_key_prop_id = property_ids[from_table][from_key]
        
        to_key_col = rel["toKey"]  # FK column in target table (e.g., orders.driver_id)
        to_table_pk = ontology_config["tables"][to_table]["key"]  # PK of target entity (e.g., orders.id)
        to_key_prop_id = property_ids[to_table][to_table_pk]
        
        contextualization = {
            "id": contextualization_id,
            "dataBindingTable": {
                "workspaceId": WORKSPACE_ID,
                "itemId": lakehouse_id,
                "sourceTableName": to_table,  # Use target table (the one with FK)
                "sourceType": "LakehouseTable"
            },
            "sourceKeyRefBindings": [
                {"sourceColumnName": to_key_col, "targetPropertyId": from_key_prop_id}  # FK col -> source PK prop
            ],
            "targetKeyRefBindings": [
                {"sourceColumnName": to_table_pk, "targetPropertyId": to_key_prop_id}  # target PK col -> target PK prop
            ]
        }
        
        definition_parts.append({
            "path": f"RelationshipTypes/{rel_id}/Contextualizations/{contextualization_id}.json",
            "payload": b64encode(contextualization),
            "payloadType": "InlineBase64"
        })
        
        print(f"  + Relationship: {from_table} -> {to_table}")
    
    # Create Ontology using dedicated ontologies endpoint
    ontology_payload = {
        "displayName": ontology_name,
        "description": f"Ontology for {ontology_config['name']} scenario",
        "definition": {
            "parts": definition_parts
        }
    }
    
    url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/ontologies"
    resp = make_request("POST", url, json=ontology_payload)
    
    if resp.status_code == 201:
        ontology_id = resp.json()["id"]
        print(f"  [OK] Created Ontology: {ontology_name} ({ontology_id})")
    elif resp.status_code == 202:
        operation_url = resp.headers.get("Location")
        result = wait_for_lro(operation_url)
        ontology_id = result.get("id")
        # If ID wasn't in LRO result, fetch it from the ontologies list
        if not ontology_id:
            created_ont = find_ontology(ontology_name)
            ontology_id = created_ont["id"] if created_ont else None
        print(f"  [OK] Created Ontology: {ontology_name} ({ontology_id})")
    else:
        print(f"  [FAIL] Failed to create Ontology: {resp.status_code}")
        print(f"    Response: {resp.text}")
        sys.exit(1)

# Wait for Ontology to be ready
time.sleep(3)

# ============================================================================
# Step 3: Save IDs for later scripts
# ============================================================================

print(f"\n[3/3] Saving configuration...")

ids_path = os.path.join(config_dir, "fabric_ids.json")
fabric_ids = {
    "lakehouse_id": lakehouse_id,
    "lakehouse_name": lakehouse_name,
    "ontology_id": ontology_id,
    "ontology_name": ontology_name,
    "solution_name": SOLUTION_NAME,
    "created_at": datetime.now().isoformat()
}
with open(ids_path, "w") as f:
    json.dump(fabric_ids, f, indent=2)
print(f"  [OK] Saved fabric_ids.json")

# ============================================================================
# Summary
# ============================================================================

print(f"\n{'='*60}")
print("Fabric Setup Complete!")
print(f"{'='*60}")
print(f"""
Lakehouse: {lakehouse_name}
  ID: {lakehouse_id}
  
Ontology: {ontology_name}
  ID: {ontology_id}
  Entities: {', '.join([t.title().replace('_', '') for t in ontology_config['tables'].keys()])}

IDs saved to: {ids_path}

Next step - Load data to Fabric:
  python scripts/03_load_fabric_data.py

After loading data:
  1. Open Fabric portal and verify Lakehouse has data
  2. Load CSV to Tables (Lakehouse > Get data > Load to Tables)
  3. Run: python scripts/04_generate_agent_prompt.py

Manual step required:
  - Create Data Agent in Fabric portal and map to Ontology
  - (Data Agent API doesn't support definition configuration yet)
""")


