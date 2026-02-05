#!/bin/bash
echo "Starting the Azure SQL Server items script"

# Variables
sqlServer="$1"
sqlDatabase="$2"
backend_app_uid="$3"
app_service="$4"
resource_group="$5"
usecase="$6"

# Get parameters from azd env, if not provided
if [ -z "$sqlServer" ]; then
    sqlServer=$(azd env get-value SQLDB_SERVER)
fi

if [ -z "$sqlDatabase" ]; then
    sqlDatabase=$(azd env get-value SQLDB_DATABASE)
fi

if [ -z "$backend_app_uid" ]; then
    backend_app_uid=$(azd env get-value SQLDB_USER_MID)
    # Fallback to API_UID if SQLDB_USER_MID is not set
    if [ -z "$backend_app_uid" ]; then
        backend_app_uid=$(azd env get-value API_UID)
    fi
fi

if [ -z "$app_service" ]; then
    app_service=$(azd env get-value API_APP_NAME)
fi

if [ -z "$resource_group" ]; then
    resource_group=$(azd env get-value RESOURCE_GROUP_NAME)
fi

if [ -z "$usecase" ]; then
    usecase=$(azd env get-value USE_CASE)
fi

# Check if all required arguments are present
if [ -z "$sqlServer" ] || [ -z "$sqlDatabase" ] || [ -z "$backend_app_uid" ] || [ -z "$app_service" ] || [ -z "$resource_group" ] || [ -z "$usecase" ]; then
    echo "Usage: $0 <sqlServer> <sqlDatabase> <backend_app_uid> <app_service> <resource_group> <usecase>"
    echo ""
    echo "Arguments can also be set via azd env variables:"
    echo "  SQLDB_SERVER, SQLDB_DATABASE, SQLDB_USER_MID (or API_UID), API_APP_NAME, RESOURCE_GROUP_NAME, USE_CASE"
    exit 1
fi

# Check if user is logged in to Azure
echo "Checking Azure authentication..."
if az account show &> /dev/null; then
    echo "Already authenticated with Azure."
else
    # Use Azure CLI login if running locally
    echo "Authenticating with Azure CLI..."
    az login --use-device-code
fi

# Extract SQL Server name from FQDN (remove .database.windows.net)
sqlServerName="${sqlServer%.database.windows.net}"

# Get signed-in user details
echo ""
echo "Getting signed-in user details..."
signed_user_id=$(az ad signed-in-user show --query id -o tsv)
signed_user_display_name=$(az ad signed-in-user show --query userPrincipalName -o tsv)

if [ -z "$signed_user_id" ]; then
    echo "Error: Could not get signed-in user ID. Please ensure you are logged in."
    exit 1
fi

echo "Signed-in user: $signed_user_display_name"

# Assign signed-in user as SQL Server Admin (required to run scripts)
echo ""
echo "Checking SQL Server admin permissions..."
sql_server_resource_id=$(az sql server show --name "$sqlServerName" --resource-group "$resource_group" --query id --output tsv 2>/dev/null)

if [ -z "$sql_server_resource_id" ]; then
    echo "Error: Could not find SQL Server '$sqlServerName' in resource group '$resource_group'"
    exit 1
fi

# Check if user is already an admin
admin=$(MSYS_NO_PATHCONV=1 az sql server ad-admin list --ids "$sql_server_resource_id" --query "[?sid == '$signed_user_id']" -o tsv 2>/dev/null)

if [ -z "$admin" ]; then
    echo "✓ Assigning user as SQL Server Admin..."
    MSYS_NO_PATHCONV=1 az sql server ad-admin create \
        --display-name "$signed_user_display_name" \
        --object-id "$signed_user_id" \
        --resource-group "$resource_group" \
        --server "$sqlServerName" \
        --output none
    if [ $? -ne 0 ]; then
        echo "✗ Failed to assign SQL Server Admin role"
        exit 1
    fi
    echo "✓ SQL Server Admin role assigned successfully"
else
    echo "✓ User is already a SQL Server Admin"
fi

# Install Python dependencies
python -m pip install -r infra/scripts/sql_scripts/requirements.txt --quiet

# Run Python unbuffered so prints show immediately.
tmp="$(mktemp)"
cleanup() { rm -f "$tmp"; }
trap cleanup EXIT

echo ""
echo "Creating tables and loading sample data into Azure SQL Server..."
echo "SQL Server: $sqlServer"
echo "SQL Database: $sqlDatabase"
echo "Use Case: $usecase"
echo ""

python -u infra/scripts/sql_scripts/create_sql_items.py \
    --sql-server "$sqlServer" \
    --sql-database "$sqlDatabase" \
    --backend_app_uid "$backend_app_uid" \
    --usecase "$usecase" \
    --exports-file "$tmp"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Azure SQL Server items creation completed successfully!"
else
    echo ""
    echo "⚠ Azure SQL Server items creation encountered errors. Please check the output above."
    exit 1
fi

source "$tmp"

SQLDB_SERVER="$SQLDB_SERVER1"
SQLDB_DATABASE="$SQLDB_DATABASE1"
SQLDB_CONNECTION_STRING="$SQLDB_CONNECTION_STRING1"

# Update environment variables of API App
if [ -n "$SQLDB_SERVER" ] && [ -n "$SQLDB_DATABASE" ] && [ -n "$SQLDB_CONNECTION_STRING" ]; then
    echo ""
    echo "Updating App Service environment variables..."
    az webapp config appsettings set \
      --resource-group "$resource_group" \
      --name "$app_service" \
      --settings \
        SQLDB_SERVER="$SQLDB_SERVER" \
        SQLDB_DATABASE="$SQLDB_DATABASE" \
        SQLDB_CONNECTION_STRING="$SQLDB_CONNECTION_STRING" \
        IS_WORKSHOP="True" \
      -o none
    echo "✓ Environment variables updated for App Service: $app_service"
else
    echo "Error: One or more required environment variables are empty. Skipping updating environment variables for App Service."
    exit 1
fi

echo ""
echo "========================================"
echo "Azure SQL Server Setup Complete!"
echo "========================================"
echo "Server: $SQLDB_SERVER"
echo "Database: $SQLDB_DATABASE"
echo "App Service: $app_service"
echo "IS_WORKSHOP: True"
echo "========================================"
