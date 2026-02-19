# Fabric Setup

Create and configure your Microsoft Fabric workspace for Fabric IQ.

!!! note "Using Azure-Only Mode?"
    If you set `AZURE_ENV_ONLY=true` before running `azd up`, you can **skip this page** and proceed directly to [Configure dev environment](03-configure.md).

## Prerequisites

- An active Azure subscription with permissions to create resources
- Workspace admin permissions

---

## Step 1 — Create a Fabric capacity in Azure

!!! tip "Already have a Fabric capacity?"
    If you already have a Fabric capacity (F8+), you can **skip this step** and use your existing capacity. Proceed to [Step 2](#step-2-create-a-fabric-workspace).

If you need to create a new Fabric capacity, follow the instructions here:
**[Create a Fabric capacity in Azure →](02a-create-fabric-capacity.md)**

---

## Step 2 — Create a Fabric workspace

!!! tip "Already have a Fabric workspace?"
    If you already have a Fabric workspace linked to a Fabric capacity, you can **skip this step** and use your existing workspace. Proceed to [Step 3](#step-3-verify-workspace-settings).

If you need to create a new Fabric workspace, follow the instructions here:
**[Create a Fabric workspace →](02b-create-fabric-workspace.md)**

---

## Step 3 — Verify workspace settings

!!! warning "Fabric IQ must be enabled"
    Ensure that [Fabric IQ is enabled on your tenant](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview-tenant-settings) before proceeding.

1. Open your newly created workspace or an existing workspace.

2. Click the **Workspace settings** gear icon (⚙️) in the top-right area.

    ![Open workspace settings](../assets/fabric/13-workspace-settings.png)

3. Go to **License info** and verify:

    - [x] The workspace is assigned to a **Fabric capacity**
    - [x] The capacity SKU is **F8** or higher

    ![Verify license info](../assets/fabric/14-license-info.png)

---

## Step 4 — Retrieve the workspace ID

You will need the workspace ID to configure the solution in the next step.

1. Open your workspace in the browser.

2. Look at the URL — the workspace ID is the GUID that appears after `/groups/`:

    ```
    https://app.fabric.microsoft.com/groups/{workspace-id}/...
    ```

    ![Copy workspace ID from URL](../assets/fabric/15-workspace-id.png)

3. Copy the workspace ID and save it for later. You'll use it in the [Configure dev environment](03-configure.md) step.

!!! tip "Finding the workspace ID"
    For more details, refer to the Microsoft documentation: [Identify your workspace ID](https://learn.microsoft.com/en-us/fabric/admin/portal-workspace#identify-your-workspace-id).

---

## Summary

You should now have:

| Item |
|------|
| Fabric capacity created in Azure (F8+) |
| Fabric workspace created and linked to capacity |
| Workspace ID copied for configuration |

!!! success "Ready to Continue"
    You have your Fabric workspace ready. Proceed to configure your dev environment.

---

[← Deploy Azure resources](01-deploy-azure.md) | [Configure dev environment →](03-configure.md)
