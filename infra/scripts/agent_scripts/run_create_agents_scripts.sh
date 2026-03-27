#!/bin/bash
set -e
echo "Started the agent creation script setup..."
echo ""

# ─── Parameter source reference ───
# Parameters can be provided via:
#   1. Command-line arguments (positional, see usage below)
#   2. azd environment variables (auto-resolved if CLI args are not provided)
#
# Usage:
#   bash $0 <projectEndpoint> <solutionName> <gptModelName> <aiFoundryResourceId> <apiAppName> <resourceGroup> <usecase> [<isWorkshop>]
#
# Parameter details:
#   $1  projectEndpoint          - Azure AI Project endpoint URL (e.g., https://<ai-service>.services.ai.azure.com/api/projects/<project-name>)  | azd env: AZURE_AI_AGENT_ENDPOINT
#   $2  solutionName             - Solution name used as a suffix for resource naming                                                             | azd env: SOLUTION_NAME
#   $3  gptModelName             - GPT model deployment name (e.g., gpt-4o-mini)                                                                 | azd env: AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME
#   $4  aiFoundryResourceId      - Full Azure resource ID of the AI Foundry (starts with /subscriptions/...)                                     | azd env: AI_FOUNDRY_RESOURCE_ID
#   $5  apiAppName               - Name of the backend API App Service                                                                           | azd env: API_APP_NAME
#   $6  resourceGroup            - Azure resource group name                                                                                     | azd env: AZURE_RESOURCE_GROUP
#   $7  usecase                  - Use case identifier: 'Retail-sales-analysis' or 'Insurance-improve-customer-meetings' (case-insensitive)      | azd env: USE_CASE
#   $8  isWorkshopDeployment     - [Optional] Workshop mode flag: 'true' or 'false' (defaults to 'false')                                       | azd env: IS_WORKSHOP
# ───────────────────────────────

# Variables
projectEndpoint="$1"
solutionName="$2"
gptModelName="$3"
aiFoundryResourceId="$4"
apiAppName="$5"
resourceGroup="$6"
usecase="$7"
isWorkshopDeployment="$8"
azureAiSearchConnectionName="$9"
azureAiSearchIndex="${10}"

# get parameters from azd env, if not provided
if [ -z "$projectEndpoint" ]; then
    projectEndpoint=$(azd env get-value AZURE_AI_AGENT_ENDPOINT)
fi

if [ -z "$solutionName" ]; then
    solutionName=$(azd env get-value SOLUTION_NAME)
fi

if [ -z "$gptModelName" ]; then
    gptModelName=$(azd env get-value AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME)
fi

if [ -z "$aiFoundryResourceId" ]; then
    aiFoundryResourceId=$(azd env get-value AI_FOUNDRY_RESOURCE_ID)
fi

if [ -z "$apiAppName" ]; then
    apiAppName=$(azd env get-value API_APP_NAME)
fi

if [ -z "$resourceGroup" ]; then
    resourceGroup=$(azd env get-value AZURE_RESOURCE_GROUP)
fi

if [ -z "$usecase" ]; then
    usecase=$(azd env get-value USE_CASE)
fi

if [ -z "$isWorkshopDeployment" ]; then
    isWorkshopDeployment=$(azd env get-value IS_WORKSHOP 2>/dev/null || echo "false")
fi

if [ -z "$azureAiSearchConnectionName" ]; then
    azureAiSearchConnectionName=$(azd env get-value AZURE_AI_SEARCH_CONNECTION_NAME 2>/dev/null || echo "")
fi

if [ -z "$azureAiSearchIndex" ]; then
    azureAiSearchIndex=$(azd env get-value AZURE_AI_SEARCH_INDEX 2>/dev/null || echo "")
fi

# ─── Validate required parameters ───
echo "Validating parameters..."
validation_failed=false

if [ -z "$projectEndpoint" ]; then
    echo "❌ ERROR: 'projectEndpoint' is missing."
    echo "   Expected: Azure AI Project endpoint URL (e.g., https://<ai-service>.services.ai.azure.com/api/projects/<project-name>)"
    echo "   Source:   Pass as argument \$1 or set azd env variable AZURE_AI_AGENT_ENDPOINT"
    validation_failed=true
elif [[ ! "$projectEndpoint" =~ ^https:// ]]; then
    echo "❌ ERROR: 'projectEndpoint' has invalid format: $projectEndpoint"
    echo "   Expected: URL starting with https:// (e.g., https://<ai-service>.services.ai.azure.com/api/projects/<project-name>)"
    validation_failed=true
fi

if [ -z "$solutionName" ]; then
    echo "❌ ERROR: 'solutionName' is missing."
    echo "   Expected: Solution name suffix used for resource naming (e.g., da5fi6dninkrjn)"
    echo "   Source:   Pass as argument \$2 or set azd env variable SOLUTION_NAME"
    validation_failed=true
fi

if [ -z "$gptModelName" ]; then
    echo "❌ ERROR: 'gptModelName' is missing."
    echo "   Expected: GPT model deployment name (e.g., gpt-4o-mini, gpt-4o, gpt-4)"
    echo "   Source:   Pass as argument \$3 or set azd env variable AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"
    validation_failed=true
fi

if [ -z "$aiFoundryResourceId" ]; then
    echo "❌ ERROR: 'aiFoundryResourceId' is missing."
    echo "   Expected: Full Azure resource ID (e.g., /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<name>)"
    echo "   Source:   Pass as argument \$4 or set azd env variable AI_FOUNDRY_RESOURCE_ID"
    validation_failed=true
elif [[ ! "$aiFoundryResourceId" =~ ^/subscriptions/ ]]; then
    echo "❌ ERROR: 'aiFoundryResourceId' has invalid format: $aiFoundryResourceId"
    echo "   Expected: Must start with /subscriptions/ (e.g., /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<name>)"
    validation_failed=true
fi

if [ -z "$apiAppName" ]; then
    echo "❌ ERROR: 'apiAppName' is missing."
    echo "   Expected: Name of the backend API App Service (e.g., api-cs-<solutionname>)"
    echo "   Source:   Pass as argument \$5 or set azd env variable API_APP_NAME"
    validation_failed=true
fi

if [ -z "$resourceGroup" ]; then
    echo "❌ ERROR: 'resourceGroup' is missing."
    echo "   Expected: Azure resource group name (e.g., rg-<envname>)"
    echo "   Source:   Pass as argument \$6 or set azd env variable AZURE_RESOURCE_GROUP"
    validation_failed=true
fi

if [ -z "$usecase" ]; then
    echo "❌ ERROR: 'usecase' is missing."
    echo "   Expected: 'Retail-sales-analysis' or 'Insurance-improve-customer-meetings' (case-insensitive)"
    echo "   Source:   Pass as argument \$7 or set azd env variable USE_CASE"
    validation_failed=true
else
    usecase_lower=$(echo "$usecase" | tr '[:upper:]' '[:lower:]')
    if [[ "$usecase_lower" != "retail-sales-analysis" && "$usecase_lower" != "insurance-improve-customer-meetings" ]]; then
        echo "❌ ERROR: 'usecase' has invalid value: $usecase"
        echo "   Expected: 'Retail-sales-analysis' or 'Insurance-improve-customer-meetings' (case-insensitive)"
        validation_failed=true
    fi
fi

if [ -n "$isWorkshopDeployment" ]; then
    is_workshop_lower=$(echo "$isWorkshopDeployment" | tr '[:upper:]' '[:lower:]')
    if [[ "$is_workshop_lower" != "true" && "$is_workshop_lower" != "false" ]]; then
        echo "❌ ERROR: 'isWorkshopDeployment' has invalid value: $isWorkshopDeployment"
        echo "   Expected: 'true' or 'false' (defaults to 'false' if not provided)"
        validation_failed=true
    fi
fi

if [ "$validation_failed" = true ]; then
    echo ""
    echo "──────────────────────────────────────────────────────────────────"
    echo "❌ Parameter validation failed. Please fix the errors above."
    echo ""
    echo "Usage: $0 <projectEndpoint> <solutionName> <gptModelName> <aiFoundryResourceId> <apiAppName> <resourceGroup> <usecase> [<isWorkshop>]"
    echo ""
    echo "Parameters can be provided via command-line arguments or resolved automatically from azd environment variables."
    echo "Run 'azd env get-values' to check your current azd environment."
    echo "──────────────────────────────────────────────────────────────────"
    exit 1
fi

# ─── Print resolved parameters ───
echo ""
echo "=== Resolved Parameters ==="
echo "  Project Endpoint:      $projectEndpoint"
echo "  Solution Name:         $solutionName"
echo "  GPT Model Name:        $gptModelName"
echo "  AI Foundry Resource ID: $aiFoundryResourceId"
echo "  API App Name:          $apiAppName"
echo "  Resource Group:        $resourceGroup"
echo "  Use Case:              $usecase"
echo "  Workshop Deployment:   $isWorkshopDeployment"
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

echo "Getting signed in user id"
signed_user_id=$(az ad signed-in-user show --query id -o tsv) || signed_user_id=${AZURE_CLIENT_ID}

echo "Checking if the user has Azure AI User role on the AI Foundry"
role_assignment=$(MSYS_NO_PATHCONV=1 az role assignment list \
  --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" \
  --scope "$aiFoundryResourceId" \
  --assignee "$signed_user_id" \
  --query "[].roleDefinitionId" -o tsv)

if [ -z "$role_assignment" ]; then
    echo "User does not have the Azure AI User role. Assigning the role..."
    MSYS_NO_PATHCONV=1 az role assignment create \
      --assignee "$signed_user_id" \
      --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" \
      --scope "$aiFoundryResourceId" \
      --output none

    if [ $? -eq 0 ]; then
        echo "✅ Azure AI User role assigned successfully."
    else
        echo "❌ Failed to assign Azure AI User role."
        exit 1
    fi
else
    echo "User already has the Azure AI User role."
fi


requirementFile="infra/scripts/agent_scripts/requirements.txt"

# Download and install Python requirements
python -m pip install --upgrade pip
python -m pip install --quiet -r "$requirementFile"

# Execute the Python scripts
echo "Running Python agents creation script..."
echo "  Workshop deployment: $isWorkshopDeployment"

eval $(python infra/scripts/agent_scripts/01_create_agents.py \
    --ai_project_endpoint="$projectEndpoint" \
    --solution_name="$solutionName" \
    --gpt_model_name="$gptModelName" \
    --usecase="$usecase" \
    --is_workshop="$isWorkshopDeployment" \
    --azure_ai_search_connection_name="$azureAiSearchConnectionName" \
    --azure_ai_search_index="$azureAiSearchIndex")

if [ $? -ne 0 ]; then
    echo "❌ Agents creation script failed."
    exit 1
fi

echo "✓ Agents creation completed."

# Update environment variables of API App
if [ -n "$chatAgentName" ] && [ -n "$titleAgentName" ]; then
    echo "Updating environment variables for App Service: $apiAppName"
  
    az webapp config appsettings set \
    --resource-group "$resourceGroup" \
    --name "$apiAppName" \
    --settings AGENT_NAME_CHAT="$chatAgentName" AGENT_NAME_TITLE="$titleAgentName" \
    -o none

    echo "Environment variables updated for App Service: $apiAppName"

    #Update local azd environment variables
    azd env set AGENT_NAME_CHAT "$chatAgentName"
    azd env set AGENT_NAME_TITLE "$titleAgentName"

else
    echo "Error: One or more agent names are empty. Cannot update environment variables."
    exit 1
fi