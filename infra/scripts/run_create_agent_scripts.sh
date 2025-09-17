#!/bin/bash
set -e
echo "Started the agent creation script setup..."

# Variables
baseUrl="$1"
managedIdentityClientId="$2"
projectEndpoint="$3"
solutionName="$4"
gptModelName="$5"

requirementFile="requirements.txt"
requirementFileUrl="${baseUrl}infra/scripts/agent_scripts/requirements.txt"

echo "Downloading files..."
curl --output "azure_credential_utils.py" "${baseUrl}infra/scripts/azure_credential_utils.py"
curl --output "01_create_agents.py" "${baseUrl}infra/scripts/agent_scripts/01_create_agents.py"
curl --output "tables.json" "${baseUrl}infra/scripts/fabric_scripts/sql_files/tables.json"

# Download and install Python requirements
curl --output "$requirementFile" "$requirementFileUrl"
pip install --upgrade pip
pip install -r "$requirementFile"

#Replace placeholder values with actuals
sed -i "s#project_endpoint_to-be-replaced#${projectEndpoint}#g" 01_create_agents.py
sed -i "s/mici_to-be-replaced/${managedIdentityClientId}/g" "01_create_agents.py"
sed -i "s/solution_name_to-be-replaced/${solutionName}/g" "01_create_agents.py"
sed -i "s/gpt_model_name_to-be-replaced/${gptModelName}/g" "01_create_agents.py"

# Execute the Python scripts
echo "Running Python agent scripts..."
# python 01_create_agents.py
agentIds=$(python 01_create_agents.py)

echo "agent creation completed."
echo "agentIds: $agentIds"

# write outputs for Bicep
printf '%s' "$agentIds" > "$AZ_SCRIPTS_OUTPUT_PATH"