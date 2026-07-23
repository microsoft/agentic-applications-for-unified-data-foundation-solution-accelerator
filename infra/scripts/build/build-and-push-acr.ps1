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

[CmdletBinding()]
param (
    [string]$AcrName,
    [string]$ResourceGroup,
    [string]$Subscription,
    [string]$ImageTag,
    [string]$ApiAppName,
    [string]$WebAppName,
    [ValidateSet("python", "dotnet")]
    [string]$BackendRuntime,
    [switch]$PrivateNetworking,
    [switch]$VerboseOutput,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$ScriptStart = [datetime]::UtcNow
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# ----------------------------------------------------------------------------
# Print helpers: consistent, colored step banners and status lines.
# ----------------------------------------------------------------------------
function Write-Step {
    param([int]$Number, [int]$Total, [string]$Title)
    Write-Host ""
    Write-Host "=====================================================================" -ForegroundColor Cyan
    Write-Host "  Step $Number/$Total  |  $Title" -ForegroundColor Cyan
    Write-Host "=====================================================================" -ForegroundColor Cyan
}
function Write-Success { param([string]$Msg) Write-Host "  [OK]  $Msg" -ForegroundColor Green }
function Write-Info    { param([string]$Msg) Write-Host "  >>    $Msg" -ForegroundColor White }
function Write-Warn    { param([string]$Msg) Write-Host "  [!]   $Msg" -ForegroundColor Yellow }
function Write-Elapsed {
    $elapsed = [datetime]::UtcNow - $ScriptStart
    Write-Host ("  Elapsed: {0:mm\:ss}" -f $elapsed) -ForegroundColor DarkGray
}

function Show-Usage {
    @"
Usage: build-and-push-acr.ps1 -ResourceGroup <rg> [options]

Required:
  -ResourceGroup <rg>          Resource group of the deployment

Auto-discovery:
  When -ResourceGroup is given, the ACR name, API/Web App Service names,
  backend runtime, and private-networking state are auto-discovered from that RG
  and the local azd environment is IGNORED. Any other explicit value still wins.
  With NO arguments, values are pulled from the local azd environment
  (azd env get-values), if one is initialized.

Options:
  -AcrName <name>              Target Azure Container Registry name
  -Subscription <id>           Azure subscription ID
  -ImageTag <tag>              Image tag (default: latest_v2)
  -ApiAppName <name>           Backend App Service name to repoint
  -WebAppName <name>           Frontend App Service name to repoint
  -BackendRuntime <stack>      python|dotnet (default: auto-detect, else python)
  -PrivateNetworking           Toggle ACR public access around the build
  -VerboseOutput               Show full command output (default: only errors)
  -Help                        Show this help
"@
}

if ($Help) {
    Show-Usage
    exit 0
}

# ----------------------------------------------------------------------------
# Track which values were supplied explicitly (explicit CLI arg always wins).
# ----------------------------------------------------------------------------
$ResourceGroupExplicit    = $PSBoundParameters.ContainsKey('ResourceGroup')
$ImageTagExplicit         = $PSBoundParameters.ContainsKey('ImageTag')
$BackendRuntimeExplicit   = $PSBoundParameters.ContainsKey('BackendRuntime')
$PrivateNetworkingExplicit = $PSBoundParameters.ContainsKey('PrivateNetworking')

if (-not $ImageTag)       { $ImageTag = "latest_v2" }
if (-not $BackendRuntime) { $BackendRuntime = "python" }
$PrivateNetworkingEnabled = [bool]$PrivateNetworking

# ----------------------------------------------------------------------------
# Fallback: pull any unset values from the local azd environment (if present).
# This ONLY runs when the user did NOT pass -ResourceGroup. If a resource
# group is supplied explicitly, the local azd environment is ignored entirely
# and every value is taken from the CLI args or discovered from that RG.
# Precedence (no explicit RG): explicit CLI arg > azd env > RG-based discovery > default.
# ----------------------------------------------------------------------------
if ($ResourceGroupExplicit) {
    Write-Info "Resource group provided explicitly - Fetching Inputs From '$ResourceGroup'."
}
elseif (Get-Command azd -ErrorAction SilentlyContinue) {
    $azdValues = & azd env get-values 2>$null
    if ($azdValues) {
        $azdMap = @{}
        foreach ($line in $azdValues) {
            if ($line -match '^\s*([^=]+)=(.*)$') {
                $azdMap[$Matches[1].Trim()] = $Matches[2].Trim().Trim('"')
            }
        }
        function Get-AzdValue([string]$key) { if ($azdMap.ContainsKey($key)) { $azdMap[$key] } else { "" } }

        if (-not $ResourceGroup) { $ResourceGroup = Get-AzdValue "RESOURCE_GROUP_NAME" }
        if (-not $Subscription)  { $Subscription  = Get-AzdValue "AZURE_SUBSCRIPTION_ID" }
        if (-not $AcrName)       { $AcrName       = Get-AzdValue "AZURE_ENV_CONTAINER_REGISTRY_NAME" }
        if (-not $ApiAppName)    { $ApiAppName    = Get-AzdValue "API_APP_NAME" }
        if (-not $WebAppName)    { $WebAppName    = Get-AzdValue "WEB_APP_NAME" }
        if (-not $BackendRuntimeExplicit) {
            $azdRuntime = Get-AzdValue "BACKEND_RUNTIME_STACK"
            if ($azdRuntime) { $BackendRuntime = $azdRuntime }
        }
        if (-not $ImageTagExplicit) {
            $azdTag = Get-AzdValue "AZURE_ENV_IMAGE_TAG"
            if ($azdTag) { $ImageTag = $azdTag }
        }
        if ($ResourceGroup) { Write-Info "Loaded defaults from azd environment." }
    }
}

if (-not $ResourceGroup) {
    Write-Error "-ResourceGroup is required (or run inside an initialized azd environment)."
    Show-Usage
    exit 1
}

# ----------------------------------------------------------------------------
# Resolve paths (script lives in infra/scripts/build -> repo root is ../../..)
# ----------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path

# ----------------------------------------------------------------------------
# Command runner: suppress stdout unless -VerboseOutput; errors always show.
# ----------------------------------------------------------------------------
function Invoke-Run {
    param([Parameter(Mandatory)][scriptblock]$Command)
    if ($VerboseOutput) {
        & $Command
    }
    else {
        & $Command | Out-Null
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE."
    }
}

# ----------------------------------------------------------------------------
# 1. Ensure Azure login + subscription
# ----------------------------------------------------------------------------
Write-Step 1 4 "Verify Azure CLI login and discover deployment"
Write-Info "Resource group : $ResourceGroup"
az account show 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Not logged in to Azure. Launching 'az login'..."
    az login | Out-Null
}
if ($Subscription) {
    Write-Info "Subscription : '$Subscription'"
    Invoke-Run { az account set --subscription $Subscription }
}

# ----------------------------------------------------------------------------
# 1b. Auto-discover any values not supplied explicitly, from the resource group
# ----------------------------------------------------------------------------
if (-not $AcrName) {
    $AcrName = az acr list --resource-group $ResourceGroup --query "[0].name" -o tsv 2>$null
    if (-not $AcrName) {
        Write-Error "ERROR: No Container Registry Found In Resource Group '$ResourceGroup'. Pass -AcrName explicitly."
        exit 1
    }
    Write-Success "Discovered ACR ........: $AcrName"
}

if (-not $ApiAppName) {
    $dotnetApp = az webapp list --resource-group $ResourceGroup --query "[?starts_with(name, 'api-cs-')].name | [0]" -o tsv 2>$null
    if ($dotnetApp) {
        $ApiAppName = $dotnetApp
        $BackendRuntime = "dotnet"
    }
    else {
        $ApiAppName = az webapp list --resource-group $ResourceGroup --query "[?starts_with(name, 'api-') && !starts_with(name, 'api-cs-')].name | [0]" -o tsv 2>$null
        $BackendRuntime = "python"
    }
    if ($ApiAppName) {
        Write-Success "Discovered Backend App : $ApiAppName (runtime: $BackendRuntime)"
    }
    else {
        Write-Warn "No Backend App Service (api-* / api-cs-*) found in '$ResourceGroup'."
    }
}

if (-not $WebAppName) {
    $WebAppName = az webapp list --resource-group $ResourceGroup --query "[?starts_with(name, 'app-')].name | [0]" -o tsv 2>$null
    if ($WebAppName) {
        Write-Success "Discovered Frontend App : $WebAppName"
    }
    else {
        Write-Warn "No Frontend App Service (app-*) found in '$ResourceGroup'."
    }
}

# Auto-detect private networking from the ACR public-access state (unless explicit)
if (-not $PrivateNetworkingExplicit) {
    $acrPublic = az acr show --name $AcrName --resource-group $ResourceGroup --query "publicNetworkAccess" -o tsv 2>$null
    if ($acrPublic -eq "Disabled") {
        $PrivateNetworkingEnabled = $true
        Write-Info "Detected private networking (ACR public access is Disabled)."
    }
}

# ----------------------------------------------------------------------------
# Compute derived values now that discovery is complete
# ----------------------------------------------------------------------------
$LoginServer = "$AcrName.azurecr.io"

# Image definitions (name|context|dockerfile)
$Images = @(
    [pscustomobject]@{ Name = "da-app"; Context = "$RepoRoot/src/App"; Dockerfile = "WebApp.Dockerfile" }
)
if ($BackendRuntime -eq "dotnet") {
    $Images += [pscustomobject]@{ Name = "da-api-dotnet"; Context = "$RepoRoot/src/api/dotnet"; Dockerfile = "CsApi.Dockerfile" }
    $BackendImage = "da-api-dotnet"
}
else {
    $Images += [pscustomobject]@{ Name = "da-api"; Context = "$RepoRoot/src/api/python"; Dockerfile = "ApiApp.Dockerfile" }
    $BackendImage = "da-api"
}

$apiAppDisplay = if ($ApiAppName) { $ApiAppName } else { "<none>" }
$webAppDisplay = if ($WebAppName) { $WebAppName } else { "<none>" }

Write-Host "  ----------------------------------------------------------"
Write-Host "  Resolved configuration:"
Write-Host "    ACR ..............: $AcrName ($LoginServer)"
Write-Host "    Image tag ........: $ImageTag"
Write-Host "    Backend runtime ..: $BackendRuntime"
Write-Host "    Backend app ......: $apiAppDisplay"
Write-Host "    Frontend app .....: $webAppDisplay"
Write-Host "    Private networking: $PrivateNetworkingEnabled"
Write-Host "    Verbose output ...: $([bool]$VerboseOutput)"
Write-Elapsed

# ----------------------------------------------------------------------------
# Cleanup: (Private networking) re-lock ACR on exit
# ----------------------------------------------------------------------------
function Disable-PublicAccess {
    if ($PrivateNetworkingEnabled) {
        Write-Host ""
        Write-Host "====================================================" -ForegroundColor Cyan
        Write-Host "  Cleanup  | Disabling Public Access '$AcrName'" -ForegroundColor Cyan
        Write-Host "====================================================" -ForegroundColor Cyan
        Invoke-Run { az acr update --name $AcrName --resource-group $ResourceGroup `
                --public-network-enabled false --default-action Deny }
        Write-Success "ACR public network access disabled again."
        # Restore the export policy to its locked-down (disabled) state. This can
        # only be disabled once public network access is off (done above).
        Invoke-Run { az acr update --name $AcrName --resource-group $ResourceGroup `
                --allow-exports false }
        Write-Success "ACR export policy re-disabled."
    }
}

try {
    # ------------------------------------------------------------------------
    # 2. (Private networking) Temporarily enable ACR public access
    # ------------------------------------------------------------------------
    if ($PrivateNetworkingEnabled) {
        Write-Step 2 4 "Temporarily opening ACR '$AcrName' for remote build"
        Write-Info "App Services stay private - only the registry is opened for the build context upload."
        # Public network access cannot be enabled while the export policy is disabled,
        # so enable exports first, then open the public endpoint.
        Invoke-Run { az acr update --name $AcrName --resource-group $ResourceGroup `
                --allow-exports true }
        Invoke-Run { az acr update --name $AcrName --resource-group $ResourceGroup `
                --public-network-enabled true --default-action Allow }
        Write-Warn "Waiting 30s for network rule propagation..."
        Start-Sleep -Seconds 30
        Write-Success "ACR public network access temporarily enabled."
    }
    else {
        Write-Step 2 4 "Public networking mode - Skipping ACR public access"
    }

    # ------------------------------------------------------------------------
    # 3. Remote build + push each image (server-side, no local Docker)
    # ------------------------------------------------------------------------
    Write-Step 3 4 "Building $($Images.Count) Image(s) via ACR Remote Build"
    $buildIndex = 0
    foreach ($entry in $Images) {
        $buildIndex++
        $imageRef = "$($entry.Name):$ImageTag"
        Write-Host ""
        Write-Host "  [$buildIndex/$($Images.Count)] $($entry.Name)" -ForegroundColor White
        Write-Info "  context ...: $($entry.Context)"
        Write-Info "  dockerfile : $($entry.Dockerfile)"
        Write-Info "  image ref ..: $LoginServer/$imageRef"
        Write-Info "  Submitting Remote build to ACR '$AcrName'"
        Push-Location $entry.Context
        try {
            Invoke-Run { az acr build `
                    --registry $AcrName `
                    --resource-group $ResourceGroup `
                    --image $imageRef `
                    --file $entry.Dockerfile `
                    --no-logs `
                    . }
        }
        finally {
            Pop-Location
        }
        Write-Success "[$buildIndex/$($Images.Count)] Pushed '$LoginServer/$imageRef'"
    }
    Write-Success "All images built and pushed."
    Write-Elapsed

    # ------------------------------------------------------------------------
    # 4. Update App Services to the newly built images (managed-identity pull)
    # ------------------------------------------------------------------------
    Write-Step 4 4 "Repointing App Services to the New Images"
    function Update-AppServiceImage {
        param(
            [string]$AppName,
            [string]$ImageName
        )
        if (-not $AppName) {
            Write-Warn "App name not provided for image '$ImageName' - skipping."
            return
        }
        $fullImage = "$LoginServer/$($ImageName):$ImageTag"
        Write-Host ""
        Write-Info "Updating '$AppName' with '$fullImage'"
        Invoke-Run { az webapp config container set `
                --name $AppName `
                --resource-group $ResourceGroup `
                --container-image-name $fullImage `
                --container-registry-url "https://$LoginServer" `
                --only-show-errors }
        # Ensure the app keeps using its managed identity for the ACR pull.
        Write-Info "Enforcing managed-identity ACR authentication on '$AppName'..."
        Invoke-Run { az resource update `
                --resource-group $ResourceGroup `
                --name $AppName `
                --resource-type "Microsoft.Web/sites" `
                --set properties.siteConfig.acrUseManagedIdentityCreds=true }
        Write-Info "Restarting '$AppName'..."
        Invoke-Run { az webapp restart --name $AppName --resource-group $ResourceGroup }
        Write-Success "'$AppName' Updated and Restarted."
    }

    Update-AppServiceImage -AppName $ApiAppName -ImageName $BackendImage
    Update-AppServiceImage -AppName $WebAppName -ImageName "da-app"

    Write-Host ""
    Write-Host "====================================================" -ForegroundColor Green
    Write-Host "  All Steps have been completed!" -ForegroundColor Green
    Write-Host "====================================================" -ForegroundColor Green
    Write-Success "Images built in '$AcrName' and App Services are pointed to the new images."
    Write-Elapsed
}
finally {
    Disable-PublicAccess
}
