# Deploy Infrastructure

## Clone the Repository

```bash
git clone https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator.git
cd agentic-applications-for-unified-data-foundation-solution-accelerator
```

## Login to Azure

```bash
azd auth login
```

This opens a browser for authentication.

**Having trouble authenticating? Try specifying your Tenant ID:**
```bash
azd auth login --tenant-id <tenant-id>
az login --tenant <tenant-id>
```

!!! tip "VS Code Web users"
    Browser-based login is not supported in VS Code Web. Use device code authentication instead:
    ```bash
    az login --use-device-code
    ```

## Deploy Resources

!!! info "No Microsoft Fabric Access?"
    If you don't have access to Microsoft Fabric or prefer to use Azure SQL instead, set the Azure-only flag before deploying:
    
    ```bash
    azd env set AZURE_ENV_ONLY true
    ```
    
    When prompted, enter a unique environment name. This deploys Azure SQL Database instead of Fabric SQL, allowing you to run the workshop without a Fabric workspace.

Register the Microsoft Cognitive Services resource provider (required if not already registered on your subscription):

```bash
az login
```

```bash
az provider register --namespace Microsoft.CognitiveServices
```

```bash
azd up
```

Follow the prompts to select your environment name, subscription, and location etc.

!!! warning "Wait for Completion"
    Deployment takes 7-8 minutes. Don't proceed until you see the success message.

## Verify Deployment

Verify in [Azure Portal](https://portal.azure.com/) that your resource group contains all resources:

- Microsoft Foundry
- Azure AI Search
- Storage Account
- Application Insights

## Environment Variables

After deployment, Azure endpoints are automatically saved to `.azure/<env>/.env` and loaded by the scripts.

!!! note "No Manual Configuration"
    You don't need to manually set Azure connection strings. The scripts read them from the azd environment automatically.

---

[← Overview](index.md) | [Create Fabric workspace →](02-setup-fabric.md)
