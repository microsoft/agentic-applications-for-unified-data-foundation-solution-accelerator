"""
02 - Setup Fabric Lakehouse, Load Data, and Create Ontology
Creates Lakehouse, uploads CSV files, loads Delta tables, and creates Ontology.

Usage:
    python 02_create_fabric_items.py [--data-folder <PATH>] [--datasource-type ontology|lakehouse]

Prerequisites:
    - Run 01_generate_data.py first (sets DATA_FOLDER in .env)
    - Azure CLI logged in (az login)
    - Fabric workspace with capacity assigned

What this script does:
    1. Creates a Lakehouse (or reuses existing)
    2. Uploads CSV files to Lakehouse
    3. Loads CSV files as Delta tables via Fabric Notebook
    4. Creates Ontology with EntityTypes matching CSV schema
    5. Adds DataBindings to connect Ontology to Lakehouse tables
    6. Creates Relationships between entities
    
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
from azure.storage.filedatalake import DataLakeServiceClient
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
p.add_argument("--skip-data-agent", action="store_true",
               help="Skip Data Agent creation step")
p.add_argument("--datasource-type", choices=["ontology", "lakehouse"], default="ontology",
               help="Data source type for Data Agent: 'ontology' (default) or 'lakehouse'")
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
tables_dir = os.path.join(data_dir, "tables")

# Check for config dir (new structure) or fallback to old structure
if not os.path.exists(config_dir):
    config_dir = data_dir
    tables_dir = data_dir

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
ONELAKE_URL = "onelake.dfs.fabric.microsoft.com"

with open(config_path) as f:
    ontology_config = json.load(f)

print(f"\n{'='*60}")
print(f"Setting up Fabric for: {SOLUTION_NAME}")
print(f"{'='*60}")
print(f"Workspace ID: {WORKSPACE_ID}")
print(f"Scenario: {ontology_config['name']}")
print(f"Datasource type: {args.datasource_type}")
print(f"Tables: {', '.join(ontology_config['tables'].keys())}")

# ============================================================================
# Authentication
# ============================================================================

def get_headers(max_retries=3, retry_delay=5):
    """Get fresh headers with Fabric API token. Retries with exponential backoff on failure."""
    credential = AzureCliCredential()
    for attempt in range(1, max_retries + 1):
        try:
            token = credential.get_token("https://api.fabric.microsoft.com/.default").token
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        except Exception as e:
            if attempt < max_retries:
                credential = AzureCliCredential()
                wait = retry_delay * (2 ** (attempt - 1))
                print(f"  [RETRY] Token acquisition attempt {attempt}/{max_retries} failed: {e}")
                print(f"  Retrying in {wait} seconds...")
                time.sleep(wait)
            else:
                print(f"  [FAIL] Token acquisition failed after {max_retries} attempts: {e}")
                raise
    raise RuntimeError("Failed to acquire token after all retries")

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

def wait_for_lro(operation_url, operation_name="Operation", timeout=300):
    """Wait for long-running operation to complete"""
    start = time.time()
    while time.time() - start < timeout:
        resp = make_request("GET", operation_url)
        if resp.status_code == 200:
            result = resp.json()
            status = result.get("status", "Unknown")
            if status in ["Succeeded", "succeeded", "Completed", "completed"]:
                # Try to get the resource from resourceLocation
                resource_location = result.get("resourceLocation")
                if resource_location:
                    res_resp = make_request("GET", resource_location)
                    if res_resp.status_code == 200:
                        return res_resp.json()
                return result
            elif status in ["Failed", "failed"]:
                raise Exception(f"{operation_name} failed: {result}")
        time.sleep(3)
    raise TimeoutError(f"{operation_name} timed out")

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

def build_lakehouse_elements(tables_config: dict) -> list:
    """Build the full Fabric element hierarchy for a lakehouse datasource.

    Returns the element tree: [Files, Tables > dbo > tables > columns]
    with all tables and columns marked as selected.
    """
    files_node = {
        "id": str(uuid.uuid4()),
        "display_name": "Files",
        "type": "lakehouse_files",
        "is_selected": False,
        "children": []
    }

    table_nodes = []
    for table_name, table_def in tables_config.items():
        col_nodes = [
            {
                "id": str(uuid.uuid4()),
                "display_name": col_name,
                "type": "lakehouse_tables.column",
                "is_selected": True,
                "children": []
            }
            for col_name in table_def["columns"]
        ]
        table_nodes.append({
            "id": str(uuid.uuid4()),
            "display_name": table_name,
            "type": "lakehouse_tables.table",
            "is_selected": True,
            "children": col_nodes
        })

    dbo_node = {
        "id": str(uuid.uuid4()),
        "display_name": "dbo",
        "type": "lakehouse_tables.schema",
        "is_selected": True,
        "children": table_nodes
    }

    tables_node = {
        "id": str(uuid.uuid4()),
        "display_name": "Tables",
        "type": "lakehouse_tables",
        "is_selected": True,
        "children": [dbo_node]
    }

    return [files_node, tables_node]


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

lakehouse_name = f"lakehouse_{SOLUTION_NAME}_{new_suffix}"
use_lakehouse_datasource = (args.datasource_type == "lakehouse")

ontology_name = f"ontology_{SOLUTION_NAME}_{new_suffix}"
ontology_id = None

# ============================================================================
# Step 1: Create Lakehouse
# ============================================================================

# Calculate total steps dynamically
total_steps = 5  # Always: Lakehouse, Workspace, Upload, Notebook, Ontology
if not args.skip_data_agent:
    total_steps += 2  # Data Agent + Publish
total_steps += 1  # Save
step = 1

print(f"\n[{step}/{total_steps}] Creating Lakehouse...")

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
# Step 2: Get Workspace Name (needed for OneLake path)
# ============================================================================

step += 1
print(f"\n[{step}/{total_steps}] Getting workspace info...")
resp = make_request("GET", f"{FABRIC_API}/workspaces/{WORKSPACE_ID}")
if resp.status_code != 200:
    print(f"  [FAIL] Failed to get workspace info: {resp.text}")
    sys.exit(1)
workspace_name = resp.json()["displayName"]
print(f"  Workspace name: {workspace_name}")

# ============================================================================
# Step 3: Upload CSV Files to Lakehouse
# ============================================================================

step += 1
print(f"\n[{step}/{total_steps}] Uploading CSV files to Lakehouse...")

credential = AzureCliCredential()
account_url = f"https://{ONELAKE_URL}"
service_client = DataLakeServiceClient(account_url, credential=credential)
file_system_client = service_client.get_file_system_client(workspace_name)

data_path = f"{lakehouse_name}.Lakehouse/Files"
directory_client = file_system_client.get_directory_client(data_path)

uploaded_files = []
for table_name in ontology_config["tables"].keys():
    csv_file = f"{table_name}.csv"
    csv_path = os.path.join(tables_dir, csv_file)

    if not os.path.exists(csv_path):
        print(f"  [FAIL] CSV not found: {csv_file}")
        continue

    try:
        print(f"  Uploading {csv_file}...")
        file_client = directory_client.get_file_client(csv_file)
        with open(csv_path, "rb") as f:
            file_client.upload_data(f, overwrite=True)

        file_size = os.path.getsize(csv_path)
        print(f"  [OK] {csv_file} uploaded ({file_size:,} bytes)")
        uploaded_files.append(csv_file)
    except Exception as e:
        print(f"  [FAIL] Failed to upload {csv_file}: {e}")
        sys.exit(1)

print("  Waiting for files to be available...")
time.sleep(10)

# ============================================================================
# Step 4: Load CSV Files as Delta Tables via Fabric Notebook
# ============================================================================

step += 1
print(f"\n[{step}/{total_steps}] Loading CSV files as Delta tables via Fabric Notebook...")

table_names = list(ontology_config["tables"].keys())
spark_code_lines = [
    "import os",
    "",
    f"lakehouse_name = '{lakehouse_name}'",
    f"table_names = {table_names}",
    "",
    "for table_name in table_names:",
    "    csv_path = f'Files/{table_name}.csv'",
    "    print(f'Loading {table_name} from {csv_path}...')",
    "    df = spark.read.option('header', 'true').option('inferSchema', 'true').csv(csv_path)",
    "    df.write.mode('overwrite').format('delta').saveAsTable(table_name)",
    "    print(f'  [OK] {table_name}: {df.count()} rows')",
    "",
    "print('All tables loaded successfully.')",
]
spark_code = "\n".join(spark_code_lines)

notebook_name = f"load_tables_{lakehouse_name}"

notebook_metadata = {
    "language_info": {"name": "python"},
    "trident": {
        "lakehouse": {
            "default_lakehouse": lakehouse_id,
            "default_lakehouse_name": lakehouse_name,
            "default_lakehouse_workspace_id": WORKSPACE_ID,
            "known_lakehouses": [{"id": lakehouse_id}]
        }
    }
}

notebook_payload_content = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": notebook_metadata,
    "cells": [
        {
            "cell_type": "code",
            "source": [spark_code],
            "metadata": {},
            "outputs": []
        }
    ]
}

# Check if notebook already exists, delete it to recreate
print(f"  Creating notebook '{notebook_name}'...")
existing_nb_url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/items?type=Notebook"
existing_nb_resp = make_request("GET", existing_nb_url)
if existing_nb_resp.status_code == 200:
    for item in existing_nb_resp.json().get("value", []):
        if item["displayName"] == notebook_name:
            del_url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/items/{item['id']}"
            make_request("DELETE", del_url)
            print(f"  Deleted existing notebook '{notebook_name}'")
            time.sleep(10)
            break

create_nb_payload = {
    "displayName": notebook_name,
    "type": "Notebook",
    "definition": {
        "format": "ipynb",
        "parts": [
            {
                "path": "artifact.content.ipynb",
                "payload": b64encode(notebook_payload_content),
                "payloadType": "InlineBase64"
            }
        ]
    }
}

create_url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/items"

# Retry notebook creation in case the name is not yet released after deletion
for nb_attempt in range(5):
    resp = make_request("POST", create_url, json=create_nb_payload)
    if resp.status_code == 400 and "NotAvailableYet" in resp.text:
        wait_secs = 15 * (nb_attempt + 1)
        print(f"  Name not released yet (attempt {nb_attempt+1}/5). Waiting {wait_secs}s...")
        time.sleep(wait_secs)
        continue
    break

if resp.status_code == 201:
    notebook_id = resp.json()["id"]
    print(f"  [OK] Created notebook: {notebook_name} ({notebook_id})")
elif resp.status_code == 202:
    operation_url = resp.headers.get("Location")
    wait_for_lro(operation_url, "Notebook creation")
    nb_resp = make_request("GET", existing_nb_url)
    notebook_id = None
    if nb_resp.status_code == 200:
        for item in nb_resp.json().get("value", []):
            if item["displayName"] == notebook_name:
                notebook_id = item["id"]
                break
    if not notebook_id:
        print(f"  [FAIL] Could not find created notebook")
        sys.exit(1)
    print(f"  [OK] Created notebook: {notebook_name} ({notebook_id})")
else:
    print(f"  [FAIL] Failed to create notebook: {resp.status_code} {resp.text}")
    sys.exit(1)

print(f"  Running notebook to load tables...")
run_url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/items/{notebook_id}/jobs/instances?jobType=RunNotebook"

max_retries = 3
notebook_succeeded = False
for attempt in range(1, max_retries + 1):
    if attempt > 1:
        print(f"  Retrying notebook execution (attempt {attempt}/{max_retries})...")
        time.sleep(30)
    run_resp = make_request("POST", run_url)

    if run_resp.status_code in [200, 202]:
        operation_url = run_resp.headers.get("Location")
        if operation_url:
            try:
                wait_for_lro(operation_url, "Notebook execution", timeout=600)
                print(f"  [OK] Notebook execution completed - all tables loaded")
                notebook_succeeded = True
                break
            except Exception as e:
                if attempt < max_retries:
                    print(f"  [WARN] Spark error (attempt {attempt}/{max_retries}): retrying...")
                    continue
                raise
        else:
            print("  Waiting for notebook execution...")
            time.sleep(60)
            print(f"  [OK] Notebook execution completed - all tables loaded")
            notebook_succeeded = True
            break
    else:
        print(f"  [WARN] Failed to run notebook: {run_resp.status_code} {run_resp.text}")
        if attempt == max_retries:
            print(f"  [FAIL] All {max_retries} attempts to run notebook failed.")
            sys.exit(1)

if not notebook_succeeded:
    print(f"  [FAIL] Notebook execution failed after {max_retries} attempts.")
    sys.exit(1)

print("  Waiting for tables to be indexed...")
time.sleep(30)

# ============================================================================
# Step 5: Create Ontology (using dedicated ontologies API)
# ============================================================================

step += 1
print(f"\n[{step}/{total_steps}] Creating Ontology...")

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
        "DateTime": "DateTime",
        "Date": "DateTime",
        "Int": "BigInt",
        "Float": "Double"
    }
    
    # Add EntityTypes and DataBindings for each table
    for table_name, table_def in ontology_config["tables"].items():
        entity_id = entity_ids[table_name]
        entity_name = table_name.title().replace("_", "")
        key_col = table_def["key"]
        key_prop_id = property_ids[table_name][key_col]
        
        # Find DateTime column for timeseries binding
        timeseries_col = None
        for col in table_def["columns"]:
            col_type = table_def["types"].get(col, "String")
            if col_type in ["DateTime", "Date"]:
                timeseries_col = col
                break
        
        # Build static properties - all columns EXCEPT DateTime
        properties = []
        for col in table_def["columns"]:
            if col == timeseries_col:
                continue  # DateTime goes in timeseriesProperties
            col_type = table_def["types"].get(col, "String")
            properties.append({
                "id": property_ids[table_name][col],
                "name": col,
                "redefines": None,
                "baseTypeNamespaceType": None,
                "valueType": type_map.get(col_type, "String")
            })
        
        # Build timeseries properties - only DateTime columns
        timeseries_properties = []
        if timeseries_col:
            timeseries_properties.append({
                "id": property_ids[table_name][timeseries_col],
                "name": timeseries_col,
                "redefines": None,
                "baseTypeNamespaceType": None,
                "valueType": "DateTime"
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
            "timeseriesProperties": timeseries_properties
        }
        
        definition_parts.append({
            "path": f"EntityTypes/{entity_id}/definition.json",
            "payload": b64encode(entity_type),
            "payloadType": "InlineBase64"
        })
        
        # Binding 1: Static (NonTimeSeries) - all columns EXCEPT DateTime
        static_property_bindings = []
        for col in table_def["columns"]:
            if col == timeseries_col:
                continue  # DateTime goes in timeseries binding
            static_property_bindings.append({
                "sourceColumnName": col,
                "targetPropertyId": property_ids[table_name][col]
            })
        
        static_binding_id = databinding_ids[table_name]
        static_binding = {
            "id": static_binding_id,
            "dataBindingConfiguration": {
                "dataBindingType": "NonTimeSeries",
                "propertyBindings": static_property_bindings,
                "sourceTableProperties": {
                    "sourceType": "LakehouseTable",
                    "workspaceId": WORKSPACE_ID,
                    "itemId": lakehouse_id,
                    "sourceTableName": table_name
                }
            }
        }
        
        definition_parts.append({
            "path": f"EntityTypes/{entity_id}/DataBindings/{static_binding_id}.json",
            "payload": b64encode(static_binding),
            "payloadType": "InlineBase64"
        })
        
        # Binding 2: TimeSeries - for DateTime column (if exists)
        if timeseries_col:
            ts_binding_id = str(uuid.uuid4())
            ts_binding = {
                "id": ts_binding_id,
                "dataBindingConfiguration": {
                    "dataBindingType": "TimeSeries",
                    "timestampColumnName": timeseries_col,
                    "propertyBindings": [
                        {"sourceColumnName": key_col, "targetPropertyId": key_prop_id},
                        {"sourceColumnName": timeseries_col, "targetPropertyId": property_ids[table_name][timeseries_col]}
                    ],
                    "sourceTableProperties": {
                        "sourceType": "LakehouseTable",
                        "workspaceId": WORKSPACE_ID,
                        "itemId": lakehouse_id,
                        "sourceTableName": table_name
                    }
                }
            }
            
            definition_parts.append({
                "path": f"EntityTypes/{entity_id}/DataBindings/{ts_binding_id}.json",
                "payload": b64encode(ts_binding),
                "payloadType": "InlineBase64"
            })
            
            print(f"  + Entity: {entity_name} ({len(properties)} static + 1 timeseries)")
        else:
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
        # For relationship: from_table (with FK) -> to_table (with PK)
        # Example: inspections.part_id -> parts.part_id
        #   - Source entity = inspections (has the FK)
        #   - Target entity = parts (has the PK being referenced)
        #   - dataBindingTable = from_table (inspections - contains both source PK and target FK)
        #   - sourceKeyRefBindings = maps source PK column to source entity's KEY property
        #   - targetKeyRefBindings = maps FK column to target entity's KEY property
        
        from_key_col = rel["fromKey"]  # FK column in source table (e.g., inspections.part_id)
        to_key_col = rel["toKey"]      # PK column in target table (e.g., parts.part_id)
        
        # Source entity's primary key
        from_table_pk = ontology_config["tables"][from_table]["key"]  # e.g., inspection_id
        from_pk_prop_id = property_ids[from_table][from_table_pk]
        
        # Target entity's primary key (must use the actual entity key, not the join column)
        to_table_pk = ontology_config["tables"][to_table]["key"]  
        to_pk_prop_id = property_ids[to_table][to_table_pk]  
        
        if to_key_col != to_table_pk:
            print(f"  ! Skipping relationship {from_table} -> {to_table}: toKey '{to_key_col}' is not the target entity's primary key '{to_table_pk}'")
            print(f"    Fabric relationships require targetKeyRefBindings to reference the target entity's key property (entityIdParts)")
            continue
        
        contextualization = {
            "id": contextualization_id,
            "dataBindingTable": {
                "workspaceId": WORKSPACE_ID,
                "itemId": lakehouse_id,
                "sourceTableName": from_table,  # Table with the FK (inspections)
                "sourceType": "LakehouseTable"
            },
            "sourceKeyRefBindings": [
                {"sourceColumnName": from_table_pk, "targetPropertyId": from_pk_prop_id}  # source PK col -> source entity KEY
            ],
            "targetKeyRefBindings": [
                {"sourceColumnName": from_key_col, "targetPropertyId": to_pk_prop_id}  # FK col -> target entity KEY
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

    # Save ontology definition parts
    ontology_def_path = os.path.join(config_dir, "ontology_definition_parts.json")
    with open(ontology_def_path, "w") as f:
        json.dump(definition_parts, f)
    print(f"  [OK] Saved definition parts")


# Wait for Ontology to be ready
time.sleep(3)

# ============================================================================
# Step 6: Create Data Agent (via Fabric REST API)
# ============================================================================

data_agent_id = None
data_agent_name = None

if not args.skip_data_agent:
    data_agent_name = f"dataagent_{SOLUTION_NAME}_{new_suffix}"
    step += 1
    print(f"\n[{step}/{total_steps}] Creating Data Agent...")

    # Check if Data Agent already exists
    existing_da = find_item("DataAgent", data_agent_name)
    # Also check via dataAgents endpoint
    if not existing_da:
        da_list_url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/dataAgents"
        da_list_resp = make_request("GET", da_list_url)
        if da_list_resp.status_code == 200:
            for da in da_list_resp.json().get("value", []):
                if da["displayName"] == data_agent_name:
                    existing_da = da
                    break
    if existing_da:
        data_agent_id = existing_da["id"]
        print(f"  [OK] Using existing Data Agent: {data_agent_name} ({data_agent_id})")
    else:
        # Schema URL base for Data Agent definition parts
        DA_SCHEMA_BASE = "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition"

        # --- Build definition parts (matching Fabric portal format) ---

        # 1. data_agent.json (required - schema version)
        data_agent_config = {"$schema": f"{DA_SCHEMA_BASE}/dataAgent/2.1.0/schema.json"}

        # 2. stage_config.json (AI instructions)
        schema_prompt_path = os.path.join(config_dir, "schema_prompt.txt")
        ai_instructions = None
        if os.path.exists(schema_prompt_path):
            with open(schema_prompt_path, "r") as f:
                ai_instructions = f.read().strip()
            print(f"  Loaded AI instructions ({len(ai_instructions)} chars)")

        stage_config = {
            "$schema": f"{DA_SCHEMA_BASE}/stageConfiguration/1.0.0/schema.json",
            "aiInstructions": ai_instructions
        }

        # 3. datasource.json (ontology or lakehouse reference)
        if use_lakehouse_datasource:
            da_source_name = f"lakehouse-{lakehouse_name}"
            # Build the full element hierarchy so tables are selected at creation time
            elements = build_lakehouse_elements(ontology_config["tables"])

            datasource = {
                "$schema": f"{DA_SCHEMA_BASE}/dataSource/1.0.0/schema.json",
                "artifactId": lakehouse_id,
                "workspaceId": WORKSPACE_ID,
                "dataSourceInstructions": None,
                "displayName": lakehouse_name,
                "type": "lakehouse",
                "userDescription": None,
                "metadata": {},
                "elements": elements
            }
        else:
            da_source_name = f"ontology-{ontology_name}"
            elements = []
            for table_name, table_def in ontology_config["tables"].items():
                entity_name = table_name.title().replace("_", "")
                col_list = ",".join(table_def["columns"])
                elements.append({
                    "id": entity_name,
                    "is_selected": True,
                    "display_name": entity_name,
                    "type": "ontology.entity",
                    "description": col_list,
                    "children": []
                })

            datasource = {
                "$schema": f"{DA_SCHEMA_BASE}/dataSource/1.0.0/schema.json",
                "artifactId": ontology_id,
                "workspaceId": WORKSPACE_ID,
                "dataSourceInstructions": None,
                "displayName": ontology_name,
                "type": "ontology",
                "userDescription": None,
                "metadata": {},
                "elements": elements
            }

        # 4. fewshots.json (sample questions, if available)
        fewshots = {"$schema": f"{DA_SCHEMA_BASE}/fewShots/1.0.0/schema.json", "fewShots": []}
        sample_questions_path = os.path.join(config_dir, "sample_questions.txt")
        if os.path.exists(sample_questions_path):
            with open(sample_questions_path, "r") as f:
                content = f.read()
            in_sql = False
            for line in content.split("\n"):
                line = line.strip()
                if "SQL QUESTIONS" in line:
                    in_sql = True
                    continue
                if line.startswith("===") and in_sql:
                    break
                if in_sql and line and line[0].isdigit():
                    question = line.split(". ", 1)[-1] if ". " in line else line
                    fewshots["fewShots"].append({
                        "id": str(uuid.uuid4()),
                        "question": question,
                        "query": ""
                    })
            if fewshots["fewShots"]:
                print(f"  Loaded {len(fewshots['fewShots'])} fewshot questions")

        # Build definition parts (same structure for both datasource types)
        da_definition_parts = [
            {"path": "Files/Config/data_agent.json", "payload": b64encode(data_agent_config), "payloadType": "InlineBase64"},
            {"path": "Files/Config/draft/stage_config.json", "payload": b64encode(stage_config), "payloadType": "InlineBase64"},
            {"path": f"Files/Config/draft/{da_source_name}/datasource.json", "payload": b64encode(datasource), "payloadType": "InlineBase64"},
        ]
        if fewshots["fewShots"]:
            da_definition_parts.append(
                {"path": f"Files/Config/draft/{da_source_name}/fewshots.json", "payload": b64encode(fewshots), "payloadType": "InlineBase64"}
            )
        da_payload = {
            "displayName": data_agent_name,
            "description": f"Data Agent for {ontology_config['name']}",
            "definition": {
                "parts": da_definition_parts
            }
        }
        if use_lakehouse_datasource:
            table_count = len(ontology_config.get("tables", {}))
            datasource_label = f"lakehouse {lakehouse_name}"
            print(f"  Creating '{data_agent_name}' with {len(da_definition_parts)} definition parts...")
            print(f"  Datasource: {datasource_label} ({table_count} tables pre-selected)")
        else:
            datasource_label = f"ontology {ontology_name}"
            print(f"  Creating '{data_agent_name}' with {len(da_definition_parts)} definition parts...")
            print(f"  Datasource: {datasource_label} ({len(elements)} entities)")

        url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/dataAgents"

        # Save payload for debugging regardless of outcome
        da_debug_path = os.path.join(config_dir, "data_agent_payload_debug.json")
        with open(da_debug_path, "w") as f:
            json.dump(da_payload, f, indent=2)
        print(f"  Payload saved to {da_debug_path} for debugging")

        resp = make_request("POST", url, json=da_payload)

        if resp.status_code == 201:
            data_agent_id = resp.json()["id"]
            print(f"  [OK] Created Data Agent: {data_agent_name} ({data_agent_id})")
        elif resp.status_code == 202:
            operation_url = resp.headers.get("Location")
            try:
                if operation_url:
                    result = wait_for_lro(operation_url, "Data Agent creation")
                    data_agent_id = result.get("id")
                if not data_agent_id:
                    created_da = find_item("DataAgent", data_agent_name)
                    data_agent_id = created_da["id"] if created_da else None
                if data_agent_id:
                    print(f"  [OK] Created Data Agent: {data_agent_name} ({data_agent_id})")
                else:
                    print(f"  [WARN] Could not find Data Agent after async creation")
            except Exception as e:
                print(f"  [WARN] Data Agent creation failed: {e}")
                created_da = find_item("DataAgent", data_agent_name)
                if created_da:
                    data_agent_id = created_da["id"]
                    print(f"  [OK] Found Data Agent despite LRO error: {data_agent_id}")
        else:
            if resp.status_code == 400 and "AlreadyInUse" in resp.text:
                # Name is reserved by a zombie agent — try with timestamp suffix
                ts_suffix = int(time.time()) % 10000
                alt_name = f"dataagent_{SOLUTION_NAME}_{ts_suffix}"
                print(f"  [WARN] Name '{data_agent_name}' is reserved (zombie). Trying '{alt_name}'...")
                da_payload["displayName"] = alt_name
                resp2 = make_request("POST", url, json=da_payload)
                if resp2.status_code == 201:
                    data_agent_id = resp2.json()["id"]
                    data_agent_name = alt_name
                    print(f"  [OK] Created Data Agent: {data_agent_name} ({data_agent_id})")
                elif resp2.status_code == 202:
                    operation_url = resp2.headers.get("Location")
                    try:
                        if operation_url:
                            result = wait_for_lro(operation_url, "Data Agent creation")
                            data_agent_id = result.get("id")
                        if not data_agent_id:
                            created_da = find_item("DataAgent", alt_name)
                            data_agent_id = created_da["id"] if created_da else None
                        if data_agent_id:
                            data_agent_name = alt_name
                            print(f"  [OK] Created Data Agent: {data_agent_name} ({data_agent_id})")
                    except Exception as e2:
                        print(f"  [WARN] Retry also failed: {e2}")
                else:
                    print(f"  [WARN] Retry also failed: {resp2.status_code} {resp2.text}")
            else:
                print(f"  [WARN] Failed to create Data Agent: {resp.status_code}")
                print(f"    Response: {resp.text}")
                print(f"    Continuing without Data Agent (create manually in Fabric portal)")

        # Save definition parts for debugging
        if data_agent_id:
            da_def_path = os.path.join(config_dir, "data_agent_definition_parts.json")
            saved_parts = da_payload.get("definition", {}).get("parts", [])
            with open(da_def_path, "w") as f:
                json.dump(saved_parts, f)
            print(f"  [OK] Saved definition parts")
else:
    print(f"\n[--] Skipping Data Agent creation (--skip-data-agent)")

# ============================================================================
# Step 7: Publish Data Agent (so it can be used as MCP server)
# ============================================================================

if not args.skip_data_agent and data_agent_id:
    step += 1
    print(f"\n[{step}/{total_steps}] Publishing Data Agent as MCP server...")

    try:
        # Get current definition
        get_def_url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/dataAgents/{data_agent_id}/getDefinition"
        get_def_resp = make_request("POST", get_def_url)

        if get_def_resp.status_code == 202:
            op_url = get_def_resp.headers.get("Location")
            time.sleep(3)
            get_def_resp = make_request("GET", op_url + "/result")

        if get_def_resp.status_code != 200:
            raise Exception(f"Failed to get definition: {get_def_resp.status_code} {get_def_resp.text[:300]}")

        current_parts = get_def_resp.json().get("definition", {}).get("parts", [])
        print(f"  Current definition: {len(current_parts)} parts")

        # Check if already published
        already_published = any("publish_info.json" in p.get("path", "") for p in current_parts)
        if already_published:
            print(f"  [OK] Data Agent already published")
        else:
            # Find draft parts to copy to published folder
            draft_stage_config = None
            datasource_folder = None
            draft_datasource = None
            draft_fewshots = None
            draft_fewshots_path = None

            for p in current_parts:
                path = p.get("path", "")
                if "draft/stage_config.json" in path:
                    draft_stage_config = p["payload"]
                elif "draft/" in path and "datasource.json" in path:
                    draft_datasource = p["payload"]
                    segs = path.split("/")
                    idx = segs.index("draft")
                    datasource_folder = segs[idx + 1]
                elif "draft/" in path and "fewshots.json" in path:
                    draft_fewshots = p["payload"]

            if not (draft_stage_config and draft_datasource and datasource_folder):
                raise Exception("Could not find draft parts to publish")

            # Build publish parts
            DA_SCHEMA_BASE_PUB = "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition"
            publish_info = {
                "$schema": f"{DA_SCHEMA_BASE_PUB}/publishInfo/1.0.0/schema.json",
                "description": ontology_config.get("description", f"Data Agent for {ontology_config.get('name', 'data analysis')}")
            }

            new_parts = list(current_parts)
            new_parts.append({"path": "Files/Config/publish_info.json", "payload": b64encode(publish_info), "payloadType": "InlineBase64"})
            new_parts.append({"path": "Files/Config/published/stage_config.json", "payload": draft_stage_config, "payloadType": "InlineBase64"})
            new_parts.append({"path": f"Files/Config/published/{datasource_folder}/datasource.json", "payload": draft_datasource, "payloadType": "InlineBase64"})
            if draft_fewshots:
                new_parts.append({"path": f"Files/Config/published/{datasource_folder}/fewshots.json", "payload": draft_fewshots, "payloadType": "InlineBase64"})

            print(f"  Publishing with {len(new_parts)} parts (added {len(new_parts) - len(current_parts)} publish parts)...")

            update_def_url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/dataAgents/{data_agent_id}/updateDefinition"
            update_resp = make_request("POST", update_def_url, json={"definition": {"parts": new_parts}})

            if update_resp.status_code == 200:
                print(f"  [OK] Data Agent published")
            elif update_resp.status_code == 202:
                op_url = update_resp.headers.get("Location")
                if op_url:
                    result = wait_for_lro(op_url, "Data Agent publish")
                print(f"  [OK] Data Agent published")
            else:
                raise Exception(f"Publish failed: {update_resp.status_code} {update_resp.text[:300]}")

            # Build MCP endpoint URL
            mcp_endpoint = f"https://api.fabric.microsoft.com/v1/mcp/workspaces/{WORKSPACE_ID}/dataagents/{data_agent_id}/agent"
            print(f"  MCP Endpoint: {mcp_endpoint}")

    except Exception as e:
        print(f"  [WARN] Failed to publish Data Agent: {e}")
        print(f"         You can publish manually in the Fabric portal")
        print(f"         Open the Data Agent > Home tab > Publish")

if not args.skip_data_agent and not data_agent_id:
    step += 1
    print(f"\n[{step}/{total_steps}] Skipping publish (Data Agent not created)")

# ============================================================================
# Step 8: Save IDs for later scripts
# ============================================================================

step += 1
print(f"\n[{step}/{total_steps}] Saving configuration...")

ids_path = os.path.join(config_dir, "fabric_ids.json")
fabric_ids = {
    "lakehouse_id": lakehouse_id,
    "lakehouse_name": lakehouse_name,
    "ontology_id": ontology_id,
    "ontology_name": ontology_name,
    "data_agent_id": data_agent_id,
    "data_agent_name": data_agent_name,
    "datasource_type": args.datasource_type,
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

da_summary = ""
if data_agent_id:
    datasource_label = f"lakehouse {lakehouse_name}" if use_lakehouse_datasource else f"ontology {ontology_name}"
    item_count = len(ontology_config['tables'])
    item_type = "tables" if use_lakehouse_datasource else "entities"
    da_summary = f"""
Data Agent: {data_agent_name}
  ID: {data_agent_id}
  Datasource: {datasource_label} ({item_count} {item_type})"""
elif not args.skip_data_agent:
    da_summary = """
Data Agent: Not created (API error - create manually in Fabric portal)"""
else:
    da_summary = """
Data Agent: Skipped (--skip-data-agent)"""

ontology_summary = f"""
Ontology: {ontology_name}
  ID: {ontology_id}
  Entities: {', '.join([t.title().replace('_', '') for t in ontology_config['tables'].keys()])}"""

print(f"""
Lakehouse: {lakehouse_name}
  ID: {lakehouse_id}
  Data: {len(uploaded_files)} CSV files uploaded and loaded as Delta tables
{ontology_summary}
{da_summary}

IDs saved to: {ids_path}

Next step - Generate schema prompt:
  python scripts/03_generate_agent_prompt.py
""")
