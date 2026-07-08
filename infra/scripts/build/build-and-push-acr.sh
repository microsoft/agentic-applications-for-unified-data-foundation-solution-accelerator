#!/bin/bash
# ============================================================================
# Post-deployment: build application container images with ACR remote build
# (`az acr build`) and push them to the deployment-specific Azure Container
# Registry, then repoint the App Services at the freshly built images.
#
# This is a SEPARATE, manual post-deployment step that runs AFTER the
# infrastructure (including the dedicated ACR) has been provisioned.
#
# Flow:
#   1. (Private networking only) Temporarily enable ACR public network access
#      so `az acr build` can upload the build context.
#   2. Remote-build + push each image server-side with `az acr build`
#      (no local Docker required).
#   3. Update each App Service to use the new image, keeping managed-identity
#      (AcrPull) authentication, and restart it.
#   4. (Private networking only) Disable ACR public network access again.
#
# Run any other existing post-deployment scripts separately, after this one.
#
# Requires: Azure CLI (`az`) and an authenticated context (`az login`).
# Does NOT require Docker to be installed locally.
# ============================================================================
set -euo pipefail

# ----------------------------------------------------------------------------
# UTF-8-safe `az` wrapper.
#
# The Windows MSI `az` launcher runs `python.exe -IBm azure.cli`. The -I
# (isolated) flag makes Python ignore PYTHON* env vars (PYTHONUTF8 /
# PYTHONIOENCODING), so on Git Bash the `az acr build` log stream is encoded
# with the console code page (cp1252) and crashes with a UnicodeEncodeError on
# any non-ASCII build output.
#
# We can't override that via env vars, but the `-X utf8` command-line flag is
# NOT blocked by isolated mode. So when the bundled python is found next to the
# az launcher we call it directly with -X utf8; otherwise we fall back to the
# normal `az` on PATH (Linux/macOS, where UTF-8 locales avoid the issue).
# ----------------------------------------------------------------------------
_AZ_PY=""
_az_launcher="$(command -v az || true)"
if [[ -n "$_az_launcher" ]]; then
    _az_dir="$(cd "$(dirname "$_az_launcher")" && pwd)"
    for _cand in "$_az_dir/../python.exe" "$_az_dir/python.exe"; do
        if [[ -f "$_cand" ]]; then _AZ_PY="$_cand"; break; fi
    done
fi

az() {
    if [[ -n "$_AZ_PY" ]]; then
        AZ_INSTALLER=MSI "$_AZ_PY" -X utf8 -Bm azure.cli "$@"
    else
        command az "$@"
    fi
}


# ----------------------------------------------------------------------------
# Argument parsing
# ----------------------------------------------------------------------------
ACR_NAME=""
RESOURCE_GROUP=""
RESOURCE_GROUP_EXPLICIT="false"
SUBSCRIPTION_ID=""
IMAGE_TAG="latest_v2"
API_APP_NAME=""
WEB_APP_NAME=""
BACKEND_RUNTIME_STACK="python"
BACKEND_RUNTIME_EXPLICIT="false"
IMAGE_TAG_EXPLICIT="false"
PRIVATE_NETWORKING="false"
PRIVATE_NETWORKING_EXPLICIT="false"
VERBOSE="false"

usage() {
    cat <<EOF
Usage: build-and-push-acr.sh --resource-group <rg> [options]

Required:
  --resource-group <rg>        Resource group of the deployment

Auto-discovery:
  When --resource-group is given, the ACR name, API/Web App Service names,
  backend runtime, and private-networking state are auto-discovered from that RG
  and the local azd environment is IGNORED. Any other explicit value still wins.
  With NO arguments, values are pulled from the local azd environment
  (azd env get-values), if one is initialized.

Options:
  --acr-name <name>            Target Azure Container Registry name
  --subscription <id>          Azure subscription ID
  --image-tag <tag>            Image tag (default: latest_v2)
  --api-app-name <name>        Backend App Service name to repoint
  --web-app-name <name>        Frontend App Service name to repoint
  --backend-runtime <stack>    python|dotnet (default: auto-detect, else python)
  --private-networking         Toggle ACR public access around the build
  --verbose                    Show full command output (default: only errors)
  -h, --help                   Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --acr-name) ACR_NAME="$2"; shift 2 ;;
        --resource-group) RESOURCE_GROUP="$2"; RESOURCE_GROUP_EXPLICIT="true"; shift 2 ;;
        --subscription) SUBSCRIPTION_ID="$2"; shift 2 ;;
        --image-tag) IMAGE_TAG="$2"; IMAGE_TAG_EXPLICIT="true"; shift 2 ;;
        --api-app-name) API_APP_NAME="$2"; shift 2 ;;
        --web-app-name) WEB_APP_NAME="$2"; shift 2 ;;
        --backend-runtime) BACKEND_RUNTIME_STACK="$2"; BACKEND_RUNTIME_EXPLICIT="true"; shift 2 ;;
        --private-networking) PRIVATE_NETWORKING="true"; PRIVATE_NETWORKING_EXPLICIT="true"; shift ;;
        --verbose) VERBOSE="true"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
    esac
done

# ----------------------------------------------------------------------------
# Fallback: pull any unset values from the local azd environment (if present).
# This ONLY runs when the user did NOT pass --resource-group. If a resource
# group is supplied explicitly, the local azd environment is ignored entirely
# and every value is taken from the CLI args or discovered from that RG.
# Precedence (no explicit RG): explicit CLI arg > azd env > RG-based discovery > default.
# ----------------------------------------------------------------------------
if [[ "$RESOURCE_GROUP_EXPLICIT" == "true" ]]; then
    echo "Resource group provided explicitly - ignoring local azd environment; all inputs will come from '$RESOURCE_GROUP'."
elif command -v azd > /dev/null 2>&1; then
    AZD_VALUES="$(azd env get-values 2>/dev/null || true)"
    if [[ -n "$AZD_VALUES" ]]; then
        azd_get() { echo "$AZD_VALUES" | grep -E "^$1=" | head -n1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }
        [[ -z "$RESOURCE_GROUP" ]]        && RESOURCE_GROUP="$(azd_get RESOURCE_GROUP_NAME)"
        [[ -z "$SUBSCRIPTION_ID" ]]       && SUBSCRIPTION_ID="$(azd_get AZURE_SUBSCRIPTION_ID)"
        [[ -z "$ACR_NAME" ]]              && ACR_NAME="$(azd_get AZURE_ENV_CONTAINER_REGISTRY_NAME)"
        [[ -z "$API_APP_NAME" ]]          && API_APP_NAME="$(azd_get API_APP_NAME)"
        [[ -z "$WEB_APP_NAME" ]]          && WEB_APP_NAME="$(azd_get WEB_APP_NAME)"
        if [[ "$BACKEND_RUNTIME_EXPLICIT" == "false" ]]; then
            azd_runtime="$(azd_get BACKEND_RUNTIME_STACK)"
            [[ -n "$azd_runtime" ]] && BACKEND_RUNTIME_STACK="$azd_runtime"
        fi
        if [[ "$IMAGE_TAG_EXPLICIT" == "false" ]]; then
            azd_tag="$(azd_get AZURE_ENV_IMAGE_TAG)"
            [[ -n "$azd_tag" ]] && IMAGE_TAG="$azd_tag"
        fi
        [[ -n "$RESOURCE_GROUP" ]] && echo "Loaded defaults from azd environment."
    fi
fi

if [[ -z "$RESOURCE_GROUP" ]]; then
    echo "ERROR: --resource-group is required (or run inside an initialized azd environment)." >&2
    usage
    exit 1
fi

# ----------------------------------------------------------------------------
# Resolve paths (script lives in infra/scripts/build -> repo root is ../../..)
# ----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ----------------------------------------------------------------------------
# Command runner: suppress stdout unless --verbose; errors (stderr) always show.
# ----------------------------------------------------------------------------
run() {
    if [[ "$VERBOSE" == "true" ]]; then
        "$@"
    else
        "$@" > /dev/null
    fi
}

# ----------------------------------------------------------------------------
# 1. Ensure Azure login + subscription
# ----------------------------------------------------------------------------
echo ""
echo "=== Step 1/4: Verifying Azure CLI login and discovering deployment ==="
echo "  Resource group ...: $RESOURCE_GROUP"
if ! az account show > /dev/null 2>&1; then
    echo "  Not logged in to Azure. Launching 'az login'..."
    az login
fi
if [[ -n "$SUBSCRIPTION_ID" ]]; then
    echo "  Setting subscription to '$SUBSCRIPTION_ID'..."
    run az account set --subscription "$SUBSCRIPTION_ID"
fi

# ----------------------------------------------------------------------------
# 1b. Auto-discover any values not supplied explicitly, from the resource group
# ----------------------------------------------------------------------------
if [[ -z "$ACR_NAME" ]]; then
    ACR_NAME="$(az acr list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv 2>/dev/null || true)"
    if [[ -z "$ACR_NAME" ]]; then
        echo "ERROR: No container registry found in resource group '$RESOURCE_GROUP'. Pass --acr-name explicitly." >&2
        exit 1
    fi
    echo "  Discovered ACR ....: $ACR_NAME"
fi

if [[ -z "$API_APP_NAME" ]]; then
    dotnet_app="$(az webapp list --resource-group "$RESOURCE_GROUP" --query "[?starts_with(name, 'api-cs-')].name | [0]" -o tsv 2>/dev/null || true)"
    if [[ -n "$dotnet_app" ]]; then
        API_APP_NAME="$dotnet_app"
        BACKEND_RUNTIME_STACK="dotnet"
    else
        API_APP_NAME="$(az webapp list --resource-group "$RESOURCE_GROUP" --query "[?starts_with(name, 'api-') && !starts_with(name, 'api-cs-')].name | [0]" -o tsv 2>/dev/null || true)"
        BACKEND_RUNTIME_STACK="python"
    fi
    if [[ -n "$API_APP_NAME" ]]; then
        echo "  Discovered API app : $API_APP_NAME (runtime: $BACKEND_RUNTIME_STACK)"
    else
        echo "  WARNING: No API App Service (api-* / api-cs-*) found in '$RESOURCE_GROUP'."
    fi
fi

if [[ -z "$WEB_APP_NAME" ]]; then
    WEB_APP_NAME="$(az webapp list --resource-group "$RESOURCE_GROUP" --query "[?starts_with(name, 'app-')].name | [0]" -o tsv 2>/dev/null || true)"
    if [[ -n "$WEB_APP_NAME" ]]; then
        echo "  Discovered Web app : $WEB_APP_NAME"
    else
        echo "  WARNING: No Web App Service (app-*) found in '$RESOURCE_GROUP'."
    fi
fi

# Auto-detect private networking from the ACR public-access state (unless explicit)
if [[ "$PRIVATE_NETWORKING_EXPLICIT" == "false" ]]; then
    acr_public="$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query "publicNetworkAccess" -o tsv 2>/dev/null || true)"
    if [[ "$acr_public" == "Disabled" ]]; then
        PRIVATE_NETWORKING="true"
        echo "  Detected private networking (ACR public access is Disabled)."
    fi
fi

# ----------------------------------------------------------------------------
# Compute derived values now that discovery is complete
# ----------------------------------------------------------------------------
LOGIN_SERVER="${ACR_NAME}.azurecr.io"

# Image definitions (name|context|dockerfile)
IMAGES=("da-app|${REPO_ROOT}/src/App|WebApp.Dockerfile")
if [[ "$BACKEND_RUNTIME_STACK" == "dotnet" ]]; then
    IMAGES+=("da-api-dotnet|${REPO_ROOT}/src/api/dotnet|CsApi.Dockerfile")
    BACKEND_IMAGE="da-api-dotnet"
else
    IMAGES+=("da-api|${REPO_ROOT}/src/api/python|ApiApp.Dockerfile")
    BACKEND_IMAGE="da-api"
fi

echo "  ----------------------------------------------------------"
echo "  Resolved configuration:"
echo "    ACR ..............: $ACR_NAME ($LOGIN_SERVER)"
echo "    Image tag ........: $IMAGE_TAG"
echo "    Backend runtime ..: $BACKEND_RUNTIME_STACK"
echo "    API app ..........: ${API_APP_NAME:-<none>}"
echo "    Web app ..........: ${WEB_APP_NAME:-<none>}"
echo "    Private networking: $PRIVATE_NETWORKING"
echo "    Verbose output ...: $VERBOSE"
echo "  Azure context ready."

# ----------------------------------------------------------------------------
# 2. (Private networking) Temporarily enable ACR public access
# ----------------------------------------------------------------------------
disable_public_access() {
    if [[ "$PRIVATE_NETWORKING" == "true" ]]; then
        echo ""
        echo "=== Cleanup: Re-locking ACR '$ACR_NAME' (disabling public access) ==="
        run az acr update --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" \
            --public-network-access Disabled --default-action Deny
        echo "  ACR public network access disabled again."
    fi
}
trap disable_public_access EXIT

echo ""
if [[ "$PRIVATE_NETWORKING" == "true" ]]; then
    echo "=== Step 2/4: Temporarily opening ACR '$ACR_NAME' for remote build ==="
    echo "  App Services stay private - only the registry is opened for the build context upload."
    run az acr update --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" \
        --public-network-access Enabled --default-action Allow
    echo "  Waiting 30s for network rule propagation..."
    sleep 30
    echo "  ACR public network access temporarily enabled."
else
    echo "=== Step 2/4: Public networking mode - no ACR access toggle needed ==="
fi

# ----------------------------------------------------------------------------
# 3. Remote build + push each image (server-side, no local Docker)
# ----------------------------------------------------------------------------
echo ""
echo "=== Step 3/4: Building ${#IMAGES[@]} image(s) via ACR remote build (no local Docker) ==="
build_index=0
for entry in "${IMAGES[@]}"; do
    build_index=$((build_index + 1))
    IFS='|' read -r image_name context dockerfile <<< "$entry"
    image_ref="${image_name}:${IMAGE_TAG}"
    echo ""
    echo "  [$build_index/${#IMAGES[@]}] Building '$image_ref'"
    echo "        context ...: $context"
    echo "        dockerfile : $dockerfile"
    # Run from within the context so `--file` resolves relative to it (az acr
    # build validates the dockerfile path against the current directory).
    ( cd "$context" && run az acr build \
        --registry "$ACR_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --image "$image_ref" \
        --file "$dockerfile" \
        . )
    echo "  [$build_index/${#IMAGES[@]}] Pushed '${LOGIN_SERVER}/${image_ref}'"
done
echo ""
echo "  All images built and pushed."

# ----------------------------------------------------------------------------
# 4. Update App Services to the newly built images (managed-identity pull)
# ----------------------------------------------------------------------------
echo ""
echo "=== Step 4/4: Repointing App Services to the new images (managed-identity pull) ==="
update_app_service_image() {
    local app_name="$1"
    local image_name="$2"
    if [[ -z "$app_name" ]]; then
        echo "  App name not provided for image '$image_name' - skipping."
        return
    fi
    local full_image="${LOGIN_SERVER}/${image_name}:${IMAGE_TAG}"
    echo ""
    echo "  Updating '$app_name' -> '$full_image'"
    run az webapp config container set \
        --name "$app_name" \
        --resource-group "$RESOURCE_GROUP" \
        --container-image-name "$full_image" \
        --container-registry-url "https://${LOGIN_SERVER}"
    # Ensure the app keeps using its managed identity for the ACR pull.
    echo "  Enforcing managed-identity ACR authentication on '$app_name'..."
    run az resource update \
        --resource-group "$RESOURCE_GROUP" \
        --name "$app_name" \
        --resource-type "Microsoft.Web/sites" \
        --set properties.siteConfig.acrUseManagedIdentityCreds=true
    echo "  Restarting '$app_name'..."
    run az webapp restart --name "$app_name" --resource-group "$RESOURCE_GROUP"
    echo "  '$app_name' updated and restarted."
}

update_app_service_image "$API_APP_NAME" "$BACKEND_IMAGE"
update_app_service_image "$WEB_APP_NAME" "da-app"

echo ""
echo "=== All done! ==="
echo "  Images built in '$ACR_NAME' and App Services repointed to managed-identity pulls."
echo "  Run any remaining post-deployment scripts separately, after this one."
