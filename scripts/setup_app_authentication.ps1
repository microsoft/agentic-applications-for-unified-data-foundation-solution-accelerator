<#
.SYNOPSIS
    Adds Microsoft Entra ID authentication to App Services with OBO support.
    Run this AFTER azd up completes successfully.

.DESCRIPTION
    This script configures Azure App Service Authentication (EasyAuth) with 
    Microsoft Entra ID as the identity provider for both frontend and API apps.
    
    It also configures:
    - Shared App Registration for OBO (On-Behalf-Of) flow
    - Service Principal (Enterprise Application)
    - API permissions (Microsoft Graph, Power BI/Fabric)
    - Admin consent for API permissions
    - user_impersonation scope for API access

.PARAMETER Environment
    The azd environment name. If not specified, auto-detects from .azure folder.

.PARAMETER ResourceGroup
    The Azure resource group name. Auto-detected from azd env if not specified.

.PARAMETER FrontendAppName
    The frontend App Service name. Auto-detected from azd env if not specified.

.PARAMETER ApiAppName
    The API App Service name. Auto-detected from azd env if not specified.

.PARAMETER SecretExpiration
    Client secret expiration in days (default: 180)

.PARAMETER SkipAdminConsent
    Skip granting admin consent (useful if you don't have admin permissions)

.EXAMPLE
    # Auto-detect everything from azd environment
    .\setup_app_authentication.ps1

.EXAMPLE
    # Specify environment explicitly
    .\setup_app_authentication.ps1 -Environment "dev"

.EXAMPLE
    # Skip admin consent if not a tenant admin
    .\setup_app_authentication.ps1 -SkipAdminConsent
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$Environment,

    [Parameter(Mandatory = $false)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $false)]
    [string]$FrontendAppName,

    [Parameter(Mandatory = $false)]
    [string]$ApiAppName,

    [Parameter(Mandatory = $false)]
    [int]$SecretExpiration = 180,

    [switch]$SkipAdminConsent
)

$ErrorActionPreference = "Continue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  App Service Authentication Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
$azCmd = Get-Command az -ErrorAction SilentlyContinue
if (-not $azCmd) {
    Write-Host "  ERROR: Azure CLI (az) is not installed or not in PATH." -ForegroundColor Red
    Write-Host "  Install from: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli" -ForegroundColor Yellow
    exit 1
}

$loginCheck = az account show --query id -o tsv 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Not logged in to Azure CLI. Run 'az login' first." -ForegroundColor Red
    exit 1
}
Write-Host "  Azure CLI detected and logged in." -ForegroundColor Green
Write-Host ""

# Function to read azd environment variables
function Get-AzdEnvValue {
    param([string]$Key, [string]$EnvFilePath)
    
    if (Test-Path $EnvFilePath) {
        $content = Get-Content $EnvFilePath -Raw
        if ($content -match "(?m)^$Key=`"?([^`"\r\n]+)`"?") {
            return $matches[1]
        }
    }
    return $null
}

# Find azd environment
Write-Host "[1/9] Reading azd environment configuration..." -ForegroundColor Yellow

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Split-Path -Parent $scriptDir
$azureFolder = Join-Path $workspaceRoot ".azure"

if (-not $Environment) {
    $Environment = $env:AZURE_ENV_NAME
    
    if (-not $Environment -and (Test-Path $azureFolder)) {
        $envFolders = Get-ChildItem -Path $azureFolder -Directory | Where-Object { 
            Test-Path (Join-Path $_.FullName ".env") 
        }
        if ($envFolders.Count -eq 1) {
            $Environment = $envFolders[0].Name
        } elseif ($envFolders.Count -gt 1) {
            Write-Host "  Multiple azd environments found. Please specify with -Environment:" -ForegroundColor Yellow
            $envFolders | ForEach-Object { Write-Host "    - $($_.Name)" -ForegroundColor Gray }
            exit 1
        }
    }
}

$envFilePath = $null
if ($Environment) {
    $envFilePath = Join-Path (Join-Path $azureFolder $Environment) ".env"
    if (Test-Path $envFilePath) {
        Write-Host "  Using azd environment: $Environment" -ForegroundColor Green
    } else {
        Write-Host "  Warning: Environment file not found at $envFilePath" -ForegroundColor Yellow
        $envFilePath = $null
    }
}

# Auto-detect parameters from azd env
if ($envFilePath) {
    if (-not $ResourceGroup) {
        $ResourceGroup = Get-AzdEnvValue -Key "AZURE_RESOURCE_GROUP" -EnvFilePath $envFilePath
        if (-not $ResourceGroup) {
            $ResourceGroup = Get-AzdEnvValue -Key "RESOURCE_GROUP_NAME" -EnvFilePath $envFilePath
        }
    }
    
    if (-not $FrontendAppName) {
        # Try to extract from WEB_APP_URL
        $webUrl = Get-AzdEnvValue -Key "WEB_APP_URL" -EnvFilePath $envFilePath
        if ($webUrl -match "https://([^.]+)\.azurewebsites\.net") {
            $FrontendAppName = $matches[1]
        }
    }
    
    if (-not $ApiAppName) {
        $ApiAppName = Get-AzdEnvValue -Key "API_APP_NAME" -EnvFilePath $envFilePath
    }
}

# Validate required parameters
$missingParams = @()
if (-not $ResourceGroup) { $missingParams += "ResourceGroup" }
if (-not $FrontendAppName) { $missingParams += "FrontendAppName" }

if ($missingParams.Count -gt 0) {
    Write-Host "  ERROR: Could not auto-detect:" -ForegroundColor Red
    $missingParams | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "  Please provide them explicitly:" -ForegroundColor Yellow
    Write-Host "    .\setup_app_authentication.ps1 -ResourceGroup 'rg-xxx' -FrontendAppName 'app-xxx'" -ForegroundColor Gray
    exit 1
}

Write-Host "  Resource Group:  $ResourceGroup" -ForegroundColor Gray
Write-Host "  Frontend App:    $FrontendAppName" -ForegroundColor Gray
if ($ApiAppName) {
    Write-Host "  API App:         $ApiAppName" -ForegroundColor Gray
}
Write-Host ""

# Step 2: Get subscription and tenant info
Write-Host "[2/9] Getting Azure subscription info..." -ForegroundColor Yellow
$subscriptionId = (az account show --query id -o tsv)
$tenantId = (az account show --query tenantId -o tsv)

if (-not $subscriptionId -or -not $tenantId) {
    Write-Host "  ERROR: Failed to retrieve subscription or tenant info." -ForegroundColor Red
    Write-Host "  Ensure you are logged in with 'az login' and have an active subscription." -ForegroundColor Yellow
    exit 1
}

Write-Host "  Subscription: $subscriptionId" -ForegroundColor Gray
Write-Host "  Tenant:       $tenantId" -ForegroundColor Gray
Write-Host ""

# Step 3: Create App Registration (shared by Frontend and API for OBO)
Write-Host "[3/9] Creating shared App Registration for OBO flow..." -ForegroundColor Yellow

$frontendUrl = "https://$FrontendAppName.azurewebsites.net"
$apiUrl = if ($ApiAppName) { "https://$ApiAppName.azurewebsites.net" } else { $null }
$appDisplayName = "$FrontendAppName-auth"

# Build redirect URIs - both apps use the same app registration
$redirectUris = @("$frontendUrl/.auth/login/aad/callback")
if ($apiUrl) {
    $redirectUris += "$apiUrl/.auth/login/aad/callback"
}

# Check if app registration already exists
$existingApp = az ad app list --display-name $appDisplayName --query "[0].appId" -o tsv 2>$null

if ($existingApp) {
    Write-Host "  App Registration already exists: $existingApp" -ForegroundColor Gray
    $clientId = $existingApp
    
    # Update redirect URIs to include both apps
    Write-Host "  Updating redirect URIs..." -ForegroundColor Gray
    az ad app update --id $clientId --web-redirect-uris $redirectUris --output none
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to update redirect URIs for App Registration." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Redirect URIs updated successfully" -ForegroundColor Green
} else {
    # Create new app registration with both redirect URIs
    $appResult = az ad app create `
        --display-name $appDisplayName `
        --sign-in-audience "AzureADMyOrg" `
        --web-redirect-uris $redirectUris `
        --enable-id-token-issuance true `
        --enable-access-token-issuance true `
        -o json | ConvertFrom-Json
    
    if (-not $appResult -or -not $appResult.appId) {
        Write-Host "  ERROR: Failed to create App Registration." -ForegroundColor Red
        exit 1
    }

    $clientId = $appResult.appId
    Write-Host "  Created App Registration: $clientId" -ForegroundColor Green
    
    # Wait for propagation
    Write-Host "  Waiting for Azure AD propagation..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
}

# Expose API scope (user_impersonation) for OBO
Write-Host "  Exposing API scope for OBO..." -ForegroundColor Gray

# Set Application ID URI
$appIdUri = "api://$clientId"
az ad app update --id $clientId --identifier-uris $appIdUri --output none 2>$null

# Check if scope already exists
$existingScopes = az ad app show --id $clientId --query "api.oauth2PermissionScopes" -o json 2>$null | ConvertFrom-Json

if (-not ($existingScopes | Where-Object { $_.value -eq "user_impersonation" })) {
    # Add user_impersonation scope using Microsoft Graph API (az ad app update --set doesn't work for nested api objects)
    $scopeId = [guid]::NewGuid().ToString()
    
    # Get the app object ID (different from client ID)
    $appObjectId = az ad app show --id $clientId --query "id" -o tsv
    
    $scopeBody = @{
        api = @{
            oauth2PermissionScopes = @(
                @{
                    adminConsentDescription = "Allow the application to access the API on behalf of the signed-in user"
                    adminConsentDisplayName = "Access API on behalf of user"
                    id = $scopeId
                    isEnabled = $true
                    type = "User"
                    userConsentDescription = "Allow the application to access the API on your behalf"
                    userConsentDisplayName = "Access API"
                    value = "user_impersonation"
                }
            )
        }
    } | ConvertTo-Json -Depth 5
    
    $scopeTempFile = [System.IO.Path]::GetTempFileName()
    $scopeBody | Out-File -FilePath $scopeTempFile -Encoding utf8 -NoNewline
    az rest --method PATCH --uri "https://graph.microsoft.com/v1.0/applications/$appObjectId" --body "@$scopeTempFile" --headers "Content-Type=application/json" --output none 2>$null
    Remove-Item $scopeTempFile -Force -ErrorAction SilentlyContinue
    
    Write-Host "  user_impersonation scope created" -ForegroundColor Green
} else {
    Write-Host "  user_impersonation scope already exists" -ForegroundColor Gray
}

# Step 4: Create Service Principal (Enterprise Application)
Write-Host "[4/9] Creating Service Principal (Enterprise Application)..." -ForegroundColor Yellow

$existingSp = az ad sp show --id $clientId --query "appId" -o tsv 2>$null
if (-not $existingSp) {
    az ad sp create --id $clientId --output none
    Write-Host "  Service Principal created" -ForegroundColor Green
    Start-Sleep -Seconds 3  # Wait for propagation
} else {
    Write-Host "  Service Principal already exists" -ForegroundColor Gray
}

# Step 5: Add API Permissions (Microsoft Graph + Power BI/Fabric + Azure ML + own API)
Write-Host "[5/9] Adding API permissions..." -ForegroundColor Yellow

# Get the user_impersonation scope ID
$scopeId = az ad app show --id $clientId --query "api.oauth2PermissionScopes[?value=='user_impersonation'].id" -o tsv

# Build comprehensive permissions JSON
# Microsoft Graph: User.Read, Group.Read.All, ChannelMessage.Read.All, Chat.Read
# Power BI Service: Workspace.Read.All, Dataset.Read.All
# Azure Machine Learning Services: user_impersonation (required for Azure AI Foundry OBO)
# Own API: user_impersonation
$permissionsJson = @"
[
  {
    "resourceAppId": "00000003-0000-0000-c000-000000000000",
    "resourceAccess": [
      {"id": "e1fe6dd8-ba31-4d61-89e7-88639da4683d", "type": "Scope"},
      {"id": "5f8c59db-677d-491f-a6b8-5f174b11ec1d", "type": "Scope"},
      {"id": "767156cb-16ae-4d10-8f8b-41b657c8c8c8", "type": "Scope"},
      {"id": "a4b8392a-d8d1-4954-a029-8e668a39a170", "type": "Scope"}
    ]
  },
  {
    "resourceAppId": "00000009-0000-0000-c000-000000000000",
    "resourceAccess": [
      {"id": "f3076109-ca66-412a-be10-d4ee1be95d47", "type": "Scope"},
      {"id": "7f33e027-4039-419b-938e-2f8ca153e68e", "type": "Scope"}
    ]
  },
  {
    "resourceAppId": "18a66f5f-dbdf-4c17-9dd7-1634712a9cbe",
    "resourceAccess": [
      {"id": "1a7925b5-f871-417a-9b8b-303f9f29fa10", "type": "Scope"}
    ]
  },
  {
    "resourceAppId": "$clientId",
    "resourceAccess": [
      {"id": "$scopeId", "type": "Scope"}
    ]
  }
]
"@

$permTempFile = [System.IO.Path]::GetTempFileName()
$permissionsJson | Out-File -FilePath $permTempFile -Encoding utf8 -NoNewline
az ad app update --id $clientId --required-resource-accesses "@$permTempFile" --output none
$permExitCode = $LASTEXITCODE
Remove-Item $permTempFile -Force -ErrorAction SilentlyContinue

if ($permExitCode -ne 0) {
    Write-Host "  ERROR: Failed to add API permissions to App Registration." -ForegroundColor Red
    exit 1
}

Write-Host "  API permissions added:" -ForegroundColor Green
Write-Host "    - Microsoft Graph: User.Read, Group.Read.All, ChannelMessage.Read.All, Chat.Read" -ForegroundColor Gray
Write-Host "    - Power BI Service: Workspace.Read.All, Dataset.Read.All" -ForegroundColor Gray
Write-Host "    - Azure Machine Learning: user_impersonation (for AI Foundry)" -ForegroundColor Gray
Write-Host "    - Own API: user_impersonation" -ForegroundColor Gray

# Step 6: Grant Admin Consent
if (-not $SkipAdminConsent) {
    Write-Host "[6/9] Granting admin consent for API permissions..." -ForegroundColor Yellow
    
    # Wait for Azure AD to propagate the permissions from Step 5
    Write-Host "  Waiting for Azure AD propagation before granting consent..." -ForegroundColor Gray
    Start-Sleep -Seconds 10
    
    # Get the service principal object ID for our app
    $spObjectId = az ad sp show --id $clientId --query "id" -o tsv 2>$null
    if (-not $spObjectId) {
        Write-Host "  ERROR: Service principal not found for client ID $clientId." -ForegroundColor Red
        Write-Host "  Cannot grant admin consent without a service principal." -ForegroundColor Yellow
    } else {
        # Grant consent per resource using Microsoft Graph oauth2PermissionGrants API
        # This is more reliable than 'az ad app permission admin-consent' which often
        # silently fails for multi-resource apps (Power BI, Azure ML, etc.)
        $resourceApps = @(
            @{ AppId = "00000003-0000-0000-c000-000000000000"; Scopes = "User.Read Group.Read.All ChannelMessage.Read.All Chat.Read"; Name = "Microsoft Graph" }
            @{ AppId = "00000009-0000-0000-c000-000000000000"; Scopes = "Workspace.Read.All Dataset.Read.All"; Name = "Power BI Service" }
            @{ AppId = "18a66f5f-dbdf-4c17-9dd7-1634712a9cbe"; Scopes = "user_impersonation"; Name = "Azure Machine Learning" }
            @{ AppId = $clientId; Scopes = "user_impersonation"; Name = "Own API" }
        )
        
        $consentSuccess = 0
        $consentFailed = 0
        
        foreach ($resource in $resourceApps) {
            $resourceSpId = az ad sp show --id $resource.AppId --query "id" -o tsv 2>$null
            if (-not $resourceSpId) {
                # Resource service principal may not exist in the tenant; create it
                Write-Host "    Creating service principal for $($resource.Name)..." -ForegroundColor Gray
                $resourceSpId = az ad sp create --id $resource.AppId --query "id" -o tsv 2>$null
                if (-not $resourceSpId) {
                    Write-Host "    Warning: Could not find or create service principal for $($resource.Name) ($($resource.AppId))." -ForegroundColor Yellow
                    $consentFailed++
                    continue
                }
                Start-Sleep -Seconds 3
            }
            
            # Check if an oauth2PermissionGrant already exists for this resource
            $existingGrant = az rest --method GET `
                --uri "https://graph.microsoft.com/v1.0/oauth2PermissionGrants?\`$filter=clientId eq '$spObjectId' and resourceId eq '$resourceSpId' and consentType eq 'AllPrincipals'" `
                --query "value[0].id" -o tsv 2>$null
            
            if ($existingGrant) {
                # Update existing grant to ensure scopes are correct
                $grantBody = @{ scope = $resource.Scopes } | ConvertTo-Json -Compress
                $grantTempFile = [System.IO.Path]::GetTempFileName()
                $grantBody | Out-File -FilePath $grantTempFile -Encoding utf8 -NoNewline
                az rest --method PATCH `
                    --uri "https://graph.microsoft.com/v1.0/oauth2PermissionGrants/$existingGrant" `
                    --body "@$grantTempFile" `
                    --headers "Content-Type=application/json" `
                    --output none 2>$null
                $grantExitCode = $LASTEXITCODE
                Remove-Item $grantTempFile -Force -ErrorAction SilentlyContinue
                
                if ($grantExitCode -eq 0) {
                    Write-Host "    $($resource.Name): consent updated" -ForegroundColor Green
                    $consentSuccess++
                } else {
                    Write-Host "    $($resource.Name): failed to update consent" -ForegroundColor Yellow
                    $consentFailed++
                }
            } else {
                # Create new oauth2PermissionGrant
                $grantBody = @{
                    clientId = $spObjectId
                    consentType = "AllPrincipals"
                    resourceId = $resourceSpId
                    scope = $resource.Scopes
                } | ConvertTo-Json -Compress
                
                $grantTempFile = [System.IO.Path]::GetTempFileName()
                $grantBody | Out-File -FilePath $grantTempFile -Encoding utf8 -NoNewline
                az rest --method POST `
                    --uri "https://graph.microsoft.com/v1.0/oauth2PermissionGrants" `
                    --body "@$grantTempFile" `
                    --headers "Content-Type=application/json" `
                    --output none 2>$null
                $grantExitCode = $LASTEXITCODE
                Remove-Item $grantTempFile -Force -ErrorAction SilentlyContinue
                
                if ($grantExitCode -eq 0) {
                    Write-Host "    $($resource.Name): consent granted" -ForegroundColor Green
                    $consentSuccess++
                } else {
                    Write-Host "    $($resource.Name): failed to grant consent" -ForegroundColor Yellow
                    $consentFailed++
                }
            }
        }
        
        if ($consentFailed -gt 0) {
            Write-Host "  Admin consent: $consentSuccess succeeded, $consentFailed failed." -ForegroundColor Yellow
            Write-Host "  Grant remaining permissions manually at:" -ForegroundColor Gray
            Write-Host "  https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/~/CallAnAPI/appId/$clientId" -ForegroundColor Cyan
        } else {
            Write-Host "  Admin consent granted for all $consentSuccess resources" -ForegroundColor Green
        }
    }
} else {
    Write-Host "[6/9] Skipping admin consent (use -SkipAdminConsent:`$false to enable)..." -ForegroundColor Yellow
    Write-Host "  Grant consent manually at:" -ForegroundColor Gray
    Write-Host "  https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/~/CallAnAPI/appId/$clientId" -ForegroundColor Cyan
}

# Step 7: Create client secret
Write-Host "[7/9] Creating client secret..." -ForegroundColor Yellow

$secretResult = az ad app credential reset `
    --id $clientId `
    --append `
    --display-name "EasyAuth-Secret" `
    --years ([math]::Ceiling($SecretExpiration / 365)) `
    -o json | ConvertFrom-Json

if (-not $secretResult -or -not $secretResult.password) {
    Write-Host "  ERROR: Failed to create client secret." -ForegroundColor Red
    exit 1
}

$clientSecret = $secretResult.password
$maskedSecret = "$('*' * ($clientSecret.Length - 4))$($clientSecret.Substring($clientSecret.Length - 4))"
Write-Host "  Client secret created: $maskedSecret" -ForegroundColor Green
Write-Host ""

# Step 8: Configure Frontend App Service Authentication
Write-Host "[8/9] Configuring Frontend App Service authentication..." -ForegroundColor Yellow

$authConfig = @{
    properties = @{
        platform = @{
            enabled = $true
        }
        globalValidation = @{
            requireAuthentication = $true
            unauthenticatedClientAction = "RedirectToLoginPage"
            redirectToProvider = "azureactivedirectory"
        }
        identityProviders = @{
            azureActiveDirectory = @{
                enabled = $true
                registration = @{
                    openIdIssuer = "https://sts.windows.net/$tenantId/v2.0"
                    clientId = $clientId
                    clientSecretSettingName = "MICROSOFT_PROVIDER_AUTHENTICATION_SECRET"
                }
                validation = @{
                    # Both the client ID and api:// URI must be in allowed audiences for OBO
                    allowedAudiences = @(
                        "api://$clientId"
                        $clientId
                    )
                }
                login = @{
                    # Request scopes needed for OBO flow
                    loginParameters = @(
                        "scope=openid profile email offline_access api://$clientId/user_impersonation"
                    )
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

$authConfigJson = $authConfig | ConvertTo-Json -Depth 10 -Compress

# Set the client secret as an app setting
Write-Host "  Setting MICROSOFT_PROVIDER_AUTHENTICATION_SECRET on frontend..." -ForegroundColor Gray
az webapp config appsettings set `
    --name $FrontendAppName `
    --resource-group $ResourceGroup `
    --settings "MICROSOFT_PROVIDER_AUTHENTICATION_SECRET=$clientSecret" `
    --output none
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Failed to set app settings on frontend App Service." -ForegroundColor Red
    exit 1
}

# Apply auth configuration - write to temp file to avoid escaping issues
$uri = "/subscriptions/$subscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Web/sites/$FrontendAppName/config/authsettingsV2?api-version=2022-03-01"

$tempFile = [System.IO.Path]::GetTempFileName()
$authConfigJson | Out-File -FilePath $tempFile -Encoding utf8 -NoNewline
az rest --method PUT --uri $uri --body "@$tempFile" --headers "Content-Type=application/json" --output none
$exitCode = $LASTEXITCODE
Remove-Item $tempFile -Force -ErrorAction SilentlyContinue

if ($exitCode -eq 0) {
    Write-Host "  Frontend authentication configured successfully" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Failed to configure frontend authentication" -ForegroundColor Red
    exit 1
}

# Step 9: Configure API App Service Authentication (if specified)
if ($ApiAppName) {
    Write-Host "[9/9] Configuring API App Service authentication (same App Registration for OBO)..." -ForegroundColor Yellow
    
    # Set the client secret and OBO environment variables
    Write-Host "  Setting app settings and OBO environment variables on API..." -ForegroundColor Gray
    az webapp config appsettings set `
        --name $ApiAppName `
        --resource-group $ResourceGroup `
        --settings `
            "MICROSOFT_PROVIDER_AUTHENTICATION_SECRET=$clientSecret" `
            "OBO_CLIENT_ID=$clientId" `
            "OBO_CLIENT_SECRET=$clientSecret" `
            "OBO_TENANT_ID=$tenantId" `
        --output none
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to set app settings on API App Service." -ForegroundColor Red
        exit 1
    }
    
    # API auth config - AllowAnonymous mode for cross-domain compatibility
    # Platform is enabled to parse tokens, but auth is not required
    # This allows the frontend to send X-ZUMO-AUTH tokens without EasyAuth blocking cross-origin requests
    $apiAuthConfig = @{
        properties = @{
            platform = @{
                enabled = $true
            }
            globalValidation = @{
                requireAuthentication = $false  # Don't require auth - API handles token validation
                unauthenticatedClientAction = "AllowAnonymous"  # Allow anonymous for cross-domain
                redirectToProvider = "azureactivedirectory"
            }
            identityProviders = @{
                azureActiveDirectory = @{
                    enabled = $true
                    registration = @{
                        openIdIssuer = "https://sts.windows.net/$tenantId/v2.0"
                        clientId = $clientId
                        clientSecretSettingName = "MICROSOFT_PROVIDER_AUTHENTICATION_SECRET"
                    }
                    validation = @{
                        allowedAudiences = @(
                            "api://$clientId"
                            $clientId
                        )
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
    $apiAuthConfigJson = $apiAuthConfig | ConvertTo-Json -Depth 10 -Compress
    
    # Apply API auth configuration
    $apiUri = "/subscriptions/$subscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Web/sites/$ApiAppName/config/authsettingsV2?api-version=2022-03-01"
    
    $tempFile = [System.IO.Path]::GetTempFileName()
    $apiAuthConfigJson | Out-File -FilePath $tempFile -Encoding utf8 -NoNewline
    az rest --method PUT --uri $apiUri --body "@$tempFile" --headers "Content-Type=application/json" --output none
    $apiExitCode = $LASTEXITCODE
    Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
    
    if ($apiExitCode -eq 0) {
        Write-Host "  API authentication configured successfully (AllowAnonymous mode)" -ForegroundColor Green
        Write-Host "  OBO environment variables set on API" -ForegroundColor Green
    } else {
        Write-Host "  Warning: Failed to configure API authentication" -ForegroundColor Yellow
    }
} else {
    Write-Host "[9/9] Skipping API authentication (no API app specified)" -ForegroundColor Gray
}

# Restart apps
Write-Host ""
Write-Host "Restarting App Services..." -ForegroundColor Yellow
az webapp restart --name $FrontendAppName --resource-group $ResourceGroup --output none
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Warning: Failed to restart frontend App Service '$FrontendAppName'." -ForegroundColor Yellow
} else {
    Write-Host "  Frontend App Service '$FrontendAppName' restarted" -ForegroundColor Green
}
if ($ApiAppName) {
    az webapp restart --name $ApiAppName --resource-group $ResourceGroup --output none
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Warning: Failed to restart API App Service '$ApiAppName'." -ForegroundColor Yellow
    } else {
        Write-Host "  API App Service '$ApiAppName' restarted" -ForegroundColor Green
    }
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Authentication Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Client ID:     $clientId" -ForegroundColor Cyan
Write-Host "  Tenant ID:     $tenantId" -ForegroundColor Cyan
Write-Host "  Client Secret: $maskedSecret" -ForegroundColor Cyan
Write-Host "  App ID URI:    api://$clientId" -ForegroundColor Cyan
Write-Host ""
Write-Host "App URLs:" -ForegroundColor Yellow
Write-Host "  Frontend: $frontendUrl" -ForegroundColor Gray
if ($ApiAppName) {
    Write-Host "  API:      https://$ApiAppName.azurewebsites.net" -ForegroundColor Gray
    Write-Host ""
    Write-Host "OBO Configuration (set on API):" -ForegroundColor Yellow
    Write-Host "  OBO_CLIENT_ID:     $clientId" -ForegroundColor Gray
    Write-Host "  OBO_CLIENT_SECRET: (set)" -ForegroundColor Gray
    Write-Host "  OBO_TENANT_ID:     $tenantId" -ForegroundColor Gray
}
Write-Host ""
Write-Host "IMPORTANT: The client secret is masked in this output." -ForegroundColor Red
Write-Host "It has already been applied to app settings and the full value will not be displayed." -ForegroundColor Red
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Visit $frontendUrl to test authentication" -ForegroundColor Gray
Write-Host "  2. Sign in with your Microsoft account" -ForegroundColor Gray
if ($ApiAppName) {
    Write-Host "  3. OBO flow is already configured!" -ForegroundColor Gray
}
Write-Host ""
