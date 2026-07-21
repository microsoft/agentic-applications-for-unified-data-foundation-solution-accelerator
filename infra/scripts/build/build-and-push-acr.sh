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
# Print helpers: consistent, colored step banners and status lines.
# ----------------------------------------------------------------------------
SCRIPT_START=$(date +%s)

CY='\033[0;36m'   # Cyan
GR='\033[0;32m'   # Green
YL='\033[0;33m'   # Yellow
WH='\033[1;37m'   # White
DG='\033[0;90m'   # Dark gray
RS='\033[0m'      # Reset

write_step() {
    local number=$1 total=$2 title=$3
    echo ""
    echo -e "${CY}=====================================================================${RS}"
    echo -e "${CY}  Step ${number}/${total}  |  ${title}${RS}"
    echo -e "${CY}=====================================================================${RS}"
}
write_success() { echo -e "${GR}  [OK]  $1${RS}"; }
write_info()    { echo -e "${WH}  >>    $1${RS}"; }
write_warn()    { echo -e "${YL}  [!]   $1${RS}"; }
write_elapsed() {
    local now elapsed mins secs
    now=$(date +%s)
    elapsed=$(( now - SCRIPT_START ))
    mins=$(( elapsed / 60 ))
    secs=$(( elapsed % 60 ))
    echo -e "${DG}  Elapsed: $(printf '%02d:%02d' $mins $secs)${RS}"
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
    write_info "Resource group provided explicitly - Fetching inputs from '$RESOURCE_GROUP'."
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
        [[ -n "$RESOURCE_GROUP" ]] && write_info "Loaded defaults from azd environment."
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
write_step 1 4 "Verify Azure CLI login and discover deployment"
write_info "Resource group : $RESOURCE_GROUP"
if ! az account show > /dev/null 2>&1; then
    write_warn "Not logged in to Azure. Launching 'az login'..."
    az login
fi
if [[ -n "$SUBSCRIPTION_ID" ]]; then
    write_info "Subscription : '$SUBSCRIPTION_ID'"
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
    write_success "Discovered ACR ........: $ACR_NAME"
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
        write_success "Discovered Backend App : $API_APP_NAME (runtime: $BACKEND_RUNTIME_STACK)"
    else
        write_warn "No Backend App Service (api-* / api-cs-*) found in '$RESOURCE_GROUP'."
    fi
fi

if [[ -z "$WEB_APP_NAME" ]]; then
    WEB_APP_NAME="$(az webapp list --resource-group "$RESOURCE_GROUP" --query "[?starts_with(name, 'app-')].name | [0]" -o tsv 2>/dev/null || true)"
    if [[ -n "$WEB_APP_NAME" ]]; then
        write_success "Discovered Frontend App : $WEB_APP_NAME"
    else
        write_warn "No Frontend App Service (app-*) found in '$RESOURCE_GROUP'."
    fi
fi

# Auto-detect private networking from the ACR public-access state (unless explicit)
if [[ "$PRIVATE_NETWORKING_EXPLICIT" == "false" ]]; then
    acr_public="$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query "publicNetworkAccess" -o tsv 2>/dev/null || true)"
    if [[ "$acr_public" == "Disabled" ]]; then
        PRIVATE_NETWORKING="true"
        write_info "Detected private networking (ACR public access is Disabled)."
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
echo "    Backend app ......: ${API_APP_NAME:-<none>}"
echo "    Frontend app .....: ${WEB_APP_NAME:-<none>}"
echo "    Private networking: $PRIVATE_NETWORKING"
echo "    Verbose output ...: $VERBOSE"
write_elapsed

# ----------------------------------------------------------------------------
# 2. (Private networking) Temporarily enable ACR public access
# ----------------------------------------------------------------------------
disable_public_access() {
    if [[ "$PRIVATE_NETWORKING" == "true" ]]; then
        echo ""
        echo -e "${CY}====================================================${RS}"
        echo -e "${CY}  Cleanup  | Disabling Public Access '$ACR_NAME'${RS}"
        echo -e "${CY}====================================================${RS}"
        run az acr update --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" \
            --public-network-enabled false --default-action Deny
        write_success "ACR public network access disabled again."
        # Restore the export policy to its locked-down (disabled) state. This can
        # only be disabled once public network access is off (done above).
        run az acr update --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" \
            --allow-exports false
        write_success "ACR export policy re-disabled."
    fi
}
trap disable_public_access EXIT

echo ""
if [[ "$PRIVATE_NETWORKING" == "true" ]]; then
    write_step 2 4 "Temporarily opening ACR '$ACR_NAME' for remote build"
    write_info "App Services stay private - only the registry is opened for the build context upload."
    # Public network access cannot be enabled while the export policy is disabled,
    # so enable exports first, then open the public endpoint.
    run az acr update --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" \
        --allow-exports true
    run az acr update --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" \
        --public-network-enabled true --default-action Allow
    write_warn "Waiting 30s for network rule propagation..."
    sleep 30
    write_success "ACR public network access temporarily enabled."
else
    write_step 2 4 "Public networking mode - Skipping ACR public access"
fi

# ----------------------------------------------------------------------------
# 3. Remote build + push each image (server-side, no local Docker)
# ----------------------------------------------------------------------------
write_step 3 4 "Building ${#IMAGES[@]} Image(s) via ACR Remote Build"
build_index=0
for entry in "${IMAGES[@]}"; do
    build_index=$((build_index + 1))
    IFS='|' read -r image_name context dockerfile <<< "$entry"
    image_ref="${image_name}:${IMAGE_TAG}"
    echo ""
    echo -e "${WH}  [$build_index/${#IMAGES[@]}] ${image_name}${RS}"
    write_info "  context    : $context"
    write_info "  dockerfile : $dockerfile"
    write_info "  image ref  : ${LOGIN_SERVER}/${image_ref}"
    write_info "  Submitting Remote build to ACR '$ACR_NAME'"
    # Run from within the context so `--file` resolves relative to it (az acr
    # build validates the dockerfile path against the current directory).
    ( cd "$context" && run az acr build \
        --registry "$ACR_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --image "$image_ref" \
        --file "$dockerfile" \
        --no-logs \
        . )
    write_success "[$build_index/${#IMAGES[@]}] Pushed '${LOGIN_SERVER}/${image_ref}'"
done
write_success "All images built and pushed."
write_elapsed

# ----------------------------------------------------------------------------
# 4. Update App Services to the newly built images (managed-identity pull)
# ----------------------------------------------------------------------------
write_step 4 4 "Repointing App Services to the New Images"
update_app_service_image() {
    local app_name="$1"
    local image_name="$2"
    if [[ -z "$app_name" ]]; then
        write_warn "App name not provided for image '$image_name' - skipping."
        return
    fi
    local full_image="${LOGIN_SERVER}/${image_name}:${IMAGE_TAG}"
    echo ""
    write_info "Updating '$app_name' with '$full_image'"
    run az webapp config container set \
        --name "$app_name" \
        --resource-group "$RESOURCE_GROUP" \
        --container-image-name "$full_image" \
        --container-registry-url "https://${LOGIN_SERVER}" \
        --only-show-errors
    # Ensure the app keeps using its managed identity for the ACR pull.
    write_info "Enforcing managed-identity ACR authentication on '$app_name'..."
    run az resource update \
        --resource-group "$RESOURCE_GROUP" \
        --name "$app_name" \
        --resource-type "Microsoft.Web/sites" \
        --set properties.siteConfig.acrUseManagedIdentityCreds=true
    write_info "Restarting '$app_name'..."
    run az webapp restart --name "$app_name" --resource-group "$RESOURCE_GROUP"
    write_success "'$app_name' Updated and Restarted."
}

update_app_service_image "$API_APP_NAME" "$BACKEND_IMAGE"
update_app_service_image "$WEB_APP_NAME" "da-app"

echo ""
echo -e "${GR}====================================================${RS}"
echo -e "${GR}  All Steps have been completed!${RS}"
echo -e "${GR}====================================================${RS}"
write_success "Images built in '$ACR_NAME' and App Services are pointed to the new images."
write_elapsed
