"""
03 - Load Data to Fabric Lakehouse
Uploads CSV files to Lakehouse and loads them as Delta tables.

Usage:
    python 03_load_fabric_data.py [--data-folder <PATH>]

Prerequisites:
    - Run 01_generate_sample_data.py (sets DATA_FOLDER in .env)
    - Run 02_create_fabric_items.py (creates Lakehouse)
    - Azure CLI logged in (az login)

What this script does:
    1. Reads fabric_ids.json from data folder
    2. Uploads CSV files to Lakehouse Files folder
    3. Loads CSV files as Delta tables using Fabric API
"""

import argparse
import os
import sys
import json
import time
import base64

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

p = argparse.ArgumentParser(description="Load data to Fabric Lakehouse")
p.add_argument("--data-folder", help="Path to data folder (default: from .env)")
p.add_argument("--skip-tables", action="store_true",
               help="Skip loading to Delta tables (upload files only)")
args = p.parse_args()

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

# Check for required files
config_path = os.path.join(config_dir, "ontology_config.json")
fabric_ids_path = os.path.join(config_dir, "fabric_ids.json")

# Fallback to old structure if config dir doesn't exist
if not os.path.exists(config_dir):
    config_dir = data_dir
    tables_dir = data_dir
    config_path = os.path.join(data_dir, "ontology_config.json")
    fabric_ids_path = os.path.join(data_dir, "fabric_ids.json")

if not os.path.exists(config_path):
    print(f"ERROR: ontology_config.json not found")
    print("       Run 01_generate_sample_data.py first")
    sys.exit(1)

if not os.path.exists(fabric_ids_path):
    print(f"ERROR: fabric_ids.json not found")
    print("       Run 02_create_fabric_items.py first")
    sys.exit(1)

with open(config_path) as f:
    ontology_config = json.load(f)

with open(fabric_ids_path) as f:
    fabric_ids = json.load(f)

# Get workspace_id from environment (not config file for security)
WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID")
if not WORKSPACE_ID:
    print("ERROR: FABRIC_WORKSPACE_ID not set in .env")
    sys.exit(1)

LAKEHOUSE_ID = fabric_ids["lakehouse_id"]
LAKEHOUSE_NAME = fabric_ids["lakehouse_name"]
FABRIC_API = "https://api.fabric.microsoft.com/v1"
ONELAKE_URL = "onelake.dfs.fabric.microsoft.com"

print(f"\n{'='*60}")
print("Loading Data to Fabric Lakehouse")
print(f"{'='*60}")
print(f"Data folder: {data_dir}")
print(f"Workspace: {WORKSPACE_ID}")
print(f"Lakehouse: {LAKEHOUSE_NAME}")
print(f"Tables: {', '.join(ontology_config['tables'].keys())}")

# ============================================================================
# Authentication
# ============================================================================

credential = AzureCliCredential()

def get_headers(max_retries=3, retry_delay=5):
    """Get fresh headers with Fabric API token. Retries with exponential backoff on failure."""
    credential = AzureCliCredential()
    for attempt in range(1, max_retries + 1):
        try:
            token = credential.get_token("https://api.fabric.microsoft.com/.default").token
            return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        except Exception as e:
            if attempt < max_retries:
                wait = retry_delay * (2 ** (attempt - 1))
                print(f"  [RETRY] Token acquisition attempt {attempt}/{max_retries} failed: {e}")
                print(f"  Retrying in {wait} seconds...")
                time.sleep(wait)
            else:
                print(f"  [FAIL] Token acquisition failed after {max_retries} attempts: {e}")
                raise
    raise RuntimeError("Failed to acquire Fabric API token and construct headers.")

def make_request(method, url, **kwargs):
    """Make request with retry logic for 429 rate limiting"""
    max_retries = 5
    for attempt in range(max_retries):
        response = requests.request(method, url, headers=get_headers(), **kwargs)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 30))
            print(f"    Rate limited. Waiting {retry_after}s...")
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
                print(f"    [OK] {operation_name} completed")
                return result
            elif status in ["Failed", "failed"]:
                print(f"    [FAIL] {operation_name} failed: {result}")
                return None
        time.sleep(3)
    print(f"    [FAIL] {operation_name} timed out")
    return None

def b64encode(content):
    """Encode content to base64"""
    if isinstance(content, dict):
        content = json.dumps(content)
    if isinstance(content, str):
        content = content.encode("utf-8")
    return base64.b64encode(content).decode("utf-8")

# ============================================================================
# Step 1: Get Workspace Name (needed for OneLake path)
# ============================================================================

print(f"\n[1/3] Getting workspace info...")
resp = make_request("GET", f"{FABRIC_API}/workspaces/{WORKSPACE_ID}")
if resp.status_code != 200:
    print(f"  [FAIL] Failed to get workspace info: {resp.text}")
    sys.exit(1)
workspace_name = resp.json()["displayName"]
print(f"  Workspace name: {workspace_name}")

# ============================================================================
# Step 2: Upload CSV Files
# ============================================================================

print(f"\n[2/3] Uploading CSV files to Lakehouse...")

# Setup OneLake connection (use workspace NAME, not ID)
account_url = f"https://{ONELAKE_URL}"
service_client = DataLakeServiceClient(account_url, credential=credential)
file_system_client = service_client.get_file_system_client(workspace_name)

# Get directory client for Lakehouse Files folder
data_path = f"{LAKEHOUSE_NAME}.Lakehouse/Files"
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

# Wait for files to be available in OneLake
print("  Waiting for files to be available...")
time.sleep(10)

# ============================================================================
# Step 3: Load CSV Files as Delta Tables
# ============================================================================

if args.skip_tables:
    print(f"\n[3/3] Skipping table load (--skip-tables flag)")
else:
    print(f"\n[3/3] Loading CSV files as Delta tables via Fabric Notebook...")

    # --- Build PySpark notebook code to load all CSVs as Delta tables ---
    table_names = list(ontology_config["tables"].keys())
    spark_code_lines = [
        "import os",
        "",
        f"lakehouse_name = '{LAKEHOUSE_NAME}'",
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

    notebook_name = f"load_tables_{LAKEHOUSE_NAME}"

    # Build notebook payload with Fabric notebook definition format
    notebook_metadata = {
        "language_info": {"name": "python"},
        "trident": {
            "lakehouse": {
                "default_lakehouse": LAKEHOUSE_ID,
                "default_lakehouse_name": LAKEHOUSE_NAME,
                "default_lakehouse_workspace_id": WORKSPACE_ID,
                "known_lakehouses": [
                    {
                        "id": LAKEHOUSE_ID
                    }
                ]
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
                time.sleep(10)  # Wait for deletion to propagate
                break

    # Create the notebook
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
    resp = make_request("POST", create_url, json=create_nb_payload)

    if resp.status_code == 201:
        notebook_id = resp.json()["id"]
        print(f"  [OK] Created notebook: {notebook_name} ({notebook_id})")
    elif resp.status_code == 202:
        operation_url = resp.headers.get("Location")
        result = wait_for_lro(operation_url, "Notebook creation")
        # Find the notebook to get its ID
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

    # Run the notebook
    print(f"  Running notebook to load tables...")
    run_url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/items/{notebook_id}/jobs/instances?jobType=RunNotebook"
    run_resp = make_request("POST", run_url)

    if run_resp.status_code in [200, 202]:
        operation_url = run_resp.headers.get("Location")
        if operation_url:
            result = wait_for_lro(operation_url, "Notebook execution", timeout=600)
            if result is None:
                print(f"  [FAIL] Notebook execution failed or timed out")
                sys.exit(1)
        else:
            # No Location header, wait and check
            print("  Waiting for notebook execution...")
            time.sleep(60)
        print(f"  [OK] Notebook execution completed - all tables loaded")
    else:
        print(f"  [FAIL] Failed to run notebook: {run_resp.status_code} {run_resp.text}")
        sys.exit(1)

    # Wait for tables to be indexed
    print("  Waiting for tables to be indexed...")
    time.sleep(30)

    # --- Original Step 3 code (replaced by notebook approach above) ---
    # tables_url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/lakehouses/{LAKEHOUSE_ID}/tables"
    #
    # for table_name in ontology_config["tables"].keys():
    #     csv_file = f"{table_name}.csv"
    #     print(f"  Loading {csv_file} as table '{table_name}'...")
    #
    #     load_table_url = f"{tables_url}/{table_name}/load"
    #     load_payload = {
    #         "relativePath": f"Files/{csv_file}",
    #         "pathType": "File",
    #         "mode": "Overwrite",
    #         "formatOptions": {
    #             "format": "Csv",
    #             "header": True,
    #             "delimiter": ","
    #         }
    #     }
    #
    #     resp = make_request("POST", load_table_url, json=load_payload)
    #
    #     if resp.status_code == 200:
    #         print(f"  [OK] Table '{table_name}' loaded successfully")
    #     elif resp.status_code == 202:
    #         operation_url = resp.headers.get("Location")
    #         wait_for_lro(operation_url, f"Table '{table_name}' loading")
    #     else:
    #         print(f"  Table loading returned status: {resp.status_code}")
    #         print(f"    Response: {resp.text}")
    #
    #     # Wait for tables to be indexed
    #     print("  Waiting for tables to be indexed...")
    #     time.sleep(30)

# ============================================================================
# Step 4: Trigger Ontology Materialization
# ============================================================================
# The ontology was created in script 02 before tables existed, so Fabric
# couldn't validate the data bindings. Now that data is loaded, we call
# updateDefinition to trigger Fabric to re-process and materialize.

ONTOLOGY_ID = fabric_ids.get("ontology_id")
ontology_def_path = os.path.join(config_dir, "ontology_definition_parts.json")

if ONTOLOGY_ID and os.path.exists(ontology_def_path):
    print(f"\n[4/4] Publishing ontology (triggering materialization)...")

    with open(ontology_def_path) as f:
        definition_parts = json.load(f)

    update_url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/ontologies/{ONTOLOGY_ID}/updateDefinition"
    update_payload = {
        "definition": {
            "parts": definition_parts
        }
    }
    update_resp = make_request("POST", update_url, json=update_payload)

    if update_resp.status_code == 200:
        print(f"  [OK] Ontology materialization triggered")
    elif update_resp.status_code == 202:
        operation_url = update_resp.headers.get("Location")
        if operation_url:
            wait_for_lro(operation_url, "Ontology materialization")
        else:
            print("  Waiting for ontology to process...")
            time.sleep(30)
        print(f"  [OK] Ontology materialization triggered (async)")
    else:
        print(f"  [WARN] updateDefinition returned {update_resp.status_code}: {update_resp.text}")
        print(f"  You may need to open the ontology in Fabric portal, edit any entity, and save.")
else:
    if not ONTOLOGY_ID:
        print(f"\n[4/4] Skipping ontology publish (no ontology_id in fabric_ids.json)")
    else:
        print(f"\n[4/4] Skipping ontology publish (no saved definition parts found)")
        print(f"  You may need to open the ontology in Fabric portal, edit any entity, and save.")

# ============================================================================
# Summary
# ============================================================================

print(f"\n{'='*60}")
print("Data Load Complete!")
print(f"{'='*60}")
print(f"""
Uploaded {len(uploaded_files)} files: {', '.join(uploaded_files)}
Tables loaded: {', '.join(ontology_config['tables'].keys())}

Next step - Generate schema prompt:
  python scripts/04_generate_agent_prompt.py
""")
