#!/bin/bash
echo "Starting the fabric items script"
echo ""

# ─── Parameter source reference ───
# Parameters can be provided via:
#   1. Command-line arguments (positional, see usage below)
#   2. azd environment variables (auto-resolved if CLI args are not provided)
#
# Usage:
#   bash $0 <fabricWorkspaceId> <solutionName> <aiFoundryName> <backend_app_pid> <backend_app_uid> <app_service> <resource_group> <usecase>
#
# Parameter details:
#   $1  fabricWorkspaceId  - Fabric workspace GUID (e.g., 5bd3db28-534a-498d-a7e7-2a1e48fb3246)                                            | user-provided
#   $2  solutionName       - Solution name suffix used for resource naming (e.g., da5fi6dninkrjn)                                           | azd env: SOLUTION_NAME
#   $3  aiFoundryName      - Name of the AI Foundry cognitive services account (e.g., aisa-<solutionname>)                                  | azd env: AI_SERVICE_NAME
#   $4  backend_app_pid    - Backend app managed identity Principal (Object) ID (GUID)                                                      | azd env: API_PID
#   $5  backend_app_uid    - Backend app managed identity Client ID (GUID)                                                                  | azd env: API_UID
#   $6  app_service        - Name of the backend API App Service (e.g., api-cs-<solutionname>)                                              | azd env: API_APP_NAME
#   $7  resource_group     - Azure resource group name (e.g., rg-<envname>)                                                                 | azd env: RESOURCE_GROUP_NAME
#   $8  usecase            - Use case identifier: 'Retail-sales-analysis' or 'Insurance-improve-customer-meetings' (case-insensitive)       | azd env: USE_CASE
# ───────────────────────────────

# Variables
fabricWorkspaceId="$1"
solutionName="$2"
aiFoundryName="$3"
backend_app_pid="$4"
backend_app_uid="$5"
app_service="$6"
resource_group="$7"
usecase="$8"

# get parameters from azd env, if not provided
if [ -z "$solutionName" ]; then
    solutionName=$(azd env get-value SOLUTION_NAME)
fi

if [ -z "$aiFoundryName" ]; then
    aiFoundryName=$(azd env get-value AI_SERVICE_NAME)
fi

if [ -z "$backend_app_pid" ]; then
    backend_app_pid=$(azd env get-value API_PID)
fi

if [ -z "$backend_app_uid" ]; then
    backend_app_uid=$(azd env get-value API_UID)
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

# ─── Validate required parameters ───
echo "Validating parameters..."
validation_failed=false

if [ -z "$fabricWorkspaceId" ]; then
    echo "❌ ERROR: 'fabricWorkspaceId' is missing."
    echo "   Expected: Fabric workspace GUID (e.g., 5bd3db28-534a-498d-a7e7-2a1e48fb3246)"
    echo "   Source:   Pass as argument \$1 (this parameter must always be provided manually)"
    validation_failed=true
elif [[ ! "$fabricWorkspaceId" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
    echo "❌ ERROR: 'fabricWorkspaceId' is not a valid GUID: $fabricWorkspaceId"
    echo "   Expected: GUID format (e.g., 5bd3db28-534a-498d-a7e7-2a1e48fb3246)"
    validation_failed=true
fi

if [ -z "$solutionName" ]; then
    echo "❌ ERROR: 'solutionName' is missing."
    echo "   Expected: Solution name suffix used for resource naming (e.g., da5fi6dninkrjn)"
    echo "   Source:   Pass as argument \$2 or set azd env variable SOLUTION_NAME"
    validation_failed=true
fi

if [ -z "$aiFoundryName" ]; then
    echo "❌ ERROR: 'aiFoundryName' is missing."
    echo "   Expected: Name of the AI Foundry cognitive services account (e.g., aisa-<solutionname>)"
    echo "   Source:   Pass as argument \$3 or set azd env variable AI_SERVICE_NAME"
    validation_failed=true
fi

if [ -z "$backend_app_pid" ]; then
    echo "❌ ERROR: 'backend_app_pid' (backend app managed identity Principal ID) is missing."
    echo "   Expected: GUID (e.g., 776846ec-52a3-4ebd-8495-217d592c4158)"
    echo "   Source:   Pass as argument \$4 or set azd env variable API_PID"
    validation_failed=true
elif [[ ! "$backend_app_pid" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
    echo "❌ ERROR: 'backend_app_pid' is not a valid GUID: $backend_app_pid"
    echo "   Expected: GUID format (e.g., 776846ec-52a3-4ebd-8495-217d592c4158)"
    validation_failed=true
fi

if [ -z "$backend_app_uid" ]; then
    echo "❌ ERROR: 'backend_app_uid' (backend app managed identity Client ID) is missing."
    echo "   Expected: GUID (e.g., c37a7fd9-86d8-40bc-a18c-7011ec963e03)"
    echo "   Source:   Pass as argument \$5 or set azd env variable API_UID"
    validation_failed=true
elif [[ ! "$backend_app_uid" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
    echo "❌ ERROR: 'backend_app_uid' is not a valid GUID: $backend_app_uid"
    echo "   Expected: GUID format (e.g., c37a7fd9-86d8-40bc-a18c-7011ec963e03)"
    validation_failed=true
fi

if [ -z "$app_service" ]; then
    echo "❌ ERROR: 'app_service' is missing."
    echo "   Expected: Name of the backend API App Service (e.g., api-cs-<solutionname>)"
    echo "   Source:   Pass as argument \$6 or set azd env variable API_APP_NAME"
    validation_failed=true
fi

if [ -z "$resource_group" ]; then
    echo "❌ ERROR: 'resource_group' is missing."
    echo "   Expected: Azure resource group name (e.g., rg-<envname>)"
    echo "   Source:   Pass as argument \$7 or set azd env variable RESOURCE_GROUP_NAME"
    validation_failed=true
fi

if [ -z "$usecase" ]; then
    echo "❌ ERROR: 'usecase' is missing."
    echo "   Expected: 'Retail-sales-analysis' or 'Insurance-improve-customer-meetings' (case-insensitive)"
    echo "   Source:   Pass as argument \$8 or set azd env variable USE_CASE"
    validation_failed=true
else
    usecase_lower=$(echo "$usecase" | tr '[:upper:]' '[:lower:]')
    if [[ "$usecase_lower" != "retail-sales-analysis" && "$usecase_lower" != "insurance-improve-customer-meetings" ]]; then
        echo "❌ ERROR: 'usecase' has invalid value: $usecase"
        echo "   Expected: 'Retail-sales-analysis' or 'Insurance-improve-customer-meetings' (case-insensitive)"
        validation_failed=true
    fi
fi

if [ "$validation_failed" = true ]; then
    echo ""
    echo "──────────────────────────────────────────────────────────────────"
    echo "❌ Parameter validation failed. Please fix the errors above."
    echo ""
    echo "Usage: $0 <fabricWorkspaceId> <solutionName> <aiFoundryName> <backend_app_pid> <backend_app_uid> <app_service> <resource_group> <usecase>"
    echo ""
    echo "Parameters can be provided via command-line arguments or resolved automatically from azd environment variables."
    echo "Run 'azd env get-values' to check your current azd environment."
    echo "──────────────────────────────────────────────────────────────────"
    exit 1
fi

# ─── Print resolved parameters ───
echo ""
echo "=== Resolved Parameters ==="
echo "  Fabric Workspace ID:   $fabricWorkspaceId"
echo "  Solution Name:         $solutionName"
echo "  AI Foundry Name:       $aiFoundryName"
echo "  Backend App PID:       $backend_app_pid"
echo "  Backend App UID:       $backend_app_uid"
echo "  App Service:           $app_service"
echo "  Resource Group:        $resource_group"
echo "  Use Case:              $usecase"
echo "==========================="
echo ""

# Check if user is logged in to Azure
echo "Checking Azure authentication..."
if az account show &> /dev/null; then
    echo "Already authenticated with Azure."
else
    # Use Azure CLI login if running locally
    echo "Authenticating with Azure CLI..."
    az login --use-device-code
fi

# # get signed user
# echo "Getting signed in user id"
# signed_user_id=$(az ad signed-in-user show --query id -o tsv)

# # Check if the user_id is empty
# if [ -z "$signed_user_id" ]; then
#     echo "Error: User ID not found. Please check the user principal name or email address."
#     exit 1
# fi

# # # Define the scope for the Key Vault (replace with your Key Vault resource ID)
# # echo "Getting key vault resource id"
# # key_vault_resource_id=$(az keyvault show --name $keyvaultName --query id --output tsv)

# # # Check if the key_vault_resource_id is empty
# # if [ -z "$key_vault_resource_id" ]; then
# #     echo "Error: Key Vault not found. Please check the Key Vault name."
# #     exit 1
# # fi

# # # Assign the Key Vault Administrator role to the user
# # echo "Assigning the Key Vault Administrator role to the user..."
# # az role assignment create --assignee $signed_user_id --role "Key Vault Administrator" --scope $key_vault_resource_id

# # Define the scope for the Azure AI Foundry resource
# echo "Getting Azure AI Foundry id"
# # aiFoundryId=$(az resource show --name $aiFoundryName --resource-type "Microsoft.AI" --resource-group $resource_group --query id --output tsv)

# az account set --subscription ""

# ai_foundry_resource_id=$(az cognitiveservices account show \
#   --name "$aiFoundryName" --resource-group "$resource_group" \
#   --query id -o tsv)

# echo "Azure AI Foundry ID: $ai_foundry_resource_id"

# echo "Assigning the Azure AI User role to the user..."
# az role assignment create --assignee $signed_user_id --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" --scope $ai_foundry_resource_id

# # Check if the role assignment command was successful
# if [ $? -ne 0 ]; then
#     echo "Error: Role assignment failed. Please check the provided details and your Azure permissions."
#     exit 1
# fi
# echo "Role assignment completed successfully."

#Replace key vault name and workspace id in the python files
# sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "create_fabric_items.py"
# sed -i "s/solutionName_to-be-replaced/${solutionName}/g" "create_fabric_items.py"
# sed -i "s/workspaceId_to-be-replaced/${fabricWorkspaceId}/g" "create_fabric_items.py"
python -m pip install -r infra/scripts/fabric_scripts/requirements.txt --quiet

# Run Python unbuffered so prints show immediately.
tmp="$(mktemp)"
cleanup() { rm -f "$tmp"; }
trap cleanup EXIT

python -u infra/scripts/fabric_scripts/create_fabric_items.py --workspaceId "$fabricWorkspaceId" --solutionname "$solutionName" --backend_app_pid "$backend_app_pid" --backend_app_uid "$backend_app_uid" --usecase "$usecase" --exports-file "$tmp"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Fabric items creation completed successfully!"
else
    echo ""
    echo "⚠ Fabric items creation encountered errors. Please check the output above."
    exit 1
fi

source "$tmp"

FABRIC_SQL_SERVER="$FABRIC_SQL_SERVER1"
FABRIC_SQL_DATABASE="$FABRIC_SQL_DATABASE1"
FABRIC_SQL_CONNECTION_STRING="$FABRIC_SQL_CONNECTION_STRING1"

# Update environment variables of API App
if [ -n "$FABRIC_SQL_SERVER" ] && [ -n "$FABRIC_SQL_DATABASE" ] && [ -n "$FABRIC_SQL_CONNECTION_STRING" ]; then
    az webapp config appsettings set \
      --resource-group "$resource_group" \
      --name "$app_service" \
      --settings FABRIC_SQL_SERVER="$FABRIC_SQL_SERVER" FABRIC_SQL_DATABASE="$FABRIC_SQL_DATABASE" FABRIC_SQL_CONNECTION_STRING="$FABRIC_SQL_CONNECTION_STRING" \
      -o none
    echo "Environment variables updated for App Service: $app_service"
else
    echo "Error: One or more required environment variables are empty. Skipping updating environment variables for App Service."
    exit 1
fi