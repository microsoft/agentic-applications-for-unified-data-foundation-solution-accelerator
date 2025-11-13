#!/bin/bash
echo "Starting the fabric items deletion script"

# Variables
fabricWorkspaceId="$1"
solutionName="$2"
backend_app_pid="$3"

# get parameters from azd env, if not provided
if [ -z "$solutionName" ]; then
    solutionName=$(azd env get-value SOLUTION_NAME)
fi

if [ -z "$backend_app_pid" ]; then
    backend_app_pid=$(azd env get-value API_PID)
fi

# Check if all required arguments are present
if [ -z "$fabricWorkspaceId" ] || [ -z "$solutionName" ] || [ -z "$backend_app_pid" ]; then
    echo "Usage: $0 <fabricWorkspaceId> <solutionName> <backend_app_pid>"
    echo ""
    echo "Arguments:"
    echo "  fabricWorkspaceId : The Fabric workspace ID"
    echo "  solutionName      : The solution name"
    echo "  backend_app_pid   : The backend app principal ID"
    exit 1
fi

# Check if user is logged in to Azure
echo "Checking Azure authentication..."
if az account show &> /dev/null; then
    echo "Already authenticated with Azure."
else
    # Use Azure CLI login if running locally
    echo "Authenticating with Azure CLI..."
    az login
fi

# Install required Python packages
echo "Installing required Python packages..."
python -m pip install -r infra/scripts/fabric_scripts/requirements.txt --quiet

# Run deletion script
echo ""
echo "Deleting Fabric items for solution: $solutionName"
echo "Workspace ID: $fabricWorkspaceId"
echo "============================================================"
echo ""

python -u infra/scripts/fabric_scripts/delete_fabric_items.py \
    --workspaceId "$fabricWorkspaceId" \
    --solutionname "$solutionName" \
    --backend_app_pid "$backend_app_pid"

# Check if the script completed successfully
if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Fabric items deletion completed successfully!"
else
    echo ""
    echo "⚠ Fabric items deletion encountered errors. Please check the output above."
    exit 1
fi
