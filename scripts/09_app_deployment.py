"""
09 - App Deployment Configuration
Assigns roles and permissions required for the deployed application.

Usage:
    python 09_app_deployment.py

Prerequisites:
    - Azure resources deployed (azd up)
    - For Fabric mode: Fabric workspace created (02_create_fabric_items.py)
    - For Azure SQL mode: SQL database populated (05_upload_to_sql.py)

What this script does:
    - Fabric mode (AZURE_ENV_ONLY=false):
        1. Assigns Fabric workspace Contributor role to backend service principal
        2. Gets Fabric SQL endpoint and updates App Service settings
    - Azure SQL mode (AZURE_ENV_ONLY=true):
        1. Assigns Azure SQL db_datareader/db_datawriter roles to API managed identity
    - Common (always runs):
        1. Assigns Cosmos DB Data Contributor role to current user
        2. Updates App Service with agent names (AGENT_NAME_CHAT, AGENT_NAME_TITLE)
"""

import json
import os
import struct
import sys
import time

# Add scripts directory to path for load_env
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from load_env import load_all_env
load_all_env()

from azure.identity import DefaultAzureCredential
import requests

# ============================================================================
# Configuration
# ============================================================================

azure_only = os.getenv("AZURE_ENV_ONLY", "false").lower() in ("true", "1", "yes")

print(f"\n{'='*60}")
print("App Deployment Configuration")
print(f"  Mode: {'Azure SQL' if azure_only else 'Fabric'}")
print(f"{'='*60}")

credential = DefaultAzureCredential()


# ============================================================================
# Helper functions
# ============================================================================

def get_fabric_headers():
    """Get fresh headers with Fabric API token."""
    token = credential.get_token("https://api.fabric.microsoft.com/.default").token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def fabric_request(method, url, **kwargs):
    """Make Fabric API request with retry logic for 429 rate limiting."""
    max_retries = 5
    for attempt in range(max_retries):
        response = requests.request(method, url, headers=get_fabric_headers(), **kwargs)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 30))
            print(f"  Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        return response
    return response


def assign_fabric_roles():
    """Assign Fabric workspace Contributor role to the backend service principal."""
    FABRIC_API = "https://api.fabric.microsoft.com/v1"
    WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID")
    BACKEND_APP_PID = os.getenv("API_PID") or os.getenv("BACKEND_APP_PID")

    print("\n[1/2] Assigning Fabric workspace role to backend app...")

    if not WORKSPACE_ID:
        print("  [SKIP] FABRIC_WORKSPACE_ID not set")
        return
    if not BACKEND_APP_PID:
        print("  [SKIP] API_PID / BACKEND_APP_PID not set")
        print("         Set API_PID in .env to enable automatic role assignment")
        return

    fabric_ra_url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/roleAssignments"
    roleassignment_json = {
        "principal": {
            "id": BACKEND_APP_PID,
            "type": "ServicePrincipal"
        },
        "role": "Contributor"
    }
    roleassignment_res = fabric_request("POST", fabric_ra_url, json=roleassignment_json)

    if roleassignment_res.status_code == 201:
        print("  [OK] Role assignment created successfully")
    elif roleassignment_res.status_code == 409:
        print("  [OK] Role assignment already exists")
    else:
        print(f"  [WARN] Failed to create role assignment. Status: {roleassignment_res.status_code}")
        print(f"         Response: {roleassignment_res.text}")


def update_fabric_app_settings():
    """Get Fabric SQL endpoint and update App Service settings."""
    FABRIC_API = "https://api.fabric.microsoft.com/v1"
    WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID")
    LAKEHOUSE_ID = os.getenv("FABRIC_LAKEHOUSE_ID")
    LAKEHOUSE_NAME = os.getenv("FABRIC_LAKEHOUSE_NAME")
    api_uid = os.getenv("API_UID")

    print("\n[2/2] Getting Fabric SQL endpoint and updating App Service...")

    if not WORKSPACE_ID or not LAKEHOUSE_ID:
        # Try loading from fabric_ids.json
        from load_env import get_data_folder
        try:
            data_dir = get_data_folder()
            config_dir = os.path.join(data_dir, "config")
            fabric_ids_path = os.path.join(config_dir, "fabric_ids.json")
            if not os.path.exists(fabric_ids_path):
                fabric_ids_path = os.path.join(data_dir, "fabric_ids.json")
            if os.path.exists(fabric_ids_path):
                import json
                with open(fabric_ids_path) as f:
                    fabric_ids = json.load(f)
                LAKEHOUSE_ID = LAKEHOUSE_ID or fabric_ids.get("lakehouse_id")
                LAKEHOUSE_NAME = LAKEHOUSE_NAME or fabric_ids.get("lakehouse_name")
        except Exception:
            pass

    if not WORKSPACE_ID:
        print("  [SKIP] FABRIC_WORKSPACE_ID not set")
        return
    if not LAKEHOUSE_ID:
        print("  [SKIP] FABRIC_LAKEHOUSE_ID not set and fabric_ids.json not found")
        return

    # Get SQL analytics endpoint
    fabric_sql_endpoint = None
    try:
        url = f"{FABRIC_API}/workspaces/{WORKSPACE_ID}/lakehouses/{LAKEHOUSE_ID}"
        resp = fabric_request("GET", url)
        if resp.status_code == 200:
            data = resp.json()
            props = data.get("properties", {})
            sql_props = props.get("sqlEndpointProperties", {})
            fabric_sql_endpoint = sql_props.get("connectionString")
    except Exception as e:
        print(f"  [WARN] Could not get Fabric SQL endpoint: {e}")

    if fabric_sql_endpoint:
        print(f"  [OK] SQL Endpoint: {fabric_sql_endpoint}")

        # Save to fabric_ids.json
        try:
            from load_env import get_data_folder
            import json
            data_dir = get_data_folder()
            config_dir = os.path.join(data_dir, "config")
            fabric_ids_path = os.path.join(config_dir, "fabric_ids.json")
            if not os.path.exists(fabric_ids_path):
                fabric_ids_path = os.path.join(data_dir, "fabric_ids.json")
            if os.path.exists(fabric_ids_path):
                with open(fabric_ids_path) as f:
                    fabric_ids = json.load(f)
                fabric_ids["sql_endpoint"] = fabric_sql_endpoint
                with open(fabric_ids_path, "w") as f:
                    json.dump(fabric_ids, f, indent=2)
        except Exception:
            pass
    else:
        print("  [WARN] SQL Endpoint not available yet")

    # Update App Service env vars
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    resource_group = os.getenv("RESOURCE_GROUP_NAME")
    app_name = os.getenv("API_APP_NAME")

    if subscription_id and resource_group and app_name:
        try:
            from azure.mgmt.web import WebSiteManagementClient

            web_client = WebSiteManagementClient(credential, subscription_id)

            current = web_client.web_apps.list_application_settings(resource_group, app_name)
            props = dict(current.properties or {})

            # Build full ODBC connection string
            if fabric_sql_endpoint:
                fabric_conn_string = (
                    f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                    f"SERVER={fabric_sql_endpoint};"
                    f"DATABASE={LAKEHOUSE_NAME};"
                    f"Encrypt=yes;TrustServerCertificate=no;"
                    f"UID={api_uid};"
                    f"Authentication=ActiveDirectoryMSI"
                )
            else:
                fabric_conn_string = ""

            new_settings = {
                "FABRIC_SQL_CONNECTION_STRING": fabric_conn_string
            }
            props.update(new_settings)

            web_client.web_apps.update_application_settings(
                resource_group,
                app_name,
                {"properties": props}
            )

            print("  [OK] App Service settings updated")
        except Exception as e:
            print(f"  [WARN] Failed to update App Service: {e}")
    else:
        if fabric_sql_endpoint:
            fabric_conn_string = (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={fabric_sql_endpoint};"
                f"DATABASE={LAKEHOUSE_NAME};"
                f"Encrypt=yes;TrustServerCertificate=no;"
                f"UID={api_uid};"
                f"Authentication=ActiveDirectoryMSI"
            )
            print(f"  NOTE: Set FABRIC_SQL_CONNECTION_STRING={fabric_conn_string} in App Service")
        else:
            print("  [SKIP] No App Service config to update (missing AZURE_SUBSCRIPTION_ID, RESOURCE_GROUP_NAME, or API_APP_NAME)")


def assign_sql_roles():
    """Assign Azure SQL db_datareader/db_datawriter roles to the API managed identity."""
    sql_server = os.getenv("SQLDB_SERVER")
    sql_database = os.getenv("SQLDB_DATABASE")
    api_mid_name = os.getenv("MID_DISPLAY_NAME")

    print("\n[1/2] Assigning Azure SQL roles to API managed identity...")

    if not sql_server or not sql_database:
        print("  [SKIP] SQLDB_SERVER or SQLDB_DATABASE not set")
        return
    if not api_mid_name:
        print("  [SKIP] MID_DISPLAY_NAME not set")
        print("         Set MID_DISPLAY_NAME in azd environment to enable")
        return

    try:
        import pyodbc
    except ImportError:
        print("  [WARN] pyodbc not installed. Run: pip install pyodbc")
        return

    try:
        # Connect to Azure SQL
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

        conn = None
        try:
            connection_string = f"DRIVER={{{driver18}}};SERVER={sql_server};DATABASE={sql_database};"
            conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
            print(f"  Connected using {driver18}")
        except Exception:
            connection_string = f"DRIVER={{{driver17}}};SERVER={sql_server};DATABASE={sql_database};"
            conn = pyodbc.connect(connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
            print(f"  Connected using {driver17}")

        cursor = conn.cursor()

        # Check if user already exists
        check_user_sql = f"SELECT COUNT(*) FROM sys.database_principals WHERE name = N'{api_mid_name}'"
        cursor.execute(check_user_sql)
        user_exists = cursor.fetchone()[0] > 0

        if not user_exists:
            create_user_sql = f"CREATE USER [{api_mid_name}] FROM EXTERNAL PROVIDER"
            try:
                cursor.execute(create_user_sql)
                conn.commit()
                print(f"  [OK] Created user: {api_mid_name}")
            except Exception as e:
                print(f"  [FAIL] Failed to create user {api_mid_name}: {e}")
                cursor.close()
                conn.close()
                sys.exit(1)
        else:
            print(f"  [OK] User already exists: {api_mid_name}")

        # Assign roles
        for role in ['db_datareader', 'db_datawriter']:
            check_role_sql = f"""
                SELECT COUNT(*)
                FROM sys.database_role_members rm
                JOIN sys.database_principals rp ON rm.role_principal_id = rp.principal_id
                JOIN sys.database_principals mp ON rm.member_principal_id = mp.principal_id
                WHERE mp.name = N'{api_mid_name}' AND rp.name = N'{role}'
            """
            cursor.execute(check_role_sql)
            has_role = cursor.fetchone()[0] > 0

            if not has_role:
                add_role_sql = f"ALTER ROLE [{role}] ADD MEMBER [{api_mid_name}]"
                try:
                    cursor.execute(add_role_sql)
                    conn.commit()
                    print(f"  [OK] Assigned {role} to {api_mid_name}")
                except Exception as e:
                    print(f"  [FAIL] Failed to assign {role}: {e}")
            else:
                print(f"  [OK] {api_mid_name} already has {role}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"  [FAIL] SQL role assignment failed: {e}")


def restart_app_service():
    """Update App Service with a dummy setting to trigger a restart."""
    from datetime import datetime, timezone

    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    resource_group = os.getenv("RESOURCE_GROUP_NAME")
    app_name = os.getenv("API_APP_NAME")

    print("\n[2/2] Restarting App Service to apply new permissions...")

    if not subscription_id or not resource_group or not app_name:
        print("  [SKIP] Missing AZURE_SUBSCRIPTION_ID, RESOURCE_GROUP_NAME, or API_APP_NAME")
        return

    try:
        from azure.mgmt.web import WebSiteManagementClient

        web_client = WebSiteManagementClient(credential, subscription_id)

        current = web_client.web_apps.list_application_settings(resource_group, app_name)
        props = dict(current.properties or {})

        # Set a dummy value with timestamp to force App Service restart
        props["LAST_DEPLOYMENT_TIMESTAMP"] = datetime.now(timezone.utc).isoformat()

        web_client.web_apps.update_application_settings(
            resource_group,
            app_name,
            {"properties": props}
        )

        print("  [OK] App Service settings updated - restart triggered")
    except Exception as e:
        print(f"  [WARN] Failed to restart App Service: {e}")


# ============================================================================
# Assign Cosmos DB Role (always runs)
# ============================================================================

def assign_cosmos_role():
    """Assign Cosmos DB Built-in Data Contributor role to the current user."""
    import uuid as _uuid
    import base64 as _base64

    cosmosdb_account = os.getenv("AZURE_COSMOSDB_ACCOUNT")
    resource_group = os.getenv("AZURE_RESOURCE_GROUP") or os.getenv("RESOURCE_GROUP_NAME")
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")

    if not cosmosdb_account:
        print("\n[SKIP] Cosmos DB role assignment - AZURE_COSMOSDB_ACCOUNT not set")
        return

    if not resource_group or not subscription_id:
        print("\n[SKIP] Cosmos DB role assignment - missing AZURE_RESOURCE_GROUP or AZURE_SUBSCRIPTION_ID")
        return

    print(f"\n{'='*60}")
    print("Assigning Cosmos DB Data Contributor Role")
    print(f"{'='*60}")
    print(f"  Account: {cosmosdb_account}")

    try:
        from azure.mgmt.cosmosdb import CosmosDBManagementClient
        from azure.mgmt.cosmosdb.models import SqlRoleAssignmentCreateUpdateParameters

        # Get the current user's object ID from the credential's token
        token = credential.get_token("https://management.azure.com/.default")
        payload = token.token.split(".")[1]
        payload += "=" * (-len(payload) % 4)  # pad base64
        token_claims = json.loads(_base64.b64decode(payload))
        user_object_id = token_claims.get("oid")

        if not user_object_id:
            print("  [WARN] Could not determine user object ID from token")
            return

        # Cosmos DB Built-in Data Contributor role definition ID
        data_contributor_role_id = "00000000-0000-0000-0000-000000000002"
        full_role_def_id = (
            f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.DocumentDB/databaseAccounts/{cosmosdb_account}"
            f"/sqlRoleDefinitions/{data_contributor_role_id}"
        )
        account_scope = (
            f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.DocumentDB/databaseAccounts/{cosmosdb_account}"
        )
        # Use a deterministic GUID so re-runs detect the existing assignment
        assignment_id = str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"{cosmosdb_account}-{user_object_id}"))

        mgmt_client = CosmosDBManagementClient(credential, subscription_id)

        # Check if role assignment already exists before creating
        try:
            existing = mgmt_client.sql_resources.get_sql_role_assignment(
                role_assignment_id=assignment_id,
                resource_group_name=resource_group,
                account_name=cosmosdb_account,
            )
            if existing:
                print(f"  [OK] Cosmos DB Data Contributor role already assigned - skipping")
        except Exception:
            # Role doesn't exist yet, create it
            role_params = SqlRoleAssignmentCreateUpdateParameters(
                role_definition_id=full_role_def_id,
                scope=account_scope,
                principal_id=user_object_id,
            )
            mgmt_client.sql_resources.begin_create_update_sql_role_assignment(
                role_assignment_id=assignment_id,
                resource_group_name=resource_group,
                account_name=cosmosdb_account,
                create_update_sql_role_assignment_parameters=role_params,
            ).result(timeout=120)
            print(f"  [OK] Cosmos DB Data Contributor role assigned to current user ({user_object_id})")

    except ImportError:
        print("  [WARN] azure-mgmt-cosmosdb not installed. Run: pip install azure-mgmt-cosmosdb")
    except Exception as e:
        print(f"  [WARN] Cosmos DB role assignment failed: {e}")
        print(f"         This is non-critical - continuing...")


# ============================================================================
# Update Agent App Settings (always runs)
# ============================================================================

def update_agent_app_settings():
    """Update App Service with agent names from agent_ids.json."""
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    resource_group = os.getenv("RESOURCE_GROUP_NAME")
    app_name = os.getenv("API_APP_NAME")

    if not subscription_id or not resource_group or not app_name:
        print("\n[SKIP] Agent App Settings update - missing AZURE_SUBSCRIPTION_ID, RESOURCE_GROUP_NAME, or API_APP_NAME")
        return

    # Load agent names from agent_ids.json
    try:
        from load_env import get_data_folder
        data_dir = get_data_folder()
        config_dir = os.path.join(data_dir, "config")
        agent_ids_path = os.path.join(config_dir, "agent_ids.json")

        if not os.path.exists(agent_ids_path):
            print(f"\n[SKIP] Agent App Settings update - {agent_ids_path} not found")
            print("       Run 07_create_agent.py first.")
            return

        with open(agent_ids_path) as f:
            agent_ids = json.load(f)

        chat_agent_name = agent_ids.get("chat_agent_name")
        title_agent_name = agent_ids.get("title_agent_name")

        if not chat_agent_name:
            print("\n[SKIP] Agent App Settings update - chat_agent_name not found in agent_ids.json")
            return

    except Exception as e:
        print(f"\n[WARN] Failed to load agent_ids.json: {e}")
        return

    print(f"\n{'='*60}")
    print("Updating App Service Agent Settings")
    print(f"{'='*60}")
    print(f"  App Service: {app_name}")

    try:
        from azure.mgmt.web import WebSiteManagementClient

        web_client = WebSiteManagementClient(credential, subscription_id)

        # Get current settings
        current = web_client.web_apps.list_application_settings(resource_group, app_name)
        props = dict(current.properties or {})

        # Agent name settings
        new_settings = {"AGENT_NAME_CHAT": chat_agent_name}
        if title_agent_name:
            new_settings["AGENT_NAME_TITLE"] = title_agent_name

        props.update(new_settings)

        web_client.web_apps.update_application_settings(
            resource_group,
            app_name,
            {"properties": props}
        )

        print(f"\n  Settings updated:")
        for key, value in new_settings.items():
            print(f"    {key}: {value}")

        print(f"\n  [OK] App Service agent settings updated successfully!")

    except Exception as e:
        print(f"\n  [WARN] Failed to update App Service agent settings: {e}")
        print("         You may need to set AGENT_NAME_CHAT and AGENT_NAME_TITLE manually.")


# ============================================================================
# Main
# ============================================================================

if not azure_only:
    # Fabric mode: assign workspace role and update App Service settings
    assign_fabric_roles()
    update_fabric_app_settings()
else:
    # Azure SQL mode: assign SQL roles to API managed identity, then restart app
    assign_sql_roles()

# Always assign Cosmos DB role and update agent names in App Service
assign_cosmos_role()
update_agent_app_settings()

# ============================================================================
# Summary
# ============================================================================

print(f"\n{'='*60}")
print("App Deployment Configuration Complete!")
print(f"{'='*60}")
