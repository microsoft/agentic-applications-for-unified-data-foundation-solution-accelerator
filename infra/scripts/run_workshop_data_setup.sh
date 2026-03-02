#!/bin/bash
set -e

echo "Starting Workshop Deployment Setup..."
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Variables (can be passed as arguments or retrieved from azd env)
sqlServer="$1"
sqlDatabase="$2"
backend_app_uid="$3"
app_service="$4"
resource_group="$5"
usecase="$6"
backend_app_display_name="$7"

# Get parameters from azd env, if not provided
if [ -z "$sqlServer" ]; then
    sqlServer=$(azd env get-value SQLDB_SERVER 2>/dev/null || echo "")
fi

if [ -z "$sqlDatabase" ]; then
    sqlDatabase=$(azd env get-value SQLDB_DATABASE 2>/dev/null || echo "")
fi

if [ -z "$backend_app_uid" ]; then
    backend_app_uid=$(azd env get-value SQLDB_USER_MID 2>/dev/null || echo "")
    if [ -z "$backend_app_uid" ]; then
        backend_app_uid=$(azd env get-value API_UID 2>/dev/null || echo "")
    fi
fi

if [ -z "$app_service" ]; then
    app_service=$(azd env get-value API_APP_NAME 2>/dev/null || echo "")
fi

if [ -z "$resource_group" ]; then
    resource_group=$(azd env get-value RESOURCE_GROUP_NAME 2>/dev/null || echo "")
fi

if [ -z "$usecase" ]; then
    usecase=$(azd env get-value USE_CASE 2>/dev/null || echo "")
fi

if [ -z "$backend_app_display_name" ]; then
    backend_app_display_name=$(azd env get-value MID_DISPLAY_NAME 2>/dev/null || echo "")
fi

# Get additional parameters for search index
searchEndpoint=$(azd env get-value AZURE_AI_SEARCH_ENDPOINT 2>/dev/null || echo "")
aiSearchName=$(azd env get-value AZURE_AI_SEARCH_NAME 2>/dev/null || echo "")
aiProjectEndpoint=$(azd env get-value AZURE_AI_PROJECT_ENDPOINT 2>/dev/null || echo "")
openaiEndpoint=$(azd env get-value AZURE_OPENAI_ENDPOINT 2>/dev/null || echo "")
embeddingModel=$(azd env get-value AZURE_OPENAI_EMBEDDING_MODEL 2>/dev/null || echo "")
indexName=$(azd env get-value AZURE_AI_SEARCH_INDEX 2>/dev/null || echo "knowledge_index")
dataFolder=$(azd env get-value SEARCH_DATA_FOLDER 2>/dev/null || echo "data/default/documents")

# Validate required parameters
missing_params=""
if [ -z "$sqlServer" ]; then missing_params="$missing_params SQLDB_SERVER"; fi
if [ -z "$sqlDatabase" ]; then missing_params="$missing_params SQLDB_DATABASE"; fi
if [ -z "$backend_app_uid" ]; then missing_params="$missing_params SQLDB_USER_MID"; fi
if [ -z "$app_service" ]; then missing_params="$missing_params API_APP_NAME"; fi
if [ -z "$resource_group" ]; then missing_params="$missing_params RESOURCE_GROUP_NAME"; fi
if [ -z "$usecase" ]; then missing_params="$missing_params USE_CASE"; fi

if [ -n "$missing_params" ]; then
    echo "Error: Missing required parameters:$missing_params"
    echo ""
    echo "Usage: $0 [sqlServer] [sqlDatabase] [backend_app_uid] [app_service] [resource_group] [usecase] [backend_app_display_name]"
    echo ""
    echo "Or set the following azd environment variables:"
    echo "  SQLDB_SERVER, SQLDB_DATABASE, SQLDB_USER_MID, API_APP_NAME, RESOURCE_GROUP_NAME, USE_CASE"
    exit 1
fi

# Check if user is logged in to Azure
echo "Checking Azure authentication..."
if az account show &> /dev/null; then
    echo "✓ Already authenticated with Azure."
else
    echo "Authenticating with Azure CLI..."
    az login --use-device-code
fi

# Get signed-in user details
signed_user_id=$(az ad signed-in-user show --query id -o tsv)
signed_user_display_name=$(az ad signed-in-user show --query userPrincipalName -o tsv)
echo "✓ Signed-in user: $signed_user_display_name"
echo ""

# Step 2: Run SQL Items Script
echo "Step 1: Creating SQL tables and loading sample data..."

bash "$SCRIPT_DIR/sql_scripts/run_sql_items_scripts.sh" \
    "$sqlServer" \
    "$sqlDatabase" \
    "$backend_app_uid" \
    "$app_service" \
    "$resource_group" \
    "$usecase"

if [ $? -ne 0 ]; then
    echo "✗ SQL items script failed"
    exit 1
fi
echo "✓ SQL items creation completed"
echo ""

# Step 2: Process Sample Data (Search Index)
echo "Step 2: Creating search index and uploading documents..."

# Check if search parameters are available
if [ -n "$searchEndpoint" ] && [ -n "$aiSearchName" ] && [ -n "$openaiEndpoint" ] && [ -n "$embeddingModel" ]; then
    bash "$SCRIPT_DIR/index_scripts/run_search_index_scripts.sh" \
        "$resource_group" \
        "$searchEndpoint" \
        "$aiSearchName" \
        "$aiProjectEndpoint" \
        "$openaiEndpoint" \
        "$embeddingModel" \
        "$indexName" \
        "$dataFolder"
    
    if [ $? -ne 0 ]; then
        echo "⚠ Search index creation had issues (non-fatal)"
    else
        echo "✓ Search index created and documents uploaded"
    fi
else
    echo "⚠ Skipping search index creation: missing search configuration"
    echo "  Required: AZURE_AI_SEARCH_ENDPOINT, AZURE_AI_SEARCH_NAME, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_EMBEDDING_MODEL"
fi
echo ""

# Step 3: Assign SQL Roles to Managed Identity
echo "Step 3: Assigning SQL roles to managed identity..."

# Install Python dependencies for role assignment
pip install --quiet pyodbc azure-identity

# Get backend app display name if not provided
if [ -z "$backend_app_display_name" ]; then
    # Try to get from managed identity name
    backend_app_display_name=$(azd env get-value BACKEND_USER_MID_NAME 2>/dev/null || echo "")
fi

# Sanitize values - remove any control characters/newlines
backend_app_display_name=$(echo "$backend_app_display_name" | tr -d '\r\n')
backend_app_uid=$(echo "$backend_app_uid" | tr -d '\r\n')

if [ -n "$backend_app_display_name" ] && [ -n "$backend_app_uid" ]; then
    # Build roles JSON for the managed identity using printf for proper escaping
    roles_json=$(printf '[{"clientId": "%s", "displayName": "%s", "role": "db_datareader"}, {"clientId": "%s", "displayName": "%s", "role": "db_datawriter"}]' \
        "$backend_app_uid" "$backend_app_display_name" "$backend_app_uid" "$backend_app_display_name")
    echo "Role json for SQL role assignment: $roles_json"

    python "$SCRIPT_DIR/add_user_scripts/assign_sql_roles.py" \
        --server "$sqlServer" \
        --database "$sqlDatabase" \
        --roles-json "$roles_json"
    
    if [ $? -ne 0 ]; then
        echo "⚠ SQL role assignment had issues (non-fatal)"
    else
        echo "✓ SQL roles assigned successfully"
    fi
else
    echo "⚠ Skipping SQL role assignment: backend_app_display_name not available"
fi
echo ""

# Final Summary
echo ""
echo "Workshop Setup Complete!"
echo "  SQL Server: $sqlServer"
echo "  Database: $sqlDatabase"
echo "  App Service: $app_service"
