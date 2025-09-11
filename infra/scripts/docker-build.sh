#!/bin/bash

set -e

AZURE_SUBSCRIPTION_ID="$1"
ENV_NAME="$2"
AZURE_LOCATION="$3"
AZURE_RESOURCE_GROUP="$4"
USE_LOCAL_BUILD="$5"
AZURE_ENV_IMAGETAG="$6"

# Validate required parameters
if [[ -z "$AZURE_SUBSCRIPTION_ID" || -z "$ENV_NAME" || -z "$AZURE_LOCATION" || -z "$AZURE_RESOURCE_GROUP" ]]; then
    echo "Missing required arguments. Usage: docker-build.sh <AZURE_SUBSCRIPTION_ID> <ENV_NAME> <AZURE_LOCATION> <AZURE_RESOURCE_GROUP> <USE_LOCAL_BUILD> <AZURE_ENV_IMAGETAG>"
    exit 1
fi

# Ensure jq is installed
which jq || { echo "jq is not installed"; exit 1; }

# Exit early if local build is not requested
if [[ "${USE_LOCAL_BUILD,,}" != "true" ]]; then
    echo "Local Build not enabled. Using prebuilt image."
    exit 0
fi

AZURE_ENV_IMAGETAG=${AZURE_ENV_IMAGETAG:-latest}

echo "Local Build enabled. Starting build process."

# STEP 1: Ensure user is logged into Azure
if ! az account show > /dev/null 2>&1; then
    echo "Not logged in to Azure. Attempting az login..."
    az login
    if [[ $? -ne 0 ]]; then
        echo "Azure login failed."
        exit 1
    fi
else
    echo "Already logged in to Azure."
fi

# STEP 2: Set Azure subscription
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
if [[ $? -ne 0 ]]; then
    echo "Failed to set Azure subscription."
    exit 1
fi

# STEP 3: Deploy container registry
echo "Deploying container registry in location: $AZURE_LOCATION"
OUTPUTS=$(az deployment group create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --template-file "./infra/deploy_container_registry.bicep" \
    --parameters environmentName="$ENV_NAME" \
    --query "properties.outputs" \
    --output json)

ACR_NAME=$(echo "$OUTPUTS" | jq -r '.createdAcrName.value')

echo "Extracted ACR Name: $ACR_NAME"

# STEP 4: Login to Azure Container Registry
echo "Logging into Azure Container Registry: $ACR_NAME"
az acr login -n "$ACR_NAME"
if [[ $? -ne 0 ]]; then
    echo "Failed to log in to ACR"
    exit 1
fi

# STEP 5: Get current script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# STEP 6: Resolve full paths to Dockerfiles and build contexts
WEBAPP_DOCKERFILE_PATH="$SCRIPT_DIR/../../src/App/WebApp.Dockerfile"
WEBAPP_CONTEXT_PATH="$SCRIPT_DIR/../../src/App"
APIAPP_DOCKERFILE_PATH="$SCRIPT_DIR/../../src/api/ApiApp.Dockerfile"
APIAPP_CONTEXT_PATH="$SCRIPT_DIR/../../src/api"

# STEP 7: Define function to build and push Docker images
build_and_push_image() {
    IMAGE_NAME="$1"
    BUILD_PATH="$2"
    BUILD_CONTEXT="$3"
    TAG="$4"

    IMAGE_URI="$ACR_NAME.azurecr.io/${IMAGE_NAME}:$TAG"

    echo -e "\n--- Building Docker image: $IMAGE_URI ---"
    docker build --no-cache -f "$BUILD_PATH" -t "$IMAGE_URI" "$BUILD_CONTEXT"
    if [[ $? -ne 0 ]]; then
        echo "Failed to build Docker image: $IMAGE_URI"
        exit 1
    fi

    echo "--- Pushing Docker image to ACR: $IMAGE_URI ---"
    docker push "$IMAGE_URI"
    if [[ $? -ne 0 ]]; then
        echo "Failed to push Docker image: $IMAGE_URI"
        exit 1
    fi

    echo "--- Docker image pushed successfully: $IMAGE_URI ---"
}

# STEP 8: Build and push images with provided tag
build_and_push_image "da-api" "$APIAPP_DOCKERFILE_PATH" "$APIAPP_CONTEXT_PATH" "$AZURE_ENV_IMAGETAG"
build_and_push_image "da-app" "$WEBAPP_DOCKERFILE_PATH" "$WEBAPP_CONTEXT_PATH" "$AZURE_ENV_IMAGETAG"

echo -e "\nAll Docker images built and pushed successfully with tag: $AZURE_ENV_IMAGETAG"
