<#
.SYNOPSIS
    Separate post-deployment script: builds the application container images with
    Azure Container Registry remote build (`az acr build`) and points the deployed
    App Services at the images in the deployment's dedicated ACR.

.DESCRIPTION
    This script is intended to be run manually AFTER `azd provision` / `azd up`
    (which creates the dedicated ACR, App Services on a placeholder image, and the
    AcrPull role assignments). It does NOT require Docker to be installed locally,
    because images are built remotely inside ACR.

    Flow:
      1. Resolve deployment values (from parameters, azd env, or environment).
      2. Build each image remotely with `az acr build` and push to the dedicated ACR.
      3. Update each App Service to use the new ACR image (managed-identity pull).
      4. Restart the App Services.

    Run any existing post-deployment scripts (agents / fabric) AFTER this script.

.PARAMETER SubscriptionId   Azure subscription ID.
.PARAMETER ResourceGroup    Resource group containing the deployment.
.PARAMETER AcrName          Dedicated Azure Container Registry name (not the login server).
.PARAMETER LoginServer      ACR login server (e.g. myacr.azurecr.io). Defaults to <AcrName>.azurecr.io.
.PARAMETER ImageTag         Image tag to build/deploy (default: latest_v2).
.PARAMETER BackendRuntimeStack  'python' or 'dotnet' (default: python).
.PARAMETER ApiAppName       Backend API App Service name.
.PARAMETER WebAppName       Frontend web App Service name.
#>
param(
    [string]$SubscriptionId,
    [string]$ResourceGroup,
    [string]$AcrName,
    [string]$LoginServer,
    [string]$ImageTag,
    [ValidateSet('python', 'dotnet')]
    [string]$BackendRuntimeStack,
    [string]$ApiAppName,
    [string]$WebAppName
)

$ErrorActionPreference = 'Stop'

# Resolve the repository root (two levels up from infra/scripts).
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir '..\..')

# ---------------------------------------------------------------------------
# STEP 0: Load values from the azd environment when not passed explicitly.
# ---------------------------------------------------------------------------
$azdValues = @{}
try {
    $azdOutput = azd env get-values 2>$null
    if ($LASTEXITCODE -eq 0 -and $azdOutput) {
        foreach ($line in $azdOutput) {
            if ($line -match '^\s*([A-Za-z0-9_]+)\s*=\s*"?(.*?)"?\s*$') {
                $azdValues[$Matches[1]] = $Matches[2]
            }
        }
    }
}
catch {
    Write-Host "azd environment not available; relying on parameters/environment variables."
}

function Resolve-Value {
    param([string]$Explicit, [string[]]$Keys, [string]$Default = '')
    if (-not [string]::IsNullOrWhiteSpace($Explicit)) { return $Explicit }
    foreach ($k in $Keys) {
        if ($azdValues.ContainsKey($k) -and -not [string]::IsNullOrWhiteSpace($azdValues[$k])) { return $azdValues[$k] }
        $envVal = [System.Environment]::GetEnvironmentVariable($k)
        if (-not [string]::IsNullOrWhiteSpace($envVal)) { return $envVal }
    }
    return $Default
}

$SubscriptionId      = Resolve-Value $SubscriptionId      @('AZURE_SUBSCRIPTION_ID')
$ResourceGroup       = Resolve-Value $ResourceGroup       @('AZURE_RESOURCE_GROUP', 'RESOURCE_GROUP_NAME')
$AcrName             = Resolve-Value $AcrName             @('AZURE_ENV_CONTAINER_REGISTRY_NAME')
$LoginServer         = Resolve-Value $LoginServer         @('ACR_LOGIN_SERVER')
$ImageTag            = Resolve-Value $ImageTag            @('AZURE_ENV_IMAGE_TAG') 'latest_v2'
$BackendRuntimeStack = Resolve-Value $BackendRuntimeStack @('BACKEND_RUNTIME_STACK') 'python'
$ApiAppName          = Resolve-Value $ApiAppName          @('API_APP_NAME')
$WebAppName          = Resolve-Value $WebAppName          @('WEB_APP_NAME')

if ([string]::IsNullOrWhiteSpace($LoginServer) -and -not [string]::IsNullOrWhiteSpace($AcrName)) {
    $LoginServer = "$AcrName.azurecr.io"
}

# Validate required values.
$missing = @()
if ([string]::IsNullOrWhiteSpace($ResourceGroup)) { $missing += 'ResourceGroup' }
if ([string]::IsNullOrWhiteSpace($AcrName))        { $missing += 'AcrName' }
if ([string]::IsNullOrWhiteSpace($ApiAppName))     { $missing += 'ApiAppName' }
if ([string]::IsNullOrWhiteSpace($WebAppName))     { $missing += 'WebAppName' }
if ($missing.Count -gt 0) {
    Write-Error "Missing required values: $($missing -join ', '). Pass them as parameters or set the corresponding azd/environment variables."
    exit 1
}

Write-Host "Resource Group : $ResourceGroup"
Write-Host "ACR            : $AcrName ($LoginServer)"
Write-Host "Image Tag      : $ImageTag"
Write-Host "Backend Stack  : $BackendRuntimeStack"
Write-Host "API App        : $ApiAppName"
Write-Host "Web App        : $WebAppName"

# ---------------------------------------------------------------------------
# STEP 1: Ensure Azure login and subscription context.
# ---------------------------------------------------------------------------
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "Not logged in. Attempting az login..."
    az login | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error "Azure login failed."; exit 1 }
}
if (-not [string]::IsNullOrWhiteSpace($SubscriptionId)) {
    az account set --subscription "$SubscriptionId"
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to set Azure subscription."; exit 1 }
}

# ---------------------------------------------------------------------------
# STEP 2: Remote build images with `az acr build` (no local Docker required).
# ---------------------------------------------------------------------------
function Invoke-AcrBuild {
    param([string]$Image, [string]$Dockerfile, [string]$Context)
    Write-Host "`n--- Remote-building $Image`:$ImageTag in ACR '$AcrName' ---"
    az acr build --registry $AcrName --image "$($Image):$ImageTag" --file $Dockerfile $Context
    if ($LASTEXITCODE -ne 0) { Write-Error "az acr build failed for image: $Image"; exit 1 }
}

$WebContext  = Join-Path $RepoRoot 'src\App'
$WebFile     = Join-Path $WebContext 'WebApp.Dockerfile'

Invoke-AcrBuild 'da-app' $WebFile $WebContext

if ($BackendRuntimeStack -eq 'dotnet') {
    $ApiImage   = 'da-api-dotnet'
    $ApiContext = Join-Path $RepoRoot 'src\api\dotnet'
    $ApiFile    = Join-Path $ApiContext 'CsApi.Dockerfile'
}
else {
    $ApiImage   = 'da-api'
    $ApiContext = Join-Path $RepoRoot 'src\api\python'
    $ApiFile    = Join-Path $ApiContext 'ApiApp.Dockerfile'
}
Invoke-AcrBuild $ApiImage $ApiFile $ApiContext

# ---------------------------------------------------------------------------
# STEP 3: Point App Services at the ACR images (managed-identity pull).
# ---------------------------------------------------------------------------
function Set-AppImage {
    param([string]$AppName, [string]$Image)
    $imageRef = "$LoginServer/$($Image):$ImageTag"
    Write-Host "`n--- Updating App Service '$AppName' -> $imageRef ---"
    az webapp config container set `
        --name $AppName `
        --resource-group $ResourceGroup `
        --container-image-name $imageRef `
        --container-registry-url "https://$LoginServer" | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to update container image for $AppName"; exit 1 }

    az webapp restart --name $AppName --resource-group $ResourceGroup | Out-Null
}

Set-AppImage $ApiAppName $ApiImage
Set-AppImage $WebAppName 'da-app'

Write-Host "`nAll images built remotely and App Services updated with tag: $ImageTag"
Write-Host "You can now run the remaining post-deployment scripts (agents / fabric)."
