"""
Generate .env file from existing Azure resources.

Use this script when infrastructure is already provisioned (e.g., by an admin)
and you need to create the .env file without running 'azd up'.

The script will:
1. First try to fetch app settings from the API App Service (fastest/most accurate)
2. Fall back to querying individual Azure resources if no App Service found

Usage:
    python scripts/generate_env_from_azure.py --resource-group <rg-name>
    python scripts/generate_env_from_azure.py -g <rg-name> --app-name <api-app-name>
    python scripts/generate_env_from_azure.py -g <rg-name> --no-app-service
    
Example:
    python scripts/generate_env_from_azure.py --resource-group rg-myproject-dev
    python scripts/generate_env_from_azure.py -g rg-myproject-dev --app-name myproject-api
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def get_az_command() -> str:
    """Get the Azure CLI command, handling Windows .cmd extension."""
    # Try 'az' first
    az_path = shutil.which("az")
    if az_path:
        return az_path
    # On Windows, also try 'az.cmd'
    if sys.platform == "win32":
        az_cmd_path = shutil.which("az.cmd")
        if az_cmd_path:
            return az_cmd_path
    return "az"  # Fall back to 'az' and let it fail with a clear error


def run_az_command(args: list[str]) -> dict | list | str | None:
    """Run an Azure CLI command and return the JSON result."""
    az_cmd = get_az_command()
    try:
        result = subprocess.run(
            [az_cmd] + args + ["--output", "json"],
            capture_output=True,
            text=True,
            check=True,
            shell=(sys.platform == "win32")  # Use shell on Windows for .cmd files
        )
        if result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except FileNotFoundError:
        print("Error: Azure CLI (az) not found. Please install it or ensure it's in PATH.", file=sys.stderr)
        print("Install: https://docs.microsoft.com/cli/azure/install-azure-cli", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running az {' '.join(args)}: {e.stderr}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        return result.stdout.strip() if result.stdout else None


def get_resources_by_type(resource_group: str, resource_type: str) -> list:
    """Get all resources of a specific type in the resource group."""
    result = run_az_command([
        "resource", "list",
        "--resource-group", resource_group,
        "--resource-type", resource_type
    ])
    return result if isinstance(result, list) else []


def get_ai_search_endpoint(resource_group: str) -> tuple[str, str]:
    """Get Azure AI Search endpoint and name."""
    resources = get_resources_by_type(resource_group, "Microsoft.Search/searchServices")
    if resources:
        name = resources[0]["name"]
        # Get the endpoint from the resource properties
        details = run_az_command([
            "search", "service", "show",
            "--name", name,
            "--resource-group", resource_group
        ])
        if details:
            # Search endpoint is https://<name>.search.windows.net
            endpoint = f"https://{name}.search.windows.net"
            return endpoint, name
    return "", ""


def get_openai_endpoint(resource_group: str) -> tuple[str, str, str]:
    """Get Azure OpenAI / AI Services endpoint and model names."""
    # Try AI Services first (newer unified service)
    resources = get_resources_by_type(resource_group, "Microsoft.CognitiveServices/accounts")
    
    for resource in resources:
        name = resource["name"]
        details = run_az_command([
            "cognitiveservices", "account", "show",
            "--name", name,
            "--resource-group", resource_group
        ])
        if details and details.get("kind") in ["AIServices", "OpenAI"]:
            endpoint = details.get("properties", {}).get("endpoint", "")
            
            # Get deployments to find model names
            deployments = run_az_command([
                "cognitiveservices", "account", "deployment", "list",
                "--name", name,
                "--resource-group", resource_group
            ]) or []
            
            chat_model = ""
            embedding_model = ""
            
            for dep in deployments:
                model_name = dep.get("properties", {}).get("model", {}).get("name", "")
                dep_name = dep.get("name", "")
                if "gpt" in model_name.lower():
                    chat_model = dep_name
                elif "embedding" in model_name.lower():
                    embedding_model = dep_name
            
            return endpoint, chat_model, embedding_model
    
    return "", "", ""


def get_ai_foundry_project(resource_group: str) -> tuple[str, str]:
    """Get Azure AI Foundry project endpoint."""
    # AI Foundry projects are Machine Learning workspaces of kind 'Project'
    resources = get_resources_by_type(resource_group, "Microsoft.MachineLearningServices/workspaces")
    
    for resource in resources:
        name = resource["name"]
        details = run_az_command([
            "ml", "workspace", "show",
            "--name", name,
            "--resource-group", resource_group
        ])
        if details:
            # Check if it's a project (has hub_resource_id) or a hub
            if details.get("kind", "").lower() == "project" or "hub_resource_id" in details:
                # Project endpoint format: https://<region>.api.azureml.ms/projects/<project-id>
                discovery_url = details.get("discovery_url", "")
                workspace_id = details.get("id", "")
                
                # Construct the endpoint
                if discovery_url and workspace_id:
                    # Parse location from discovery_url or workspace_id
                    location = details.get("location", "")
                    
                    # AI Foundry endpoint format
                    endpoint = f"https://{name}.{location}.api.azureml.ms"
                    return endpoint, name
    
    return "", ""


def get_cosmos_db_account(resource_group: str) -> str:
    """Get CosmosDB account name."""
    resources = get_resources_by_type(resource_group, "Microsoft.DocumentDB/databaseAccounts")
    if resources:
        return resources[0]["name"]
    return ""


def get_sql_server(resource_group: str) -> tuple[str, str]:
    """Get SQL Server name and database name."""
    servers = get_resources_by_type(resource_group, "Microsoft.Sql/servers")
    if servers:
        server_name = servers[0]["name"]
        # Get databases on this server
        databases = run_az_command([
            "sql", "db", "list",
            "--server", server_name,
            "--resource-group", resource_group
        ]) or []
        
        # Filter out system databases
        user_dbs = [db["name"] for db in databases if db["name"] not in ["master"]]
        db_name = user_dbs[0] if user_dbs else ""
        
        return server_name, db_name
    return "", ""


def get_managed_identity(resource_group: str) -> tuple[str, str, str]:
    """Get managed identity details."""
    resources = get_resources_by_type(resource_group, "Microsoft.ManagedIdentity/userAssignedIdentities")
    
    for resource in resources:
        name = resource["name"]
        # Look for backend-related identity
        if "backend" in name.lower() or "api" in name.lower():
            details = run_az_command([
                "identity", "show",
                "--name", name,
                "--resource-group", resource_group
            ])
            if details:
                client_id = details.get("clientId", "")
                principal_id = details.get("principalId", "")
                return name, client_id, principal_id
    
    # Fall back to first identity
    if resources:
        name = resources[0]["name"]
        details = run_az_command([
            "identity", "show",
            "--name", name,
            "--resource-group", resource_group
        ])
        if details:
            return name, details.get("clientId", ""), details.get("principalId", "")
    
    return "", "", ""


def get_principal_id_from_client_id(client_id: str) -> str:
    """Get the principal ID (object ID) from a client ID using Azure AD."""
    if not client_id:
        return ""
    
    result = run_az_command([
        "ad", "sp", "show",
        "--id", client_id,
        "--query", "id",
        "-o", "tsv"
    ])
    
    # Result comes back as string when using -o tsv
    if isinstance(result, str):
        return result.strip()
    return ""


def get_app_service(resource_group: str, name_contains: str) -> tuple[str, str]:
    """Get App Service URL and name."""
    resources = get_resources_by_type(resource_group, "Microsoft.Web/sites")
    
    for resource in resources:
        name = resource["name"]
        if name_contains.lower() in name.lower():
            details = run_az_command([
                "webapp", "show",
                "--name", name,
                "--resource-group", resource_group
            ])
            if details:
                hostname = details.get("defaultHostName", "")
                if hostname:
                    return f"https://{hostname}", name
    return "", ""


def get_app_service_settings(resource_group: str, app_name: str) -> dict[str, str]:
    """Get all application settings from an App Service."""
    result = run_az_command([
        "webapp", "config", "appsettings", "list",
        "--name", app_name,
        "--resource-group", resource_group
    ])
    
    if isinstance(result, list):
        # Convert list of {name, value} dicts to a simple dict
        return {item["name"]: item.get("value", "") for item in result}
    return {}


def find_api_app_service(resource_group: str) -> tuple[str, str]:
    """Find the API App Service in the resource group."""
    resources = get_resources_by_type(resource_group, "Microsoft.Web/sites")
    
    # Look for API app service (contains 'api' or 'backend' in name)
    for resource in resources:
        name = resource["name"]
        if "api" in name.lower() or "backend" in name.lower():
            details = run_az_command([
                "webapp", "show",
                "--name", name,
                "--resource-group", resource_group
            ])
            if details:
                hostname = details.get("defaultHostName", "")
                return name, f"https://{hostname}" if hostname else ""
    
    return "", ""


def generate_env_from_app_service(resource_group: str, app_name: str) -> str | None:
    """Generate .env content from App Service application settings."""
    print(f"Fetching application settings from App Service: {app_name}")
    
    settings = get_app_service_settings(resource_group, app_name)
    if not settings:
        print("  No application settings found")
        return None
    
    print(f"  Found {len(settings)} application settings")
    
    # Get subscription ID from current account
    account = run_az_command(["account", "show"])
    subscription_id = account.get("id", "") if account else ""
    
    # Map of important env vars to include
    important_vars = [
        # Solution
        "SOLUTION_NAME", "RESOURCE_GROUP_NAME",
        # Subscription
        "AZURE_SUBSCRIPTION_ID",
        # Azure AI Services
        "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT_MODEL", "AZURE_CHAT_MODEL",
        "AZURE_OPENAI_EMBEDDING_MODEL", "AZURE_EMBEDDING_MODEL",
        # AI Foundry
        "AZURE_AI_AGENT_ENDPOINT", "AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME",
        # AI Search
        "AZURE_AI_SEARCH_ENDPOINT", "AZURE_AI_SEARCH_NAME", "AZURE_AI_SEARCH_INDEX",
        "AZURE_AI_SEARCH_CONNECTION_NAME", "AZURE_AI_SEARCH_CONNECTION_ID",
        # CosmosDB
        "AZURE_COSMOSDB_ACCOUNT", "AZURE_COSMOSDB_DATABASE", "AZURE_COSMOSDB_CONVERSATIONS_CONTAINER",
        # SQL
        "SQLDB_SERVER", "SQLDB_DATABASE", "SQLDB_USER_MID",
        # Managed Identity
        "API_UID", "API_PID", "MID_DISPLAY_NAME",
        # App Service
        "WEB_APP_URL", "API_APP_NAME",
        # Workshop
        "IS_WORKSHOP", "USE_CASE", "BACKEND_RUNTIME_STACK",
    ]
    
    lines = [
        "# Auto-generated from App Service application settings",
        f"# Resource Group: {resource_group}",
        f"# App Service: {app_name}",
        f"# Generated by: generate_env_from_azure.py",
        "",
        "# --- Azure Subscription & Resource Group ---",
        f"AZURE_SUBSCRIPTION_ID={subscription_id}",
        f"RESOURCE_GROUP_NAME={resource_group}",
        f"API_APP_NAME={app_name}",
        "",
        "# --- From App Service Settings ---",
    ]
    
    # Add all important vars that exist in settings
    for var in important_vars:
        if var in settings:
            lines.append(f"{var}={settings[var]}")
    
    # Derive API_PID from API_UID if not present
    if "API_UID" in settings and "API_PID" not in settings:
        api_uid = settings.get("API_UID", "")
        if api_uid:
            print(f"  Fetching API_PID from API_UID...")
            api_pid = get_principal_id_from_client_id(api_uid)
            if api_pid:
                lines.append(f"API_PID={api_pid}")
                print(f"  Found API_PID: {api_pid}")
    
    # Derive MID_DISPLAY_NAME from managed identity if not present
    if "MID_DISPLAY_NAME" not in settings:
        mid_name, _, _ = get_managed_identity(resource_group)
        if mid_name:
            lines.append(f"MID_DISPLAY_NAME={mid_name}")
            print(f"  Found MID_DISPLAY_NAME: {mid_name}")
    
    # Add any other AZURE_* or relevant vars we might have missed
    for key, value in sorted(settings.items()):
        if key not in important_vars:
            if key.startswith("AZURE_") or key.startswith("AI_") or key.startswith("SQL"):
                lines.append(f"{key}={value}")
    
    return "\n".join(lines)


def infer_solution_name(resource_group: str, resources: list) -> str:
    """Try to infer the solution name from resource naming patterns."""
    # Common pattern: rg-<solution>-<env> or <solution>-rg-<env>
    rg_parts = resource_group.lower().replace("rg-", "").replace("-rg", "").split("-")
    
    # Remove common suffixes
    for suffix in ["dev", "prod", "staging", "test", "uat"]:
        if suffix in rg_parts:
            rg_parts.remove(suffix)
    
    if rg_parts:
        return rg_parts[0]
    
    return ""


def generate_env_content(resource_group: str) -> str:
    """Generate .env file content from Azure resources."""
    print(f"Fetching resources from resource group: {resource_group}")
    
    # Get subscription ID from current account
    account = run_az_command(["account", "show"])
    subscription_id = account.get("id", "") if account else ""
    
    # Collect all resource info
    search_endpoint, search_name = get_ai_search_endpoint(resource_group)
    print(f"  Found AI Search: {search_name or 'not found'}")
    
    openai_endpoint, chat_model, embedding_model = get_openai_endpoint(resource_group)
    print(f"  Found OpenAI endpoint: {openai_endpoint or 'not found'}")
    
    project_endpoint, project_name = get_ai_foundry_project(resource_group)
    print(f"  Found AI Foundry project: {project_name or 'not found'}")
    
    cosmos_account = get_cosmos_db_account(resource_group)
    print(f"  Found CosmosDB: {cosmos_account or 'not found'}")
    
    sql_server, sql_db = get_sql_server(resource_group)
    print(f"  Found SQL Server: {sql_server or 'not found'}")
    
    mid_name, mid_client_id, mid_principal_id = get_managed_identity(resource_group)
    print(f"  Found Managed Identity: {mid_name or 'not found'}")
    
    web_app_url, _ = get_app_service(resource_group, "web")
    api_app_name, _ = get_app_service(resource_group, "api")
    print(f"  Found Web App: {web_app_url or 'not found'}")
    
    # Infer solution name
    all_resources = run_az_command(["resource", "list", "--resource-group", resource_group]) or []
    solution_name = infer_solution_name(resource_group, all_resources)
    
    # Build env content
    lines = [
        "# Auto-generated from Azure resources",
        f"# Resource Group: {resource_group}",
        f"# Generated by: generate_env_from_azure.py",
        "",
        "# --- Solution Settings ---",
        f"AZURE_SUBSCRIPTION_ID={subscription_id}",
        f"SOLUTION_NAME={solution_name}",
        f"RESOURCE_GROUP_NAME={resource_group}",
        f"API_APP_NAME={api_app_name}",
        "",
        "# --- Azure AI Services ---",
        f"AZURE_OPENAI_ENDPOINT={openai_endpoint}",
        f"AZURE_OPENAI_DEPLOYMENT_MODEL={chat_model}",
        f"AZURE_CHAT_MODEL={chat_model}",
        f"AZURE_OPENAI_EMBEDDING_MODEL={embedding_model}",
        f"AZURE_EMBEDDING_MODEL={embedding_model}",
        "",
        "# --- Azure AI Foundry ---",
        f"AZURE_AI_AGENT_ENDPOINT={project_endpoint}",
        f"AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME={chat_model}",
        "",
        "# --- Azure AI Search ---",
        f"AZURE_AI_SEARCH_ENDPOINT={search_endpoint}",
        f"AZURE_AI_SEARCH_NAME={search_name}",
        f"AZURE_AI_SEARCH_INDEX=knowledge_index",
        f"SEARCH_DATA_FOLDER=data/default/documents",
        "",
        "# --- Azure CosmosDB ---",
        f"AZURE_COSMOSDB_ACCOUNT={cosmos_account}",
        f"AZURE_COSMOSDB_DATABASE=db_conversation_history",
        f"AZURE_COSMOSDB_CONVERSATIONS_CONTAINER=conversations",
        "",
        "# --- Azure SQL ---",
        f"SQLDB_SERVER={sql_server}",
        f"SQLDB_DATABASE={sql_db}",
        f"SQLDB_USER_MID={mid_client_id}",
        "",
        "# --- Managed Identity ---",
        f"API_UID={mid_client_id}",
        f"API_PID={mid_principal_id}",
        f"MID_DISPLAY_NAME={mid_name}",
        "",
        "# --- App Service ---",
        f"WEB_APP_URL={web_app_url}",
        "",
        "# --- Workshop Settings ---",
        "IS_WORKSHOP=true",
        "USE_CASE=Network operations with outage tracking and trouble ticket management",
    ]
    
    return "\n".join(lines)


def get_default_env_content() -> str:
    """Get default env content for new .env files (Fabric settings, agent IDs, etc.)."""
    lines = [
        "",
        "# --- Fabric Settings (fill in manually) ---",
        "FABRIC_WORKSPACE_ID=",
        "DATA_FOLDER=data/default",
        "INDUSTRY=Telecommunications",
        "DATA_SIZE=large",
        "SEARCH_DATA_FOLDER=data/default/documents",
        "",
        "# --- Agent IDs (auto-populated by scripts) ---",
        "FABRIC_AGENT_ID=",
        "FOUNDRY_AGENT_ID=",
        "",
        "# --- Default value (auto-populated by scripts) ---",
        "AZURE_ENV_DEPLOY_APP=true",
    ]
    return "\n".join(lines)


def parse_env_content(content: str) -> dict[str, str]:
    """Parse .env content into a dictionary of key-value pairs."""
    env_vars = {}
    for line in content.splitlines():
        line = line.strip()
        # Skip comments and empty lines
        if not line or line.startswith("#"):
            continue
        # Parse KEY=VALUE
        if "=" in line:
            key, _, value = line.partition("=")
            env_vars[key.strip()] = value.strip()
    return env_vars


def merge_env_content(existing_content: str, new_content: str) -> str:
    """
    Merge new env values into existing content.
    - Updates existing values with new values from API
    - Preserves existing values not present in new content
    - Preserves comments and structure from existing file
    """
    new_vars = parse_env_content(new_content)
    existing_vars = parse_env_content(existing_content)
    
    # Track which new vars have been written
    written_vars = set()
    
    result_lines = []
    for line in existing_content.splitlines():
        stripped = line.strip()
        
        # Keep comments and empty lines as-is
        if not stripped or stripped.startswith("#"):
            result_lines.append(line)
            continue
        
        # Parse KEY=VALUE
        if "=" in stripped:
            key, _, old_value = stripped.partition("=")
            key = key.strip()
            
            # If new content has this key, use new value
            if key in new_vars:
                new_value = new_vars[key]
                # Only update if new value is non-empty or old value was empty
                if new_value or not old_value.strip():
                    result_lines.append(f"{key}={new_value}")
                else:
                    result_lines.append(line)  # Keep existing non-empty value
                written_vars.add(key)
            else:
                result_lines.append(line)  # Keep existing value
        else:
            result_lines.append(line)
    
    # Add any new vars that weren't in the existing file
    new_additions = [k for k in new_vars if k not in written_vars and k not in existing_vars]
    if new_additions:
        result_lines.append("")
        result_lines.append("# --- Added from Azure ---")
        for key in new_additions:
            if new_vars[key]:  # Only add non-empty values
                result_lines.append(f"{key}={new_vars[key]}")
    
    return "\n".join(result_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate .env file from existing Azure resources"
    )
    parser.add_argument(
        "--resource-group", "-g",
        required=True,
        help="Azure resource group name containing the deployed infrastructure"
    )
    parser.add_argument(
        "--app-name", "-a",
        default=None,
        help="API App Service name to fetch settings from (auto-detected if not specified)"
    )
    parser.add_argument(
        "--env-file", "-e",
        default=None,
        help="Path to output .env file (default: scripts/.env)"
    )
    parser.add_argument(
        "--azd-env", "-n",
        default=None,
        help="Also create azd environment directory with this name"
    )
    parser.add_argument(
        "--no-app-service",
        action="store_true",
        help="Skip App Service and query individual resources instead"
    )
    
    args = parser.parse_args()
    
    # Check Azure CLI is logged in
    account = run_az_command(["account", "show"])
    if not account:
        print("Error: Please login to Azure CLI first: az login", file=sys.stderr)
        sys.exit(1)
    
    print(f"Using Azure subscription: {account.get('name', 'unknown')}")
    
    env_content = None
    
    # Try to get settings from App Service first (fastest and most accurate)
    if not args.no_app_service:
        app_name = args.app_name
        if not app_name:
            # Auto-detect API app service
            app_name, _ = find_api_app_service(args.resource_group)
        
        if app_name:
            env_content = generate_env_from_app_service(args.resource_group, app_name)
            if env_content:
                print(f"\n✓ Generated from App Service: {app_name}")
        else:
            print("No API App Service found, falling back to resource discovery...")
    
    # Fall back to querying individual resources
    if not env_content:
        print("Querying individual Azure resources...")
        env_content = generate_env_content(args.resource_group)
    
    # Determine output path
    script_dir = Path(__file__).parent
    if args.env_file:
        env_path = Path(args.env_file)
    else:
        env_path = script_dir / ".env"
    
    # Merge with existing .env file (preserve values not from API)
    if env_path.exists():
        print(f"\nMerging with existing: {env_path}")
        existing_content = env_path.read_text()
        merged_content = merge_env_content(existing_content, env_content)
        env_path.write_text(merged_content)
        print(f"Updated: {env_path}")
    else:
        # New file: add default Fabric settings and agent IDs
        full_content = env_content + get_default_env_content()
        env_path.write_text(full_content)
        print(f"\nGenerated: {env_path}")
    
    # Also create azd environment if requested
    if args.azd_env:
        azure_dir = script_dir.parent / ".azure"
        azd_env_dir = azure_dir / args.azd_env
        azd_env_dir.mkdir(parents=True, exist_ok=True)
        
        azd_env_path = azd_env_dir / ".env"
        if azd_env_path.exists():
            # Merge with existing content
            existing_content = azd_env_path.read_text()
            merged_content = merge_env_content(existing_content, env_content)
            azd_env_path.write_text(merged_content)
            print(f"Updated (merged): {azd_env_path}")
        else:
            # New file - include defaults
            azd_env_path.write_text(env_content + get_default_env_content())
            print(f"Generated: {azd_env_path}")
        
        # Create config.json
        config_path = azure_dir / "config.json"
        config_path.write_text(json.dumps({"defaultEnvironment": args.azd_env}, indent=2))
        print(f"Generated: {config_path}")
    
    print("\nDone! Review the generated .env file and fill in any missing values.")
    print("Note: FABRIC_WORKSPACE_ID must be set manually if using Fabric.")


if __name__ == "__main__":
    main()
