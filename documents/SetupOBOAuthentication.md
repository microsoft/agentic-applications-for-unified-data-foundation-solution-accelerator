# Set Up OBO (On-Behalf-Of) Authentication

When `USE_USER_ACCESS_TOKEN` is enabled, the API uses the **On-Behalf-Of (OBO)** flow to call downstream services (e.g., Azure AI Foundry, Fabric Data Agent) using the signed-in user's identity instead of a managed identity.

## Prerequisites

- Completed `azd up` deployment successfully
- Access to **Microsoft Entra ID** with permissions to create App Registrations
- Azure CLI (`az`) logged in
- PowerShell 7.0+

## What This Configures

The `setup_app_authentication.ps1` script automatically sets up:

- A shared **App Registration** with a client secret
- **Service Principal** (Enterprise Application)
- **API permissions** (Microsoft Graph, Power BI/Fabric)
- **Admin consent** for API permissions
- `user_impersonation` scope for API access
- **EasyAuth** settings on both frontend and API App Services

## How to Enable

1. Set the environment variable before deployment:

    ```shell
    azd env set USE_USER_ACCESS_TOKEN true
    ```

2. Run `azd up` to provision and deploy resources.

3. After deployment completes, run the authentication setup script:

    ```powershell
    .\infra\scripts\post-provision\setup_app_authentication.ps1
    ```

## Script Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-Environment` | The azd environment name | Auto-detected from `.azure` folder |
| `-ResourceGroup` | Azure resource group name | Auto-detected from azd env |
| `-FrontendAppName` | Frontend App Service name | Auto-detected from azd env |
| `-ApiAppName` | API App Service name | Auto-detected from azd env |
| `-SecretExpiration` | Client secret expiration in days | 180 |
| `-SkipAdminConsent` | Skip granting admin consent (if you don't have admin permissions) | — |

## Examples

```powershell
# Auto-detect everything from azd environment
.\infra\scripts\post-provision\setup_app_authentication.ps1
```

---

## Troubleshooting

- **Authentication changes can take up to 10 minutes** to propagate after running this script.
- If you don't have tenant admin permissions, use `-SkipAdminConsent` and ask your admin to grant consent manually in the Azure Portal under **Enterprise Applications → Permissions**.
