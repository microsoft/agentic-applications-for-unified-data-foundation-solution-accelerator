<#
.SYNOPSIS
    Configures OBO (On-Behalf-Of) authentication flow between frontend and backend app registrations.

.DESCRIPTION
    This script:
    0. Configures EasyAuth identity provider on both frontend and API App Services
    1. Exposes an API scope (user_impersonation) on the backend app registration
    2. Adds API permission from frontend app to backend app
    2b. Adds downstream API permissions (Azure AI, Cognitive Services, Azure SQL) on backend app
    3. Grants admin consent for all permissions
    4. Updates EasyAuth loginParameters on the FRONTEND App Service with correct scopes
    5. Sets OBO environment variables (OBO_CLIENT_ID, OBO_CLIENT_SECRET, OBO_TENANT_ID) on the API App Service

.PARAMETER ClientId
    The Application (client) ID of an existing app registration to use for both frontend and backend.
    If not provided, a new app registration will be created.

.PARAMETER AppDisplayName
    Display name for the new app registration. Only used when -ClientId is not provided.
    Defaults to the FrontendAppServiceName.

.PARAMETER AppServiceName
    The name of the API (backend) App Service.

.PARAMETER FrontendAppServiceName
    The name of the Frontend App Service (where EasyAuth issues tokens).

.PARAMETER ResourceGroup
    The resource group containing the App Services.

.PARAMETER SubscriptionId
    The Azure subscription ID.

.PARAMETER OboClientSecret
    The client secret for the OBO flow. If not provided, a new secret will be created on the app registration.

.EXAMPLE
    # Auto-create app registration
    .\setup_obo_auth.ps1 `
        -AppServiceName "api-prdcauthqrm6o" `
        -FrontendAppServiceName "app-prdcauthqrm6o" `
        -ResourceGroup "rg-prdcauth" `
        -SubscriptionId "1d5876cd-7603-407a-96d2-ae5ca9a9c5f3"

.EXAMPLE
    # Use existing app registration
    .\setup_obo_auth.ps1 `
        -ClientId "056a746c-c025-49ca-af55-0ba58be43e4c" `
        -AppServiceName "api-prdcauthqrm6o" `
        -FrontendAppServiceName "app-prdcauthqrm6o" `
        -ResourceGroup "rg-prdcauth" `
        -SubscriptionId "1d5876cd-7603-407a-96d2-ae5ca9a9c5f3"
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$ClientId,

    [Parameter(Mandatory = $false)]
    [string]$AppDisplayName,

    [Parameter(Mandatory = $true)]
    [string]$AppServiceName,

    [Parameter(Mandatory = $true)]
    [string]$FrontendAppServiceName,

    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $true)]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $false)]
    [string]$OboClientSecret
)

$ErrorActionPreference = "Stop"

if (-not $AppDisplayName) {
    $AppDisplayName = $FrontendAppServiceName
}

Write-Host "=== OBO Authentication Setup ===" -ForegroundColor Cyan
Write-Host "App Service (API):      $AppServiceName"
Write-Host "App Service (Frontend): $FrontendAppServiceName"
Write-Host "Resource Group: $ResourceGroup"
Write-Host "Subscription:  $SubscriptionId"
Write-Host ""

# -------------------------------------------------------------------
# Step 0: Create or use existing app registration & configure EasyAuth
# -------------------------------------------------------------------
Write-Host "[Step 0] Setting up app registration and EasyAuth identity provider..." -ForegroundColor Yellow

# Get tenant ID
$tenantId = az account show --query "tenantId" -o tsv
Write-Host "  Tenant ID: $tenantId"

# Create or reuse app registration
if ($ClientId) {
    Write-Host "  Using existing app registration: $ClientId"
} else {
    Write-Host "  Creating new app registration: $AppDisplayName"
    $frontendUrl = "https://$FrontendAppServiceName.azurewebsites.net"
    $apiUrl = "https://$AppServiceName.azurewebsites.net"

    $ClientId = az ad app create `
        --display-name $AppDisplayName `
        --sign-in-audience "AzureADMyOrg" `
        --web-redirect-uris "$frontendUrl/.auth/login/aad/callback" "$apiUrl/.auth/login/aad/callback" `
        --query "appId" -o tsv

    if ($LASTEXITCODE -eq 0 -and $ClientId) {
        Write-Host "  [OK] App registration created: $ClientId" -ForegroundColor Green

        # Create service principal for the app
        az ad sp create --id $ClientId --output none 2>$null
        Write-Host "  [OK] Service principal created" -ForegroundColor Green
    } else {
        Write-Error "  [FAIL] Failed to create app registration"
    }
}

# Use the same client ID for both frontend and backend
$BackendClientId = $ClientId
$FrontendClientId = $ClientId

Write-Host "  App Registration: $ClientId (used for both frontend and backend)"

# Create a client secret if not provided
if (-not $OboClientSecret) {
    Write-Host "  Creating client secret on app registration..."
    $secretResult = az ad app credential reset --id $ClientId --display-name "OBO-Auth-Secret" --years 1 --query "password" -o tsv
    if ($LASTEXITCODE -eq 0 -and $secretResult) {
        $OboClientSecret = $secretResult
        Write-Host "  [OK] Client secret created" -ForegroundColor Green
    } else {
        Write-Error "  [FAIL] Failed to create client secret. Provide -OboClientSecret manually."
    }
}

function Set-EasyAuth {
    param(
        [string]$SiteName,
        [string]$ClientId,
        [string]$TenantId,
        [string]$SubscriptionId,
        [string]$ResourceGroup
    )

    $authUrl = "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Web/sites/$SiteName/config/authsettingsV2?api-version=2023-12-01"
    $currentAuth = az rest --method GET --url $authUrl -o json 2>$null | ConvertFrom-Json

    $aadEnabled = $currentAuth.properties.identityProviders.azureActiveDirectory.enabled
    if ($aadEnabled -eq $true) {
        Write-Host "  EasyAuth already configured on $SiteName"
        return
    }

    Write-Host "  Configuring EasyAuth on $SiteName..."

    # Set the MICROSOFT_PROVIDER_AUTHENTICATION_SECRET app setting
    az webapp config appsettings set -n $SiteName -g $ResourceGroup `
        --settings "MICROSOFT_PROVIDER_AUTHENTICATION_SECRET=$OboClientSecret" --output none

    $authBody = @{
        properties = @{
            platform = @{
                enabled = $true
            }
            globalValidation = @{
                unauthenticatedClientAction = "RedirectToLoginPage"
                redirectToProvider = "azureActiveDirectory"
            }
            identityProviders = @{
                azureActiveDirectory = @{
                    enabled = $true
                    registration = @{
                        clientId = $ClientId
                        clientSecretSettingName = "MICROSOFT_PROVIDER_AUTHENTICATION_SECRET"
                        openIdIssuer = "https://sts.windows.net/$TenantId/v2.0"
                    }
                    validation = @{
                        allowedAudiences = @("api://$ClientId")
                        defaultAuthorizationPolicy = @{
                            allowedApplications = @($ClientId)
                        }
                    }
                    login = @{
                        disableWWWAuthenticate = $false
                    }
                }
            }
            login = @{
                tokenStore = @{
                    enabled = $true
                }
            }
        }
    }

    $tempFile = "$env:TEMP\easyauth_$SiteName.json"
    $authBody | ConvertTo-Json -Depth 20 | Out-File -Encoding utf8 -FilePath $tempFile

    az rest --method PUT --url $authUrl `
        --headers "Content-Type=application/json" `
        --body "@$tempFile" --output none

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] EasyAuth configured on $SiteName" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] EasyAuth configuration may have failed on $SiteName" -ForegroundColor DarkYellow
    }
}

# Configure EasyAuth on frontend App Service
Set-EasyAuth -SiteName $FrontendAppServiceName -ClientId $ClientId `
    -TenantId $tenantId -SubscriptionId $SubscriptionId -ResourceGroup $ResourceGroup

# Configure EasyAuth on API App Service
if ($FrontendAppServiceName -ne $AppServiceName) {
    Set-EasyAuth -SiteName $AppServiceName -ClientId $ClientId `
        -TenantId $tenantId -SubscriptionId $SubscriptionId -ResourceGroup $ResourceGroup
}

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
# Step 5: Set OBO environment variables on API App Service
# -------------------------------------------------------------------
Write-Host ""
Write-Host "[Step 5] Setting OBO environment variables on API App Service ($AppServiceName)..." -ForegroundColor Yellow

az webapp config appsettings set -n $AppServiceName -g $ResourceGroup `
    --settings `
    "OBO_CLIENT_ID=$BackendClientId" `
    "OBO_CLIENT_SECRET=$OboClientSecret" `
    "OBO_TENANT_ID=$tenantId" `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] OBO environment variables set on $AppServiceName" -ForegroundColor Green
} else {
    Write-Error "  [FAIL] Failed to set OBO environment variables"
}

# -------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------
Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:"
Write-Host "  App Registration:     $ClientId (frontend + backend)"
Write-Host "  Backend App ID URI: api://$ClientId"
Write-Host "  Exposed scope:      user_impersonation"
Write-Host "  Frontend permission: api://$ClientId/user_impersonation (Delegated)"
Write-Host "  EasyAuth scopes:    openid profile email offline_access api://$ClientId/user_impersonation"
Write-Host "  EasyAuth target:    $FrontendAppServiceName (frontend App Service)"
Write-Host ""
Write-Host "Downstream API permissions (delegated, admin-consented):"
Write-Host "  Azure AI Services:    user_impersonation (18a66f5f-dbdf-4c17-9dd7-1634712a9cbe)"
Write-Host "  Cognitive Services:   user_impersonation (7d312290-28c8-473c-a0ed-8e53749b6d6d)"
Write-Host "  Azure SQL Database:   user_impersonation (022907d3-0f1b-48f7-badc-1ba6abab6d66)"
Write-Host ""
Write-Host "OBO environment variables (set on $AppServiceName):"
Write-Host "  OBO_TENANT_ID       = $tenantId"
Write-Host "  OBO_CLIENT_ID       = $ClientId"
Write-Host "  OBO_CLIENT_SECRET   = ********** (configured)"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Users must log out and log back in to get new tokens"
Write-Host ""
