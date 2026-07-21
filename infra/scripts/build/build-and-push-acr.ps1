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

# ----------------------------------------------------------------------------
# UTF-8-safe `az` wrapper.
#
# The Windows MSI `az.cmd` launcher runs Python in isolated mode, which ignores
# PYTHON* environment variables and leaves log streaming on the active console
# code page (commonly cp1252). `az acr build` can then crash while writing
# non-ASCII build output. When we can locate the bundled Python next to the az
# launcher, call Azure CLI directly with `-X utf8` to force UTF-8 output.
# ----------------------------------------------------------------------------
$Script:AzPython = $null
$AzCommand = Get-Command az -ErrorAction SilentlyContinue
if ($AzCommand) {
    $AzDir = Split-Path -Parent $AzCommand.Source
    foreach ($Candidate in @(
        (Join-Path $AzDir '..\python.exe'),
        (Join-Path $AzDir 'python.exe')
    )) {
        try {
            $ResolvedCandidate = (Resolve-Path $Candidate -ErrorAction Stop).Path
            if (Test-Path $ResolvedCandidate -PathType Leaf) {
                $Script:AzPython = $ResolvedCandidate
                break
            }
        }
        catch {
        }
    }
}

function Invoke-AzCli {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    if ($Script:AzPython) {
        & $Script:AzPython -X utf8 -Bm azure.cli @Arguments
    }
    else {
        & $AzCommand.Source @Arguments
    }
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
    Write-Host "Resource group provided explicitly - ignoring local azd environment; all inputs will come from '$ResourceGroup'."
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
        if ($ResourceGroup) { Write-Host "Loaded defaults from azd environment." }
    }
}

if (-not $ResourceGroup) {
    Write-Error "ERROR: -ResourceGroup is required (or run inside an initialized azd environment)."
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
Write-Host ""
Write-Host "=== Step 1/4: Verifying Azure CLI login and discovering deployment ==="
Write-Host "  Resource group ...: $ResourceGroup"
Invoke-AzCli @('account', 'show') 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Not logged in to Azure. Launching 'az login'..."
    Invoke-AzCli @('login') | Out-Null
}
if ($Subscription) {
    Write-Host "  Setting subscription to '$Subscription'..."
    Invoke-Run { Invoke-AzCli @('account', 'set', '--subscription', $Subscription) }
}

# ----------------------------------------------------------------------------
# 1b. Auto-discover any values not supplied explicitly, from the resource group
# ----------------------------------------------------------------------------
if (-not $AcrName) {
    $AcrName = Invoke-AzCli @('acr', 'list', '--resource-group', $ResourceGroup, '--query', '[0].name', '-o', 'tsv') 2>$null
    if (-not $AcrName) {
        Write-Error "ERROR: No container registry found in resource group '$ResourceGroup'. Pass -AcrName explicitly."
        exit 1
    }
    Write-Host "  Discovered ACR ....: $AcrName"
}

if (-not $ApiAppName) {
    $dotnetApp = Invoke-AzCli @('webapp', 'list', '--resource-group', $ResourceGroup, '--query', "[?starts_with(name, 'api-cs-')].name | [0]", '-o', 'tsv') 2>$null
    if ($dotnetApp) {
        $ApiAppName = $dotnetApp
        $BackendRuntime = "dotnet"
    }
    else {
        $ApiAppName = Invoke-AzCli @('webapp', 'list', '--resource-group', $ResourceGroup, '--query', "[?starts_with(name, 'api-') && !starts_with(name, 'api-cs-')].name | [0]", '-o', 'tsv') 2>$null
        $BackendRuntime = "python"
    }
    if ($ApiAppName) {
        Write-Host "  Discovered API app : $ApiAppName (runtime: $BackendRuntime)"
    }
    else {
        Write-Host "  WARNING: No API App Service (api-* / api-cs-*) found in '$ResourceGroup'."
    }
}

if (-not $WebAppName) {
    $WebAppName = Invoke-AzCli @('webapp', 'list', '--resource-group', $ResourceGroup, '--query', "[?starts_with(name, 'app-')].name | [0]", '-o', 'tsv') 2>$null
    if ($WebAppName) {
        Write-Host "  Discovered Web app : $WebAppName"
    }
    else {
        Write-Host "  WARNING: No Web App Service (app-*) found in '$ResourceGroup'."
    }
}

# Auto-detect private networking from the ACR public-access state (unless explicit)
if (-not $PrivateNetworkingExplicit) {
    $acrPublic = Invoke-AzCli @('acr', 'show', '--name', $AcrName, '--resource-group', $ResourceGroup, '--query', 'publicNetworkAccess', '-o', 'tsv') 2>$null
    if ($acrPublic -eq "Disabled") {
        $PrivateNetworkingEnabled = $true
        Write-Host "  Detected private networking (ACR public access is Disabled)."
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
Write-Host "    API app ..........: $apiAppDisplay"
Write-Host "    Web app ..........: $webAppDisplay"
Write-Host "    Private networking: $PrivateNetworkingEnabled"
Write-Host "    Verbose output ...: $([bool]$VerboseOutput)"
Write-Host "  Azure context ready."

# ----------------------------------------------------------------------------
# Cleanup: (Private networking) re-lock ACR on exit
# ----------------------------------------------------------------------------
function Disable-PublicAccess {
    if ($PrivateNetworkingEnabled) {
        Write-Host ""
        Write-Host "=== Cleanup: Re-locking ACR '$AcrName' (disabling public access) ==="
    Invoke-Run { Invoke-AzCli @('acr', 'update', '--name', $AcrName, '--resource-group', $ResourceGroup, '--public-network-enabled', 'false', '--default-action', 'Deny') }
        Write-Host "  ACR public network access disabled again."
        # Restore the export policy to its locked-down (disabled) state. This can
        # only be disabled once public network access is off (done above).
    Invoke-Run { Invoke-AzCli @('acr', 'update', '--name', $AcrName, '--resource-group', $ResourceGroup, '--allow-exports', 'false') }
        Write-Host "  ACR export policy re-disabled."
    }
}

try {
    # ------------------------------------------------------------------------
    # 2. (Private networking) Temporarily enable ACR public access
    # ------------------------------------------------------------------------
    Write-Host ""
    if ($PrivateNetworkingEnabled) {
        Write-Host "=== Step 2/4: Temporarily opening ACR '$AcrName' for remote build ==="
        Write-Host "  App Services stay private - only the registry is opened for the build context upload."
        # Public network access cannot be enabled while the export policy is disabled,
        # so enable exports first, then open the public endpoint.
        Invoke-Run { Invoke-AzCli @('acr', 'update', '--name', $AcrName, '--resource-group', $ResourceGroup, '--allow-exports', 'true') }
        Invoke-Run { Invoke-AzCli @('acr', 'update', '--name', $AcrName, '--resource-group', $ResourceGroup, '--public-network-enabled', 'true', '--default-action', 'Allow') }
        Write-Host "  Waiting 30s for network rule propagation..."
        Start-Sleep -Seconds 30
        Write-Host "  ACR public network access temporarily enabled."
    }
    else {
        Write-Host "=== Step 2/4: Public networking mode - no ACR access toggle needed ==="
    }

    # ------------------------------------------------------------------------
    # 3. Remote build + push each image (server-side, no local Docker)
    # ------------------------------------------------------------------------
    Write-Host ""
    Write-Host "=== Step 3/4: Building $($Images.Count) image(s) via ACR remote build (no local Docker) ==="
    $buildIndex = 0
    foreach ($entry in $Images) {
        $buildIndex++
        $imageRef = "$($entry.Name):$ImageTag"
        Write-Host ""
        Write-Host "  [$buildIndex/$($Images.Count)] Building '$imageRef'"
        Write-Host "        context ...: $($entry.Context)"
        Write-Host "        dockerfile : $($entry.Dockerfile)"
        # Run from within the context so `--file` resolves relative to it (az acr
        # build validates the dockerfile path against the current directory).
        Push-Location $entry.Context
        try {
            Invoke-Run { Invoke-AzCli @('acr', 'build', '--registry', $AcrName, '--resource-group', $ResourceGroup, '--image', $imageRef, '--file', $entry.Dockerfile, '.') }
        }
        finally {
            Pop-Location
        }
        Write-Host "  [$buildIndex/$($Images.Count)] Pushed '$LoginServer/$imageRef'"
    }
    Write-Host ""
    Write-Host "  All images built and pushed."

    # ------------------------------------------------------------------------
    # 4. Update App Services to the newly built images (managed-identity pull)
    # ------------------------------------------------------------------------
    Write-Host ""
    Write-Host "=== Step 4/4: Repointing App Services to the new images (managed-identity pull) ==="
    function Update-AppServiceImage {
        param(
            [string]$AppName,
            [string]$ImageName
        )
        if (-not $AppName) {
            Write-Host "  App name not provided for image '$ImageName' - skipping."
            return
        }
        $fullImage = "$LoginServer/$($ImageName):$ImageTag"
        Write-Host ""
        Write-Host "  Updating '$AppName' -> '$fullImage'"
        Invoke-Run { Invoke-AzCli @('webapp', 'config', 'container', 'set', '--name', $AppName, '--resource-group', $ResourceGroup, '--container-image-name', $fullImage, '--container-registry-url', "https://$LoginServer") }
        # Ensure the app keeps using its managed identity for the ACR pull.
        Write-Host "  Enforcing managed-identity ACR authentication on '$AppName'..."
        Invoke-Run { Invoke-AzCli @('resource', 'update', '--resource-group', $ResourceGroup, '--name', $AppName, '--resource-type', 'Microsoft.Web/sites', '--set', 'properties.siteConfig.acrUseManagedIdentityCreds=true') }
        Write-Host "  Restarting '$AppName'..."
        Invoke-Run { Invoke-AzCli @('webapp', 'restart', '--name', $AppName, '--resource-group', $ResourceGroup) }
        Write-Host "  '$AppName' updated and restarted."
    }

    Update-AppServiceImage -AppName $ApiAppName -ImageName $BackendImage
    Update-AppServiceImage -AppName $WebAppName -ImageName "da-app"

    Write-Host ""
    Write-Host "=== All done! ==="
    Write-Host "  Images built in '$AcrName' and App Services repointed to managed-identity pulls."
    Write-Host "  Run any remaining post-deployment scripts separately, after this one."
}
finally {
    Disable-PublicAccess
}
