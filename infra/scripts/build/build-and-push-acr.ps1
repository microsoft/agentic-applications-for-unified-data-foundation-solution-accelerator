<#
.SYNOPSIS
    Post-deployment: build application container images with ACR remote build
    (`az acr build`) and push them to the deployment-specific Azure Container
    Registry, then repoint the App Services at the freshly built images.

.DESCRIPTION
    This is a SEPARATE, manual post-deployment step that runs AFTER the
    infrastructure (including the dedicated ACR) has been provisioned.

    Flow:
      1. (Private networking only) Temporarily enable ACR public network access
         so `az acr build` can upload the build context.
      2. Remote-build + push each image server-side with `az acr build`
         (no local Docker required).
      3. Update each App Service to use the new image, keeping managed-identity
         (AcrPull) authentication, and restart it.
      4. (Private networking only) Disable ACR public network access again.

    Run any other existing post-deployment scripts separately, after this one.

.NOTES
    Requires: Azure CLI (`az`) and an authenticated context (`az login`).
    Does NOT require Docker to be installed locally.

    When -ResourceGroup is given, the ACR name, API/Web App Service names,
    backend runtime, and private-networking state are auto-discovered from that RG
    and the local azd environment is IGNORED. Any other explicit parameter still wins.
    With NO parameters, values are pulled from the local azd environment
    (azd env get-values), if one is initialized.

    By default, individual `az` command output is suppressed and only progress
    messages and errors are shown. Pass -VerboseOutput to see full command output.
#>

[CmdletBinding()]
param (
    [string]$ResourceGroup,
    [string]$AcrName,
    [string]$SubscriptionId,
    [string]$ImageTag = "latest_v2",
    [string]$ApiAppName,
    [string]$WebAppName,
    [ValidateSet("python", "dotnet")] [string]$BackendRuntimeStack = "python",
    [switch]$PrivateNetworking,
    [switch]$VerboseOutput
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# UTF-8-safe `az` wrapper (mirrors the bash `az()` override).
#
# The Windows MSI `az` launcher runs `python.exe -IBm azure.cli`. The -I
# (isolated) flag makes Python ignore PYTHON* env vars (PYTHONUTF8 /
# PYTHONIOENCODING), so the `az acr build` log stream is encoded with the
# console code page (cp1252) and crashes with a UnicodeEncodeError on any
# non-ASCII build output. The `-X utf8` command-line flag is NOT blocked by
# isolated mode, so we call the bundled python directly with -X utf8 when we
# can find it; otherwise we fall back to the normal `az` launcher on PATH.
#
# Shadowing `az` as a function means EVERY az call in this script (login,
# discovery queries, and the acr build) uses the UTF-8-safe invocation, exactly
# like the bash version.
# ---------------------------------------------------------------------------
$script:AzPython = $null
$script:AzReal = $null
$azCmd = Get-Command az -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($azCmd) {
    $script:AzReal = $azCmd.Source
    $azDir = Split-Path -Parent $azCmd.Source
    foreach ($cand in @(
            (Join-Path $azDir "..\python.exe"),
            (Join-Path $azDir "python.exe"))) {
        if (Test-Path $cand) { $script:AzPython = (Resolve-Path $cand).Path; break }
    }
}

function az {
    if ($script:AzPython) {
        $env:AZ_INSTALLER = "MSI"
        & $script:AzPython -X utf8 -B -m azure.cli @args
    }
    elseif ($script:AzReal) {
        & $script:AzReal @args
    }
    else {
        throw "Azure CLI ('az') was not found on PATH."
    }
}

# ---------------------------------------------------------------------------
# Command runner: suppress stdout unless -VerboseOutput; errors always show.
# (mirrors the bash `run()` wrapper, plus a non-zero exit-code guard.)
# ---------------------------------------------------------------------------
function Invoke-Az {
    param([string[]]$Args)
    if ($VerboseOutput) {
        az @Args
    }
    else {
        az @Args 1>$null
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Args -join ' ')"
    }
}

# ---------------------------------------------------------------------------
# Resolve paths (script lives in infra/scripts/build -> repo root is ../../..)
# ---------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..\..")).Path

# ---------------------------------------------------------------------------
# Fallback: pull any unset values from the local azd environment (if present).
# This ONLY runs when the user did NOT pass -ResourceGroup. If a resource group
# is supplied explicitly, the local azd environment is ignored entirely and
# every value is taken from the parameters or discovered from that RG.
# Precedence (no explicit RG): explicit parameter > azd env > RG-based discovery > default.
# ---------------------------------------------------------------------------
if ($PSBoundParameters.ContainsKey('ResourceGroup')) {
    Write-Host "Resource group provided explicitly - ignoring local azd environment; all inputs will come from '$ResourceGroup'."
}
elseif (Get-Command azd -ErrorAction SilentlyContinue) {
    $azdRaw = azd env get-values 2>$null
    if ($LASTEXITCODE -eq 0 -and $azdRaw) {
        $azdValues = @{}
        foreach ($line in $azdRaw) {
            if ($line -match '^\s*([A-Za-z0-9_]+)="?(.*?)"?\s*$') {
                $azdValues[$Matches[1]] = $Matches[2]
            }
        }
        function Get-AzdValue([string]$Key) {
            if ($azdValues.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace($azdValues[$Key])) {
                return $azdValues[$Key]
            }
            return $null
        }
        if (-not $PSBoundParameters.ContainsKey('ResourceGroup'))      { $v = Get-AzdValue 'RESOURCE_GROUP_NAME';                if ($v) { $ResourceGroup = $v } }
        if (-not $PSBoundParameters.ContainsKey('SubscriptionId'))     { $v = Get-AzdValue 'AZURE_SUBSCRIPTION_ID';              if ($v) { $SubscriptionId = $v } }
        if (-not $PSBoundParameters.ContainsKey('AcrName'))            { $v = Get-AzdValue 'AZURE_ENV_CONTAINER_REGISTRY_NAME';  if ($v) { $AcrName = $v } }
        if (-not $PSBoundParameters.ContainsKey('ApiAppName'))         { $v = Get-AzdValue 'API_APP_NAME';                       if ($v) { $ApiAppName = $v } }
        if (-not $PSBoundParameters.ContainsKey('WebAppName'))         { $v = Get-AzdValue 'WEB_APP_NAME';                       if ($v) { $WebAppName = $v } }
        if (-not $PSBoundParameters.ContainsKey('BackendRuntimeStack')){ $v = Get-AzdValue 'BACKEND_RUNTIME_STACK';              if ($v) { $BackendRuntimeStack = $v } }
        if (-not $PSBoundParameters.ContainsKey('ImageTag'))          { $v = Get-AzdValue 'AZURE_ENV_IMAGE_TAG';                if ($v) { $ImageTag = $v } }
        if ($ResourceGroup) { Write-Host "Loaded defaults from azd environment." }
    }
}

if ([string]::IsNullOrWhiteSpace($ResourceGroup)) {
    throw "ResourceGroup is required (pass -ResourceGroup or run inside an initialized azd environment)."
}

# ---------------------------------------------------------------------------
# 1. Ensure Azure login + subscription
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== Step 1/4: Verifying Azure CLI login and discovering deployment ==="
Write-Host "  Resource group ...: $ResourceGroup"
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "  Not logged in to Azure. Launching 'az login'..."
    & az login | Out-Null
}
if ($SubscriptionId) {
    Write-Host "  Setting subscription to '$SubscriptionId'..."
    Invoke-Az @("account", "set", "--subscription", $SubscriptionId)
}
Write-Host "  Azure context ready."

# ---------------------------------------------------------------------------
# 1b. Auto-discover any values not supplied explicitly, from the resource group
# ---------------------------------------------------------------------------
$UsePrivateNetworking = $PrivateNetworking.IsPresent

if ([string]::IsNullOrWhiteSpace($AcrName)) {
    $AcrName = az acr list --resource-group $ResourceGroup --query "[0].name" -o tsv 2>$null
    if ([string]::IsNullOrWhiteSpace($AcrName)) {
        throw "No container registry found in resource group '$ResourceGroup'. Pass -AcrName explicitly."
    }
    Write-Host "  Discovered ACR ....: $AcrName"
}

if ([string]::IsNullOrWhiteSpace($ApiAppName)) {
    $dotnetApp = az webapp list --resource-group $ResourceGroup --query "[?starts_with(name, 'api-cs-')].name | [0]" -o tsv 2>$null
    if (-not [string]::IsNullOrWhiteSpace($dotnetApp)) {
        $ApiAppName = $dotnetApp
        $BackendRuntimeStack = "dotnet"
    }
    else {
        $ApiAppName = az webapp list --resource-group $ResourceGroup --query "[?starts_with(name, 'api-') && !starts_with(name, 'api-cs-')].name | [0]" -o tsv 2>$null
        $BackendRuntimeStack = "python"
    }
    if (-not [string]::IsNullOrWhiteSpace($ApiAppName)) {
        Write-Host "  Discovered API app : $ApiAppName (runtime: $BackendRuntimeStack)"
    }
    else {
        Write-Host "  WARNING: No API App Service (api-* / api-cs-*) found in '$ResourceGroup'."
    }
}

if ([string]::IsNullOrWhiteSpace($WebAppName)) {
    $WebAppName = az webapp list --resource-group $ResourceGroup --query "[?starts_with(name, 'app-')].name | [0]" -o tsv 2>$null
    if (-not [string]::IsNullOrWhiteSpace($WebAppName)) {
        Write-Host "  Discovered Web app : $WebAppName"
    }
    else {
        Write-Host "  WARNING: No Web App Service (app-*) found in '$ResourceGroup'."
    }
}

# Auto-detect private networking from the ACR public-access state (unless explicit)
if (-not $PrivateNetworking.IsPresent) {
    $acrPublic = az acr show --name $AcrName --resource-group $ResourceGroup --query "publicNetworkAccess" -o tsv 2>$null
    if ($acrPublic -eq "Disabled") {
        $UsePrivateNetworking = $true
        Write-Host "  Detected private networking (ACR public access is Disabled)."
    }
}

# ---------------------------------------------------------------------------
# Compute derived values now that discovery is complete
# ---------------------------------------------------------------------------
$LoginServer = "$AcrName.azurecr.io"

# Image definitions: name -> @{ Context; Dockerfile }
$Images = @{
    "da-app" = @{
        Context    = (Join-Path $RepoRoot "src\App")
        Dockerfile = "WebApp.Dockerfile"
    }
}
if ($BackendRuntimeStack -eq "dotnet") {
    $Images["da-api-dotnet"] = @{
        Context    = (Join-Path $RepoRoot "src\api\dotnet")
        Dockerfile = "CsApi.Dockerfile"
    }
    $BackendImage = "da-api-dotnet"
}
else {
    $Images["da-api"] = @{
        Context    = (Join-Path $RepoRoot "src\api\python")
        Dockerfile = "ApiApp.Dockerfile"
    }
    $BackendImage = "da-api"
}

Write-Host "  ----------------------------------------------------------"
Write-Host "  Resolved configuration:"
Write-Host "    ACR ..............: $AcrName ($LoginServer)"
Write-Host "    Image tag ........: $ImageTag"
Write-Host "    Backend runtime ..: $BackendRuntimeStack"
Write-Host "    API app ..........: $(if ($ApiAppName) { $ApiAppName } else { '<none>' })"
Write-Host "    Web app ..........: $(if ($WebAppName) { $WebAppName } else { '<none>' })"
Write-Host "    Private networking: $UsePrivateNetworking"
Write-Host "    Verbose output ...: $($VerboseOutput.IsPresent)"

# ---------------------------------------------------------------------------
# 2. (Private networking) Temporarily enable ACR public access
# ---------------------------------------------------------------------------
Write-Host ""
if ($UsePrivateNetworking) {
    Write-Host "=== Step 2/4: Temporarily opening ACR '$AcrName' for remote build ==="
    Write-Host "  App Services stay private - only the registry is opened for the build context upload."
    # Public network access cannot be enabled while the export policy is disabled,
    # so enable exports first, then open the public endpoint.
    Invoke-Az @("acr", "update", "--name", $AcrName, "--resource-group", $ResourceGroup, "--allow-exports", "true")
    Invoke-Az @("acr", "update", "--name", $AcrName, "--resource-group", $ResourceGroup, "--public-network-enabled", "true", "--default-action", "Allow")
    Write-Host "  Waiting 30s for network rule propagation..."
    Start-Sleep -Seconds 30
    Write-Host "  ACR public network access temporarily enabled."
}
else {
    Write-Host "=== Step 2/4: Public networking mode - no ACR access toggle needed ==="
}

try {
    # -----------------------------------------------------------------------
    # 3. Remote build + push each image (server-side, no local Docker)
    # -----------------------------------------------------------------------
    Write-Host ""
    Write-Host "=== Step 3/4: Building $($Images.Count) image(s) via ACR remote build (no local Docker) ==="
    $buildIndex = 0
    foreach ($imageName in $Images.Keys) {
        $buildIndex++
        $ctx = $Images[$imageName].Context
        $dockerfile = $Images[$imageName].Dockerfile
        $imageRef = "${imageName}:${ImageTag}"

        Write-Host ""
        Write-Host "  [$buildIndex/$($Images.Count)] Building '$imageRef'"
        Write-Host "        context ...: $ctx"
        Write-Host "        dockerfile : $dockerfile"
        # Run from within the context so `--file` resolves relative to it (az acr
        # build validates the dockerfile path against the current directory).
        Push-Location $ctx
        try {
            Invoke-Az @(
                "acr", "build",
                "--registry", $AcrName,
                "--resource-group", $ResourceGroup,
                "--image", $imageRef,
                "--file", $dockerfile,
                "."
            )
        }
        finally {
            Pop-Location
        }
        Write-Host "  [$buildIndex/$($Images.Count)] Pushed '$LoginServer/$imageRef'"
    }
    Write-Host ""
    Write-Host "  All images built and pushed."
}
finally {
    # -----------------------------------------------------------------------
    # Cleanup. (Private networking) Disable ACR public access again
    # -----------------------------------------------------------------------
    if ($UsePrivateNetworking) {
        Write-Host ""
        Write-Host "=== Cleanup: Re-locking ACR '$AcrName' (disabling public access) ==="
        Invoke-Az @("acr", "update", "--name", $AcrName, "--resource-group", $ResourceGroup, "--public-network-enabled", "false", "--default-action", "Deny")
        Write-Host "  ACR public network access disabled again."
        # Restore the export policy to its locked-down (disabled) state. This can
        # only be disabled once public network access is off (done above).
        Invoke-Az @("acr", "update", "--name", $AcrName, "--resource-group", $ResourceGroup, "--allow-exports", "false")
        Write-Host "  ACR export policy re-disabled."
    }
}

# ---------------------------------------------------------------------------
# 4. Update App Services to the newly built images (managed-identity pull)
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== Step 4/4: Repointing App Services to the new images (managed-identity pull) ==="
function Update-AppServiceImage {
    param([string]$AppName, [string]$ImageName)
    if ([string]::IsNullOrWhiteSpace($AppName)) {
        Write-Host "  App name not provided for image '$ImageName' - skipping."
        return
    }
    $fullImage = "$LoginServer/${ImageName}:${ImageTag}"
    Write-Host ""
    Write-Host "  Updating '$AppName' -> '$fullImage'"
    Invoke-Az @(
        "webapp", "config", "container", "set",
        "--name", $AppName,
        "--resource-group", $ResourceGroup,
        "--container-image-name", $fullImage,
        "--container-registry-url", "https://$LoginServer"
    )
    # Ensure the app keeps using its managed identity for the ACR pull.
    Write-Host "  Enforcing managed-identity ACR authentication on '$AppName'..."
    Invoke-Az @(
        "resource", "update",
        "--resource-group", $ResourceGroup,
        "--name", $AppName,
        "--resource-type", "Microsoft.Web/sites",
        "--set", "properties.siteConfig.acrUseManagedIdentityCreds=true"
    )
    Write-Host "  Restarting '$AppName'..."
    Invoke-Az @("webapp", "restart", "--name", $AppName, "--resource-group", $ResourceGroup)
    Write-Host "  '$AppName' updated and restarted."
}

Update-AppServiceImage -AppName $ApiAppName -ImageName $BackendImage
Update-AppServiceImage -AppName $WebAppName -ImageName "da-app"

Write-Host ""
Write-Host "=== All done! ==="
Write-Host "  Images built in '$AcrName' and App Services repointed to managed-identity pulls."
Write-Host "  Run any remaining post-deployment scripts separately, after this one."
