#!/bin/bash
#
# Separate post-deployment script: builds the application container images with
# Azure Container Registry remote build (`az acr build`) and points the deployed
# App Services at the images in the deployment's dedicated ACR.
#
# Intended to be run manually AFTER `azd provision` / `azd up`, which creates the
# dedicated ACR, the App Services (on a placeholder image), and the AcrPull role
# assignments. Docker is NOT required locally because images are built remotely.
#
# Flow:
#   1. Resolve deployment values (parameters -> azd env -> environment variables).
#   2. Build each image remotely with `az acr build` and push to the dedicated ACR.
#   3. Update each App Service to use the new ACR image (managed-identity pull).
#   4. Restart the App Services.
#
# Run any existing post-deployment scripts (agents / fabric) AFTER this script.
#
# Usage:
#   acr_build_and_deploy.sh [SUBSCRIPTION_ID] [RESOURCE_GROUP] [ACR_NAME] \
#                           [IMAGE_TAG] [BACKEND_RUNTIME_STACK] [API_APP_NAME] \
#                           [WEB_APP_NAME] [LOGIN_SERVER]
# Any omitted argument is resolved from the azd environment or environment variables.

set -euo pipefail

SUBSCRIPTION_ID="${1:-}"
RESOURCE_GROUP="${2:-}"
ACR_NAME="${3:-}"
IMAGE_TAG="${4:-}"
BACKEND_RUNTIME_STACK="${5:-}"
API_APP_NAME="${6:-}"
WEB_APP_NAME="${7:-}"
LOGIN_SERVER="${8:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ---------------------------------------------------------------------------
# STEP 0: Load values from the azd environment when not passed explicitly.
# ---------------------------------------------------------------------------
declare -A AZD_VALUES
if command -v azd >/dev/null 2>&1; then
    if AZD_OUTPUT="$(azd env get-values 2>/dev/null)"; then
        while IFS= read -r line; do
            if [[ "$line" =~ ^[[:space:]]*([A-Za-z0-9_]+)[[:space:]]*=[[:space:]]*(.*)$ ]]; then
                key="${BASH_REMATCH[1]}"
                val="${BASH_REMATCH[2]}"
                val="${val%\"}"
                val="${val#\"}"
                AZD_VALUES["$key"]="$val"
            fi
        done <<< "$AZD_OUTPUT"
    fi
fi

resolve_value() {
    # $1 = explicit value, remaining args = candidate keys
    local explicit="$1"; shift
    if [[ -n "$explicit" ]]; then echo "$explicit"; return; fi
    local key
    for key in "$@"; do
        if [[ -n "${AZD_VALUES[$key]:-}" ]]; then echo "${AZD_VALUES[$key]}"; return; fi
        if [[ -n "${!key:-}" ]]; then echo "${!key}"; return; fi
    done
    echo ""
}

SUBSCRIPTION_ID="$(resolve_value "$SUBSCRIPTION_ID" AZURE_SUBSCRIPTION_ID)"
RESOURCE_GROUP="$(resolve_value "$RESOURCE_GROUP" AZURE_RESOURCE_GROUP RESOURCE_GROUP_NAME)"
ACR_NAME="$(resolve_value "$ACR_NAME" AZURE_ENV_CONTAINER_REGISTRY_NAME)"
LOGIN_SERVER="$(resolve_value "$LOGIN_SERVER" ACR_LOGIN_SERVER)"
IMAGE_TAG="$(resolve_value "$IMAGE_TAG" AZURE_ENV_IMAGE_TAG)"
BACKEND_RUNTIME_STACK="$(resolve_value "$BACKEND_RUNTIME_STACK" BACKEND_RUNTIME_STACK)"
API_APP_NAME="$(resolve_value "$API_APP_NAME" API_APP_NAME)"
WEB_APP_NAME="$(resolve_value "$WEB_APP_NAME" WEB_APP_NAME)"

IMAGE_TAG="${IMAGE_TAG:-latest_v2}"
BACKEND_RUNTIME_STACK="${BACKEND_RUNTIME_STACK:-python}"
if [[ -z "$LOGIN_SERVER" && -n "$ACR_NAME" ]]; then
    LOGIN_SERVER="${ACR_NAME}.azurecr.io"
fi

# Validate required values.
MISSING=()
[[ -z "$RESOURCE_GROUP" ]] && MISSING+=("RESOURCE_GROUP")
[[ -z "$ACR_NAME" ]]       && MISSING+=("ACR_NAME")
[[ -z "$API_APP_NAME" ]]   && MISSING+=("API_APP_NAME")
[[ -z "$WEB_APP_NAME" ]]   && MISSING+=("WEB_APP_NAME")
if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "Missing required values: ${MISSING[*]}. Pass them as arguments or set the corresponding azd/environment variables." >&2
    exit 1
fi

echo "Resource Group : $RESOURCE_GROUP"
echo "ACR            : $ACR_NAME ($LOGIN_SERVER)"
echo "Image Tag      : $IMAGE_TAG"
echo "Backend Stack  : $BACKEND_RUNTIME_STACK"
echo "API App        : $API_APP_NAME"
echo "Web App        : $WEB_APP_NAME"

# ---------------------------------------------------------------------------
# STEP 1: Ensure Azure login and subscription context.
# ---------------------------------------------------------------------------
if ! az account show >/dev/null 2>&1; then
    echo "Not logged in to Azure. Attempting az login..."
    az login
fi
if [[ -n "$SUBSCRIPTION_ID" ]]; then
    az account set --subscription "$SUBSCRIPTION_ID"
fi

# ---------------------------------------------------------------------------
# STEP 2: Remote build images with `az acr build` (no local Docker required).
# ---------------------------------------------------------------------------
acr_build() {
    local image="$1" dockerfile="$2" context="$3"
    echo -e "\n--- Remote-building ${image}:${IMAGE_TAG} in ACR '${ACR_NAME}' ---"
    az acr build --registry "$ACR_NAME" --image "${image}:${IMAGE_TAG}" --file "$dockerfile" "$context"
}

WEB_CONTEXT="$REPO_ROOT/src/App"
WEB_FILE="$WEB_CONTEXT/WebApp.Dockerfile"
acr_build "da-app" "$WEB_FILE" "$WEB_CONTEXT"

if [[ "$BACKEND_RUNTIME_STACK" == "dotnet" ]]; then
    API_IMAGE="da-api-dotnet"
    API_CONTEXT="$REPO_ROOT/src/api/dotnet"
    API_FILE="$API_CONTEXT/CsApi.Dockerfile"
else
    API_IMAGE="da-api"
    API_CONTEXT="$REPO_ROOT/src/api/python"
    API_FILE="$API_CONTEXT/ApiApp.Dockerfile"
fi
acr_build "$API_IMAGE" "$API_FILE" "$API_CONTEXT"

# ---------------------------------------------------------------------------
# STEP 3: Point App Services at the ACR images (managed-identity pull).
# ---------------------------------------------------------------------------
set_app_image() {
    local app_name="$1" image="$2"
    local image_ref="${LOGIN_SERVER}/${image}:${IMAGE_TAG}"
    echo -e "\n--- Updating App Service '${app_name}' -> ${image_ref} ---"
    az webapp config container set \
        --name "$app_name" \
        --resource-group "$RESOURCE_GROUP" \
        --container-image-name "$image_ref" \
        --container-registry-url "https://${LOGIN_SERVER}" >/dev/null

    az webapp restart --name "$app_name" --resource-group "$RESOURCE_GROUP" >/dev/null
}

set_app_image "$API_APP_NAME" "$API_IMAGE"
set_app_image "$WEB_APP_NAME" "da-app"

echo -e "\nAll images built remotely and App Services updated with tag: $IMAGE_TAG"
echo "You can now run the remaining post-deployment scripts (agents / fabric)."
