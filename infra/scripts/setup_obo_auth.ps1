<#
.SYNOPSIS
    Configures OBO (On-Behalf-Of) authentication flow between frontend and backend app registrations.

.DESCRIPTION
    This script:
    1. Exposes an API scope (user_impersonation) on the backend app registration
    2. Adds API permission from frontend app to backend app
    2b. Adds downstream API permissions (Azure AI, Cognitive Services, Azure SQL) on backend app
    3. Grants admin consent for all permissions
    4. Updates EasyAuth loginParameters on the FRONTEND App Service with correct scopes

.PARAMETER BackendClientId
    The Application (client) ID of the backend app registration.

.PARAMETER FrontendClientId
    The Application (client) ID of the frontend app registration.

.PARAMETER AppServiceName
    The name of the API App Service.

.PARAMETER FrontendAppServiceName
    The name of the Frontend App Service (where EasyAuth issues tokens). If not provided, defaults to AppServiceName.

.PARAMETER ResourceGroup
    The resource group containing the App Service.

.PARAMETER SubscriptionId
    The Azure subscription ID.

.EXAMPLE
    .\setup_obo_auth.ps1 `
        -BackendClientId "a5b01284-f4a6-4eae-8f57-45f299ec507b" `
        -FrontendClientId "79691eb1-a9d4-4760-82c7-f70a7a9cd73c" `
        -AppServiceName "api-prdcauthqrm6o" `
        -FrontendAppServiceName "app-prdcauthqrm6o" `
        -ResourceGroup "rg-prdcauth" `
        -SubscriptionId "1d5876cd-7603-407a-96d2-ae5ca9a9c5f3"
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$BackendClientId,

    [Parameter(Mandatory = $true)]
    [string]$FrontendClientId,

    [Parameter(Mandatory = $true)]
    [string]$AppServiceName,

    [Parameter(Mandatory = $false)]
    [string]$FrontendAppServiceName,

    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $true)]
    [string]$SubscriptionId
)

$ErrorActionPreference = "Stop"

if (-not $FrontendAppServiceName) {
    $FrontendAppServiceName = $AppServiceName
}

Write-Host "=== OBO Authentication Setup ===" -ForegroundColor Cyan
Write-Host "Backend App:   $BackendClientId"
Write-Host "Frontend App:  $FrontendClientId"
Write-Host "API App Service:      $AppServiceName"
Write-Host "Frontend App Service: $FrontendAppServiceName"
Write-Host "Resource Group: $ResourceGroup"
Write-Host "Subscription:  $SubscriptionId"
Write-Host ""

# -------------------------------------------------------------------
# Step 1: Expose an API scope on backend app registration
# -------------------------------------------------------------------
Write-Host "[Step 1] Exposing API scope on backend app registration..." -ForegroundColor Yellow

# Set Application ID URI if not already set
$backendApp = az ad app show --id $BackendClientId --query "identifierUris" -o tsv 2>$null
if (-not $backendApp) {
    Write-Host "  Setting Application ID URI: api://$BackendClientId"
    az ad app update --id $BackendClientId --identifier-uris "api://$BackendClientId"
} else {
    Write-Host "  Application ID URI already set: $backendApp"
}

# Check if user_impersonation scope already exists
$existingScopes = az ad app show --id $BackendClientId --query "api.oauth2PermissionScopes[?value=='user_impersonation'].id" -o tsv
if ($existingScopes) {
    Write-Host "  user_impersonation scope already exists (ID: $existingScopes)"
    $scopeId = $existingScopes
} else {
    # Generate a new GUID for the scope
    $scopeId = [guid]::NewGuid().ToString()
    Write-Host "  Adding user_impersonation scope (ID: $scopeId)"

    $scopeJson = @"
{
    "api": {
        "oauth2PermissionScopes": [
            {
                "adminConsentDescription": "Allow the application to access the API on behalf of the signed-in user",
                "adminConsentDisplayName": "Access API",
                "id": "$scopeId",
                "isEnabled": true,
                "type": "User",
                "userConsentDescription": "Allow the application to access the API on your behalf",
                "userConsentDisplayName": "Access API",
                "value": "user_impersonation"
            }
        ]
    }
}
"@
    $tempFile = "$env:TEMP\scope_body.json"
    $scopeJson | Out-File -Encoding utf8 -FilePath $tempFile

    az rest --method PATCH `
        --url "https://graph.microsoft.com/v1.0/applications(appId='$BackendClientId')" `
        --headers "Content-Type=application/json" `
        --body "@$tempFile" `
        --output none

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] user_impersonation scope added" -ForegroundColor Green
    } else {
        Write-Error "  [FAIL] Failed to add scope"
    }
}

# -------------------------------------------------------------------
# Step 2: Add API permission from frontend to backend
# -------------------------------------------------------------------
Write-Host ""
Write-Host "[Step 2] Adding API permission on frontend app registration..." -ForegroundColor Yellow

# Check if permission already exists
$existingPermission = az ad app show --id $FrontendClientId `
    --query "requiredResourceAccess[?resourceAppId=='$BackendClientId'].resourceAccess[?id=='$scopeId'].id" -o tsv

if ($existingPermission) {
    Write-Host "  Permission already exists"
} else {
    Write-Host "  Adding delegated permission for user_impersonation"
    az ad app permission add `
        --id $FrontendClientId `
        --api $BackendClientId `
        --api-permissions "${scopeId}=Scope"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Permission added" -ForegroundColor Green
    } else {
        Write-Error "  [FAIL] Failed to add permission"
    }
}

# -------------------------------------------------------------------
# Step 2b: Add downstream API permissions on backend app registration
# -------------------------------------------------------------------
Write-Host ""
Write-Host "[Step 2b] Adding downstream API permissions on backend app registration..." -ForegroundColor Yellow

# Azure AI Services (ai.azure.com) - needed by AIProjectClient
$aiApiId = "18a66f5f-dbdf-4c17-9dd7-1634712a9cbe"
$aiScopeId = az ad sp show --id $aiApiId --query "oauth2PermissionScopes[?value=='user_impersonation'].id" -o tsv
if ($aiScopeId) {
    Write-Host "  Adding Azure AI Services (user_impersonation)"
    az ad app permission add --id $BackendClientId --api $aiApiId --api-permissions "${aiScopeId}=Scope" 2>$null
}

# Cognitive Services - needed by AI Search
$cogApiId = "7d312290-28c8-473c-a0ed-8e53749b6d6d"
$cogScopeId = az ad sp show --id $cogApiId --query "oauth2PermissionScopes[?value=='user_impersonation'].id" -o tsv
if ($cogScopeId) {
    Write-Host "  Adding Cognitive Services (user_impersonation)"
    az ad app permission add --id $BackendClientId --api $cogApiId --api-permissions "${cogScopeId}=Scope" 2>$null
}

# Azure SQL Database - needed by SQL queries via OBO
$sqlApiId = "022907d3-0f1b-48f7-badc-1ba6abab6d66"
$sqlScopeId = az ad sp show --id $sqlApiId --query "oauth2PermissionScopes[?value=='user_impersonation'].id" -o tsv
if ($sqlScopeId) {
    Write-Host "  Adding Azure SQL Database (user_impersonation)"
    az ad app permission add --id $BackendClientId --api $sqlApiId --api-permissions "${sqlScopeId}=Scope" 2>$null
}

Write-Host "  [OK] Downstream API permissions added" -ForegroundColor Green

# -------------------------------------------------------------------
# Step 3: Grant admin consent
# -------------------------------------------------------------------
Write-Host ""
Write-Host "[Step 3] Granting admin consent..." -ForegroundColor Yellow

az ad app permission admin-consent --id $BackendClientId 2>$null
if ($BackendClientId -ne $FrontendClientId) {
    az ad app permission admin-consent --id $FrontendClientId 2>$null
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] Admin consent granted" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Admin consent may require Global Admin. Grant it manually in the portal." -ForegroundColor DarkYellow
}

# -------------------------------------------------------------------
# Step 4: Update EasyAuth loginParameters on App Service
# -------------------------------------------------------------------
Write-Host ""
Write-Host "[Step 4] Updating EasyAuth loginParameters on App Service..." -ForegroundColor Yellow

# Get current auth config (update on the FRONTEND App Service where tokens are issued)
$authUrl = "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Web/sites/$FrontendAppServiceName/config/authsettingsV2?api-version=2023-12-01"
$currentConfig = az rest --method GET --url $authUrl -o json | ConvertFrom-Json

# Update loginParameters
$loginParams = @("scope=openid profile email offline_access api://$BackendClientId/user_impersonation")
$loginObj = $currentConfig.properties.identityProviders.azureActiveDirectory.login
if ($loginObj.PSObject.Properties["loginParameters"]) {
    $loginObj.loginParameters = $loginParams
} else {
    $loginObj | Add-Member -NotePropertyName "loginParameters" -NotePropertyValue $loginParams
}

# Write updated config
$updatedFile = "$env:TEMP\auth_obo_config.json"
$currentConfig | ConvertTo-Json -Depth 20 | Out-File -Encoding utf8 -FilePath $updatedFile

az rest --method PUT --url $authUrl `
    --headers "Content-Type=application/json" `
    --body "@$updatedFile" `
    --query "properties.identityProviders.azureActiveDirectory.login" `
    --output json

if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] EasyAuth updated with scope: openid profile email offline_access api://$BackendClientId/user_impersonation" -ForegroundColor Green
} else {
    Write-Error "  [FAIL] Failed to update EasyAuth"
}

# -------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------
Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:"
Write-Host "  Backend App ID URI: api://$BackendClientId"
Write-Host "  Exposed scope:      user_impersonation"
Write-Host "  Frontend permission: api://$BackendClientId/user_impersonation (Delegated)"
Write-Host "  EasyAuth scopes:    openid profile email offline_access api://$BackendClientId/user_impersonation"
Write-Host "  EasyAuth target:    $FrontendAppServiceName (frontend App Service)"
Write-Host ""
Write-Host "Downstream API permissions (delegated, admin-consented):"
Write-Host "  Azure AI Services:    user_impersonation (18a66f5f-dbdf-4c17-9dd7-1634712a9cbe)"
Write-Host "  Cognitive Services:   user_impersonation (7d312290-28c8-473c-a0ed-8e53749b6d6d)"
Write-Host "  Azure SQL Database:   user_impersonation (022907d3-0f1b-48f7-badc-1ba6abab6d66)"
Write-Host ""
Write-Host "Required environment variables for the backend API App Service:"
Write-Host "  OBO_TENANT_ID       = (your tenant ID)"
Write-Host "  OBO_CLIENT_ID       = $BackendClientId"
Write-Host "  OBO_CLIENT_SECRET   = (create in app registration > Certificates & secrets)"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Ensure OBO_CLIENT_ID, OBO_CLIENT_SECRET, OBO_TENANT_ID are set on $AppServiceName"
Write-Host "  2. Users must log out and log back in to get new tokens"
Write-Host ""
