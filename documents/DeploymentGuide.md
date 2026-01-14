# Deployment Guide

## **Pre-requisites**

To deploy this solution, ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the necessary permissions to create **resource groups, resources, app registrations, and assign roles at the resource group level**. This should include Contributor role at the subscription level and Role Based Access Control (RBAC) permissions at the subscription and/or resource group level. Follow the steps in [Azure Account Set Up](./AzureAccountSetUp.md). Follow the steps in [Fabric Capacity Set Up](https://learn.microsoft.com/en-us/fabric/admin/capacity-settings?tabs=fabric-capacity#create-a-new-capacity).

Check the [Azure Products by Region](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/?products=all&regions=all) page and select a **region** where the following services are available:

- [Microsoft Fabric](https://learn.microsoft.com/en-us/fabric/)
- [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry)
- [GPT Model Capacity](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models)
- [Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Azure Container Registry](https://learn.microsoft.com/en-us/azure/container-registry/)
<!-- - [Embedding Deployment Capacity](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models#embedding-models) -->

Here are some example regions where the services are available: East US, East US2, Australia East, UK South, France Central.

### **Important Note for PowerShell Users**

If you encounter issues running PowerShell scripts due to the policy of not being digitally signed, you can temporarily adjust the `ExecutionPolicy` by running the following command in an elevated PowerShell session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

This will allow the scripts to run for the current session without permanently changing your system's policy.

## Deployment Options & Steps
###  Fabric Deployment 
<!-- if you have an existing workspace use this Id -->
1. Follow the steps in [Fabric Deployment](./Fabric_deployment.md) to create a Fabric workspace

Pick from the options below to see step-by-step instructions for GitHub Codespaces, VS Code Dev Containers, VS Code (Web), Local Environments, and Bicep deployments.

| [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator) | [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator) | [![Open in Visual Studio Code Web](https://img.shields.io/static/v1?style=for-the-badge&label=Visual%20Studio%20Code%20(Web)&message=Open&color=blue&logo=visualstudiocode&logoColor=white)](https://vscode.dev/azure/?vscode-azure-exp=foundry&agentPayload=eyJiYXNlVXJsIjogImh0dHBzOi8vcmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbS9taWNyb3NvZnQvYWdlbnRpYy1hcHBsaWNhdGlvbnMtZm9yLXVuaWZpZWQtZGF0YS1mb3VuZGF0aW9uLXNvbHV0aW9uLWFjY2VsZXJhdG9yL3JlZnMvaGVhZHMvbWFpbi9pbmZyYS92c2NvZGVfd2ViIiwgImluZGV4VXJsIjogIi9pbmRleC5qc29uIiwgInZhcmlhYmxlcyI6IHsiYWdlbnRJZCI6ICIiLCAiY29ubmVjdGlvblN0cmluZyI6ICIiLCAidGhyZWFkSWQiOiAiIiwgInVzZXJNZXNzYWdlIjogIiIsICJwbGF5Z3JvdW5kTmFtZSI6ICIiLCAibG9jYXRpb24iOiAiIiwgInN1YnNjcmlwdGlvbklkIjogIiIsICJyZXNvdXJjZUlkIjogIiIsICJwcm9qZWN0UmVzb3VyY2VJZCI6ICIiLCAiZW5kcG9pbnQiOiAiIn0sICJjb2RlUm91dGUiOiBbImFpLXByb2plY3RzLXNkayIsICJweXRob24iLCAiZGVmYXVsdC1henVyZS1hdXRoIiwgImVuZHBvaW50Il19) |
|---|---|---|

<details>
  <summary><b>Deploy in GitHub Codespaces</b></summary>

### GitHub Codespaces

You can run this solution using GitHub Codespaces. The button will open a web-based VS Code instance in your browser:

1. Open the solution accelerator (this may take several minutes):

    [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator)

2. Accept the default values on the create Codespaces page.
3. Open a terminal window if it is not already open.
4. Continue with the [deploying steps](#deploying-with-azd).

</details>

<details>
  <summary><b>Deploy in VS Code</b></summary>

### VS Code Dev Containers

You can run this solution in VS Code Dev Containers, which will open the project in your local VS Code using the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers):

1. Start Docker Desktop (install it if not already installed).
2. Open the project:

    [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator)

3. In the VS Code window that opens, once the project files show up (this may take several minutes), open a terminal window.
4. Continue with the [deploying steps](#deploying-with-azd).

</details>

<details>
  <summary><b>Deploy in Visual Studio Code (WEB)</b></summary>

### Visual Studio Code (WEB)

You can run this solution in VS Code Web. The button will open a web-based VS Code instance in your browser:

1. Open the solution accelerator (this may take several minutes):

    [![Open in Visual Studio Code Web](https://img.shields.io/static/v1?style=for-the-badge&label=Visual%20Studio%20Code%20(Web)&message=Open&color=blue&logo=visualstudiocode&logoColor=white)](https://vscode.dev/azure/?vscode-azure-exp=foundry&agentPayload=eyJiYXNlVXJsIjogImh0dHBzOi8vcmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbS9taWNyb3NvZnQvYWdlbnRpYy1hcHBsaWNhdGlvbnMtZm9yLXVuaWZpZWQtZGF0YS1mb3VuZGF0aW9uLXNvbHV0aW9uLWFjY2VsZXJhdG9yL3JlZnMvaGVhZHMvbWFpbi9pbmZyYS92c2NvZGVfd2ViIiwgImluZGV4VXJsIjogIi9pbmRleC5qc29uIiwgInZhcmlhYmxlcyI6IHsiYWdlbnRJZCI6ICIiLCAiY29ubmVjdGlvblN0cmluZyI6ICIiLCAidGhyZWFkSWQiOiAiIiwgInVzZXJNZXNzYWdlIjogIiIsICJwbGF5Z3JvdW5kTmFtZSI6ICIiLCAibG9jYXRpb24iOiAiIiwgInN1YnNjcmlwdGlvbklkIjogIiIsICJyZXNvdXJjZUlkIjogIiIsICJwcm9qZWN0UmVzb3VyY2VJZCI6ICIiLCAiZW5kcG9pbnQiOiAiIn0sICJjb2RlUm91dGUiOiBbImFpLXByb2plY3RzLXNkayIsICJweXRob24iLCAiZGVmYXVsdC1henVyZS1hdXRoIiwgImVuZHBvaW50Il19)

2. When prompted, sign in using your Microsoft account linked to your Azure subscription.
3. Select the appropriate subscription to continue.

4. Once the solution opens, the **AI Foundry terminal** will automatically start running the following command to install the required dependencies:
    ```shell
    sh install.sh
    ```
    During this process, you’ll be prompted with the message:
    ```
    What would you like to do with these files?
    - Overwrite with versions from template
    - Keep my existing files unchanged
    ```
    Choose “**Overwrite with versions from template**” and provide a unique environment name when prompted.

5. **Authenticate with Azure** (VS Code Web requires device code authentication):
   
    ```shell
    az login --use-device-code
    ```
    > **Note:** In VS Code Web environment, the regular `az login` command may fail. Use the `--use-device-code` flag to authenticate via device code flow. Follow the prompts in the terminal to complete authentication.
 
6. Continue with the [deploying steps](#deploying-with-azd).


</details>

<details>
  <summary><b>Deploy in your local Environment</b></summary>

### Local Environment

If you're not using one of the above options for opening the project, then you'll need to:

1. Make sure the following tools are installed:
    - [PowerShell](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell?view=powershell-7.5) <small>(v7.0+)</small> - available for Windows, macOS, and Linux.
    - [Azure Developer CLI (azd)](https://aka.ms/install-azd) <small>(v1.15.0+)</small> - version
    - [Python 3.9+](https://www.python.org/downloads/)
    - [Docker Desktop](https://www.docker.com/products/docker-desktop/)
    - [Git](https://git-scm.com/downloads)
    - [Microsoft ODBC Driver 17](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver16)

2. Clone the repository or download the project code via command-line:

    ```shell
    azd init -t microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator/
    ```

3. Open the project folder in your terminal or editor.
4. Continue with the [deploying steps](#deploying-with-azd).

</details>

<br/>

Consider the following settings during your deployment to modify specific settings:

<details>
  <summary><b>Configurable Deployment Settings</b></summary>

When you start the deployment, most parameters will have **default values**, but you can update the following settings [here](../documents/CustomizingAzdParameters.md):

| **Setting**                                 | **Description**                                                                                           | **Default value**      |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ---------------------- |
| **Azure Region**                            | The region where resources will be created.                                                               | *(empty)*              |
| **Environment Name**                        | A **3–20 character alphanumeric value** used to generate a unique ID to prefix the resources.             | env\_name              |
| **Backend Programming Language**                   | Programming language for the backend API: **python** or **dotnet**.                           | *(empty)*              |
| **Use Case**                   | Use case: **Retail-sales-analysis** or **Insurance-improve-customer-meetings**.                           | *(empty)*              |
| **Deployment Type**                         | Select from a drop-down list (allowed: `Standard`, `GlobalStandard`).                                     | GlobalStandard         |
| **GPT Model**                               | Choose from **gpt-4, gpt-4o, gpt-4o-mini**.                                                               | gpt-4o-mini            |
| **GPT Model Version**                       | The version of the selected GPT model.                                                                    | 2024-07-18             |
| **OpenAI API Version**                      | The Azure OpenAI API version to use.                                                                      | 2025-01-01-preview     |
| **GPT Model Deployment Capacity**           | Configure capacity for **GPT models** (in thousands).                                                     | 30k                    |
| **Image Tag**                               | Docker image tag to deploy. Common values: `latest`, `dev`, `hotfix`.                  | latest       |
| **Use Local Build**                         | Boolean flag to determine if local container builds should be used.                         | false             |
| **Existing Log Analytics Workspace**        | To reuse an existing Log Analytics Workspace ID.                                                          | *(empty)*              |
| **Existing Azure AI Foundry Project**        | To reuse an existing Azure AI Foundry Project ID instead of creating a new one.              | *(empty)*          |



</details>

<details>
  <summary><b>[Optional] Quota Recommendations</b></summary>

By default, the **Gpt-4o-mini model capacity** in deployment is set to **30k tokens**, so we recommend updating the following:

> **For Global Standard | GPT-4o-mini - increase the capacity to at least 150k tokens post-deployment for optimal performance.**

Depending on your subscription quota and capacity, you can [adjust quota settings](AzureGPTQuotaSettings.md) to better meet your specific needs. You can also [adjust the deployment parameters](CustomizingAzdParameters.md) for additional optimization.

**⚠️ Warning:** Insufficient quota can cause deployment errors. Please ensure you have the recommended capacity or request additional capacity before deploying this solution.

</details>
<details>

  <summary><b>Reusing an Existing Log Analytics Workspace</b></summary>

  Guide to get your [Existing Workspace ID](/documents/re-use-log-analytics.md)

</details>
<details>

  <summary><b>Reusing an Existing Azure AI Foundry Project</b></summary>

  Guide to get your [Existing Project ID](/documents/re-use-foundry-project.md)

</details>

### Deploying with AZD

Once you've opened the project in [Codespaces](#github-codespaces), [Dev Containers](#vs-code-dev-containers), [Visual Studio Code (WEB)](#visual-studio-code-web), or [locally](#local-environment), you can deploy it to Azure by following these steps:

1. Login to Azure:

    ```shell
    azd auth login
    ```

    #### To authenticate with Azure Developer CLI (`azd`), use the following command with your **Tenant ID**:

    ```sh
    azd auth login --tenant-id <tenant-id>
    ```

2. Provision and deploy all the resources:

    ```shell
    azd up
    ```

3. Provide an `azd` environment name (e.g., "daapp").
4. Select a subscription from your Azure account and choose a location that has quota for all the resources.
5. Choose the programming language for the backend API:
   - **Python**
   - **.NET (dotnet)**
6. Choose the use case: 
   - **Retail-sales-analysis**
   - **Insurance-improve-customer-meetings** 

   This deployment will take *7-10 minutes* to provision the resources in your account and set up the solution with sample data.
   
   If you encounter an error or timeout during deployment, changing the location may help, as there could be availability constraints for the resources.

7. Once the deployment has completed successfully, copy the 2 bash commands from the terminal (ex. 
`bash ./infra/scripts/agent_scripts/run_create_agents_scripts.sh` and
`bash ./infra/scripts/fabric_scripts/run_fabric_items_scripts.sh <fabric-workspaceId>`) for later use.

> **Note**: If you are running this deployment in GitHub Codespaces or VS Code Dev Container or Visual Studio Code (WEB) skip to step 9. 

8. Create and activate a virtual environment 
  
    ```shell
    python -m venv .venv
    ```

    ```shell
    source .venv/Scripts/activate
    ```

9. Login to Azure
    ```shell
    az login
    ```

    Alternatively, login to Azure using a device code (recommended when using VS Code Web):

    ```shell
    az login --use-device-code
    ```

> **Note**: you will need to open a Git Bash terminal to complete steps 10 and 11.  
10. Run the bash script from the output of the azd deployment. The script will look like the following:
    
    ```Shell
    bash ./infra/scripts/agent_scripts/run_create_agents_scripts.sh
    ```
    If you don't have azd env then you need to pass parameters along with the command. Then the command will look like the following:
    ```Shell
    bash ./infra/scripts/agent_scripts/run_create_agents_scripts.sh <project-endpoint> <solution-name> <gpt-model-name> <ai-foundry-resource-id> <api-app-name> <resource-group>
    ```

11. Run the bash script from the output of the azd deployment. Replace the <fabric-workspaceId> with your Fabric workspace Id created in the previous steps. The script will look like the following:
    ```Shell
    bash ./infra/scripts/fabric_scripts/run_fabric_items_scripts.sh <fabric-workspaceId>
    ```

    If you don't have azd env then you need to pass parameters along with the command. Then the command will look like the following:
    ```Shell
    bash ./infra/scripts/fabric_scripts/run_fabric_items_scripts.sh <fabric-workspaceId> <solutionname> <ai-foundry-name> <backend-api-mid-principal> <backend-api-mid-client> <api-app-name> <resourcegroup>
    ```

12. Once the script has run successfully, go to the deployed resource group, find the App Service, and get the app URL from `Default domain`.

13. If you are done trying out the application, you can delete the resources by running `azd down`.


## Post Deployment Steps

1. **Add App Authentication**
   
    Follow steps in [App Authentication](./AppAuthentication.md) to configure authentication in app service. Note: Authentication changes can take up to 10 minutes 

2. **Deleting Resources After a Failed Deployment**  

     - Follow steps in [Delete Resource Group](./DeleteResourceGroup.md) if your deployment fails and/or you need to clean up the resources.

3. **Cleaning Up Fabric Resources**

     If you are done trying out the accelerator and want to clean up the Fabric resources (lakehouse, SQL database, and role assignments), run the following script:

     ```shell
     bash ./infra/scripts/fabric_scripts/delete_fabric_items_scripts.sh <fabric-workspaceId>
     ```

     If you don't have azd env then you need to pass parameters along with the command:
     
     ```shell
     bash ./infra/scripts/fabric_scripts/delete_fabric_items_scripts.sh <fabric-workspaceId> <solutionname> <backend-api-principal-id>
     ```

     **Note**: This script will remove the lakehouse, SQL database, and service principal role assignments from the Fabric workspace. To completely remove all Azure resources, use `azd down`.

## Sample Questions 

To help you get started, here are some **Sample Questions** you can ask in the app:

For Retail sales analysis use case: 
- Show total revenue by year for last 5 years as a line chart.
- Show top 10 products by Revenue in the last year in a table.
- Show as a donut chart.

For Insurance improve customer meetings use case: 
- I'm meeting Ida Abolina. Can you summarize her customer information and tell me the number of claims, payments, and communications she's had?
- Can you provide details of her communications?
- Based on Ida's policy data has she ever missed a payment?

These questions serve as a great starting point to explore insights from the data.

## Create Fabric Data Agent and Publish to Teams
1. Follow the steps in [CopilotStudioDeployment](./CopilotStudioDeployment.md)

## Local Development
To set up and run the application locally for development, see the [Local Development Setup Guide](./LocalDevelopmentSetup.md).
