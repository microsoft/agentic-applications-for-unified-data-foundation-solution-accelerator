# Create a Fabric capacity in Azure

Set up a Microsoft Fabric capacity resource in your Azure subscription.

## Prerequisites

- An active Azure subscription with permissions to create resources

---

## Steps

1. Sign in to the [Azure Portal](https://portal.azure.com/).

2. Search for **Microsoft Fabric** in the top search bar and select **Microsoft Fabric** from the results.

    ![Search for Microsoft Fabric in the Azure Portal](../assets/fabric/01-search-fabric.png)

3. Click **+ Create** to start creating a new Fabric capacity.

    ![Click Create on the Microsoft Fabric page](../assets/fabric/02-create-fabric.png)

4. Fill in the required details on the **Basics** tab:

    | Field | Value |
    |-------|-------|
    | **Subscription** | Select your Azure subscription |
    | **Resource group** | Select an existing resource group or create a new one |
    | **Capacity name** | Enter a unique name (e.g., `fabriccapworkshop`) |
    | **Region** | Select a region close to your other Azure resources |
    | **Size** | Click Change Size & Select **F8** or higher (F8 is recommended for this workshop) |
    | **Fabric capacity administrator** | This should be the user account that will manage the workspace. |


    ![Fill in the Fabric capacity basics](../assets/fabric/03-capacity-basics.png)

5. Click **Review + create**, verify the settings, and then click **Create**.

    ![Review and create the Fabric capacity](../assets/fabric/05-review-create.png)

7. Wait for the deployment to complete. This typically takes 1–2 minutes.

    ![Deployment in progress](../assets/fabric/06-deployment-complete.png)

---

## Summary

You should now have a Fabric capacity (F8+) created in your Azure subscription.

---


[← Create Fabric Workspace](02-setup-fabric.md)
