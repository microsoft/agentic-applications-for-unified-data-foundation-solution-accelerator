#!/bin/bash
echo "starting script"

# Variables
fabricWorkspaceId="$1"
solutionName="$2"
aiFoundryName="$3"
backend_app_pid="$4"
backend_app_uid="$5"
app_service="$6"
resource_group="$7"

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

python -m pip install -r requirements.txt --quiet

# Run Python unbuffered so prints show immediately.
tmp="$(mktemp)"
cleanup() { rm -f "$tmp"; }
trap cleanup EXIT

python -u create_fabric_items.py --workspaceId "$fabricWorkspaceId" --solutionname "$solutionName" --backend_app_pid "$backend_app_pid" --backend_app_uid "$backend_app_uid" --exports-file "$tmp"

source "$tmp"

FABRIC_SQL_SERVER="$FABRIC_SQL_SERVER1"
FABRIC_SQL_DATABASE="$FABRIC_SQL_DATABASE1"
FABRIC_SQL_CONNECTION_STRING="$FABRIC_SQL_CONNECTION_STRING1"

# Update environment variables of API App
az webapp config appsettings set \
  --resource-group "$resource_group" \
  --name "$app_service" \
  --settings FABRIC_SQL_SERVER="$FABRIC_SQL_SERVER" FABRIC_SQL_DATABASE="$FABRIC_SQL_DATABASE" FABRIC_SQL_CONNECTION_STRING="$FABRIC_SQL_CONNECTION_STRING" \
  -o none

echo "Environment variables updated for App Service: $app_service"
