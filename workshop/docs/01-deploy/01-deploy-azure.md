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

**To authenticate with Azure Developer CLI (azd), use the following command with your Tenant ID:**
```bash
azd auth login --tenant-id <tenant-id>
az login --tenant <tenant-id>
```

## Deploy Resources

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
