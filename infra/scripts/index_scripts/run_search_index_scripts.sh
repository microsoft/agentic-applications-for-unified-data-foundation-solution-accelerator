#!/bin/bash
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Variables
resourceGroupName="$1"
searchEndpoint="$2"
aiSearchName="$3"
aiProjectEndpoint="$4"
openaiEndpoint="$5"
embeddingModel="$6"
indexName="$7"
dataFolder="$8"

# Get parameters from azd env, if not provided
if [ -z "$resourceGroupName" ]; then
    resourceGroupName=$(azd env get-value RESOURCE_GROUP_NAME)
fi

if [ -z "$searchEndpoint" ]; then
    searchEndpoint=$(azd env get-value AZURE_AI_SEARCH_ENDPOINT)
fi

if [ -z "$aiSearchName" ]; then
    aiSearchName=$(azd env get-value AZURE_AI_SEARCH_NAME)
fi

if [ -z "$aiProjectEndpoint" ]; then
    aiProjectEndpoint=$(azd env get-value AZURE_AI_PROJECT_ENDPOINT)
fi

if [ -z "$openaiEndpoint" ]; then
    openaiEndpoint=$(azd env get-value AZURE_OPENAI_ENDPOINT)
fi

if [ -z "$embeddingModel" ]; then
    embeddingModel=$(azd env get-value AZURE_OPENAI_EMBEDDING_MODEL)
fi

if [ -z "$indexName" ]; then
    indexName=$(azd env get-value AZURE_AI_SEARCH_INDEX)
fi

if [ -z "$indexName" ]; then
    indexName="knowledge_index"
fi

if [ -z "$dataFolder" ]; then
    dataFolder=$(azd env get-value SEARCH_DATA_FOLDER)
fi

if [ -z "$dataFolder" ]; then
    dataFolder="data/default/documents"
fi

# Check if all required arguments are provided
if [ -z "$resourceGroupName" ] || [ -z "$searchEndpoint" ] || [ -z "$aiSearchName" ] || \
   [ -z "$aiProjectEndpoint" ] || [ -z "$openaiEndpoint" ] || [ -z "$embeddingModel" ]; then
    echo "Usage: $0 <resourceGroupName> <searchEndpoint> <aiSearchName> <aiProjectEndpoint> <openaiEndpoint> <embeddingModel>"
    exit 1
fi

# Check if user is logged in to Azure
if az account show &> /dev/null; then
    echo "Already authenticated with Azure."
else
    az login --use-device-code
fi

# Get signed in user id
signed_user_id=$(az ad signed-in-user show --query id -o tsv) || signed_user_id=${AZURE_CLIENT_ID}

# Assign Search Index Data Contributor role
search_resource_id=$(az search service show --name $aiSearchName --resource-group $resourceGroupName --query id --output tsv)

role_assignment=$(MSYS_NO_PATHCONV=1 az role assignment list \
    --assignee "$signed_user_id" \
    --role "Search Index Data Contributor" \
    --scope "$search_resource_id" \
    --query "[].roleDefinitionId" -o tsv)

if [ -z "$role_assignment" ]; then
    MSYS_NO_PATHCONV=1 az role assignment create \
        --assignee "$signed_user_id" \
        --role "Search Index Data Contributor" \
        --scope "$search_resource_id" \
        --output none

    if [ $? -eq 0 ]; then
        echo "✅ Search Index Data Contributor role assigned successfully."
    else
        echo "❌ Failed to assign Search Index Data Contributor role."
        exit 1
    fi
fi

# Install Python requirements
pip install --quiet -r "$SCRIPT_DIR/requirements.txt"
if [ $? -ne 0 ]; then
    echo "❌ Failed to install Python requirements"
    exit 1
fi

# Run index creation and data upload
error_flag=false

python "$SCRIPT_DIR/01_create_search_index.py" \
    --search_endpoint="$searchEndpoint" \
    --openai_endpoint="$openaiEndpoint" \
    --embedding_model="$embeddingModel" \
    --index_name="$indexName"

if [ $? -ne 0 ]; then
    error_flag=true
fi

python "$SCRIPT_DIR/02_upload_documents.py" \
    --search_endpoint="$searchEndpoint" \
    --ai_project_endpoint="$aiProjectEndpoint" \
    --embedding_model="$embeddingModel" \
    --index_name="$indexName" \
    --data_folder="$dataFolder"

if [ $? -ne 0 ]; then
    error_flag=true
fi

# Final status
if [ "$error_flag" = true ]; then
    exit 1
fi

