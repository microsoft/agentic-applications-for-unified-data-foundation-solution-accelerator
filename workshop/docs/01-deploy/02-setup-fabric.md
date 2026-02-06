# Create Fabric workspace

Create and configure your Microsoft Fabric workspace for Fabric IQ.

!!! note "Using Azure-Only Mode?"
    If you set `AZURE_ENV_ONLY=true` before running `azd up`, you can **skip this page** and proceed directly to [Configure dev environment](03-configure.md).

## Prerequisites

- [Microsoft Fabric capacity (F2 or higher recommended)](https://learn.microsoft.com/en-us/fabric/admin/capacity-settings?tabs=fabric-capacity#create-a-new-capacity)
- Workspace admin permissions

## Create a Fabric workspace

1. Go to [Microsoft Fabric](https://app.fabric.microsoft.com)
2. Click **Workspaces** → **New workspace**
3. Name it something like `iq-workshop`
4. Select your Fabric capacity
5. Click **Apply**

## Configure workspace settings

1. Open your new workspace
2. Go to **Settings** → **License info**
3. Verify the workspace is using Fabric capacity

## Get workspace details

You'll need these values for the next step:

| Setting | Where to find it |
|---------|------------------|
| Workspace ID | URL after `/groups/` |
| Workspace name | Workspace settings |


[← Deploy Azure resources](01-deploy-azure.md) | [Configure dev environment →](03-configure.md)
