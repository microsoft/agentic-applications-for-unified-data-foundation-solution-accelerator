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

## Deployment Options

This solution deploys with Microsoft Fabric (Data Agent, Ontology, Lakehouse) + Azure AI Foundry.

**Requirements:** Fabric capacity (F8+) + Azure subscription

---

## Scenario Packs

Pre-built scenario packs provide ready-to-use datasets without requiring AI data generation. They are ideal for demos, workshops, and testing.

| Pack | Industry | Use Case | Tables | Documents |
|------|----------|----------|--------|-----------|
| **retail** | Retail | Inventory and sales operations | 13 (customers, orders, products, invoices, payments, locations) | None (SQL-only) |
| **insurance** | Insurance | Claims processing and customer management | 4 (customer, policy, claim, communicationshistory) | None (SQL-only) |
| **default** | Telecommunications | Network operations with outage tracking and trouble ticket management | AI-generated | AI-generated |
| **default_large** | Telecommunications | Network operations (large dataset) | AI-generated | AI-generated |

> **Note:** If you don't use `--scenario`, the `default` scenario is used automatically (Telecommunications - Network operations with outage tracking and trouble ticket management) which generates AI-based sample data.

To use a scenario pack, add `--scenario <name>` to the build command (see step 7 below).

**Additional data options:**
- [Bring Your Own Data](../data/customdata/README.md) — Use your own CSV tables and PDF documents
- [Generate Custom Data](./GenerateCustomData.md) — AI-generate datasets for any custom industry/use case (ideal for POCs)

---

## Deployment Steps

###  Fabric Deployment
<!-- if you have an existing workspace use this Id -->
1. Follow the steps in [Fabric Deployment](./Fabric_deployment.md) to create a Fabric workspace

    > **Important (Fabric Admin Portal):** Before proceeding, ensure the following tenant settings are enabled in the [Fabric Admin Portal](https://app.fabric.microsoft.com/admin-portal) → **Tenant settings**:
    > - **Ontology (preview)** — Required for Data Agent to function
    > - **Graph (preview)** — Required for entity relationships
    > - **Copilot and Azure OpenAI Service** — Required for AI features
    >
    > These settings may take up to 15 minutes to propagate. See [Fabric IQ Tenant Settings](https://learn.microsoft.com/en-us/fabric/iq/ontology/overview-tenant-settings) for details.

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
    - [Bicep CLI](https://learn.microsoft.com/azure/azure-resource-manager/bicep/install) <small>(v0.33.0+)</small>
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
| **Backend Programming Language**            | Programming language for the backend API: **python** or **dotnet**.                                       | python                 |
| **Deployment Type**                         | Select from a drop-down list (allowed: `Standard`, `GlobalStandard`).                                     | GlobalStandard         |
| **GPT Model**                               | Name of the GPT model to deploy (e.g., `gpt-4.1-mini`).                                                  | gpt-4.1-mini           |
| **GPT Model Version**                       | The version of the selected GPT model.                                                                    | 2025-04-14             |
| **OpenAI API Version**                      | The Azure OpenAI API version to use.                                                                      | 2025-01-01-preview     |
| **GPT Model Deployment Capacity**           | Configure capacity for **GPT models** (in thousands).                                                     | 150                    |
| **Image Tag**                               | Docker image tag to deploy. Common values: `latest_v2`, `dev`, `hotfix`.                                  | latest\_v2             |
| **Existing Log Analytics Workspace**        | To reuse an existing Log Analytics Workspace ID.                                                          | *(empty)*              |
| **Existing Azure AI Foundry Project**       | To reuse an existing Azure AI Foundry Project ID instead of creating a new one.                           | *(empty)*              |
| **Use User Access Token**                   | Enable On-Behalf-Of (OBO) flow so the API calls downstream services using the signed-in user's token. Requires running [OBO Authentication Setup](./SetupOBOAuthentication.md) after deployment. | false              |



</details>

<details>
  <summary><b>[Optional] Quota Recommendations</b></summary>

By default, the **gpt-4.1-mini model capacity** in deployment is set to **150 TPM (thousands)**, which is the recommended minimum for optimal performance.

Depending on your subscription quota and capacity, you can [adjust quota settings](AzureGPTQuotaSettings.md) to better meet your specific needs. You can also [adjust the deployment parameters](CustomizingAzdParameters.md) for additional optimization.

**⚠️ Warning:** Insufficient quota can cause deployment errors. Please ensure you have the recommended capacity or request additional capacity before deploying this solution.

</details>
<details>

  <summary><b>Reusing an Existing Log Analytics Workspace</b></summary>

  Guide to get your [Existing Workspace ID](re-use-log-analytics.md)

</details>
<details>

  <summary><b>Reusing an Existing Azure AI Foundry Project</b></summary>

  Guide to get your [Existing Project ID](re-use-foundry-project.md)

</details>

<details>
  <summary><b>Choose Deployment Mode (Optional)</b></summary>

### Deployment Modes

This solution supports three deployment modes to fit different use cases:

| **Aspect** | **Development/Testing (bicep)** | **Production (avm)** | **Production WAF-Aligned (avm-waf)** |
|------------|-----------------------------------|----------------------|--------------------------------------|
| **Deployment Flavor** | `bicep` (Vanilla Bicep) | `avm` (AVM modules) | `avm-waf` (AVM + WAF features) |
| **Configuration File** | `main.parameters.json` (default) | `main.parameters.json` | Copy `main.waf.parameters.json` to `main.parameters.json` |
| **Security Controls** | Minimal (for rapid iteration) | Production-ready | Enhanced (WAF best practices) |
| **Networking** | Public endpoints | Public endpoints | Private endpoints, VNet isolation |
| **Cost** | Lower costs | Moderate costs | Higher costs (VMs, private networking) |
| **Use Case** | POCs, development, testing | Production workloads | Production with compliance requirements |
| **Framework** | Basic configuration | AVM-compliant | [Well-Architected Framework](https://learn.microsoft.com/en-us/azure/well-architected/) |

**How to switch deployment flavors:**
```bash
# For AVM production without private networking
azd env set DEPLOYMENT_FLAVOR avm
```

**To use production(WAF-aligned) configuration:**

Copy the contents from the production configuration file to your main parameters file:

1. Navigate to the `infra` folder in your project
2. Open `main.waf.parameters.json` in a text editor (like Notepad, VS Code, etc.)
3. Select all content (Ctrl+A) and copy it (Ctrl+C)
4. Open `main.parameters.json` in the same text editor
5. Select all existing content (Ctrl+A) and paste the copied content (Ctrl+V)
6. Save the file (Ctrl+S)

> **Note:** The `deploymentFlavor` parameter in `main.parameters.json` controls which modules are used. Set to `bicep` (default), `avm`, or `avm-waf` depending on your requirements. See [Parameter Customization Guide](./CustomizingAzdParameters.md) for details.

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

      By default the backend API is configured to Python.
      To use dotnet instead, run the below command.

      ```sh
      azd env set BACKEND_RUNTIME_STACK dotnet
      ```

    **NOTE:** If you are running the latest azd version (version 1.23.9), please run the following command. 
    ```bash 
    azd config set provision.preflight off
    ```

    **[Optional] Reuse an existing Fabric workspace:**

    If you already have a Fabric workspace, set its ID before provisioning. This skips Fabric capacity creation during `azd up`:
    ```shell
    azd env set FABRIC_WORKSPACE_ID <your-workspace-id>
    ```
    > You can find your workspace ID in the Fabric URL: `https://app.fabric.microsoft.com/groups/<workspace-id>/...`
    > If you omit `FABRIC_WORKSPACE_ID`, a new Fabric capacity and workspace will be created automatically.

2. Provision and deploy all the resources:

    ```shell
    azd up
    ```

3. Provide an `azd` environment name (e.g., "daapp").
4. Select a subscription from your Azure account and choose a location that has quota for all the resources.

   This deployment will take *7-10 minutes* to provision the resources in your account and set up the solution with sample data.
   
   If you encounter an error or timeout during deployment, changing the location may help, as there could be availability constraints for the resources.

5. Setup Python environment:

    ```shell
    python -m venv .venv
    ```

    For Windows (PowerShell):
    ```shell
    .venv\Scripts\Activate.ps1
    ```

    For Windows (Bash):
    ```shell
    source .venv/Scripts/activate
    ```

    For Linux/macOS/VS Code Web (Bash):
    ```shell
    source .venv/bin/activate
    ```

6. Install dependencies:

    ```shell
    pip install uv && uv pip install -r infra/scripts/post-provision/requirements.txt
    ```

7. Login to Azure:

    ```shell
    az login
    ```

    > **VS Code Web users:** Use `az login --use-device-code` since browser-based login is not supported in VS Code Web.

8. Build the solution:

    ```shell
    python infra/scripts/post-provision/00_build_solution.py --from 02
    ```

    **Using a Scenario Pack** (pre-built datasets — no AI generation needed):
    > **Note:** If you have already deployed with default scenario or any other scenario, run the command with the `--clean` flag appended at the end:
    >
    > ```shell
    > # Retail scenario:
    > python infra/scripts/post-provision/00_build_solution.py --scenario retail --clean
    >
    > # Insurance scenario:
    > python infra/scripts/post-provision/00_build_solution.py --scenario insurance --clean
    > ```

    ```shell
    # Retail scenario:
    python infra/scripts/post-provision/00_build_solution.py --scenario retail

    # Insurance scenario:
    python infra/scripts/post-provision/00_build_solution.py --scenario insurance
    ```


    > **Tip:** To reuse an existing Fabric workspace, run `azd env set FABRIC_WORKSPACE_ID <your-workspace-id>` before building.

    > **Note:** Scenario packs skip data generation (step 01) and document upload (step 05) automatically.
    > Press **Enter** to start or **Ctrl+C** to cancel the process.

9. Test the agent:

    ```shell
    python infra/scripts/post-provision/07_test_agent.py
    ```

    **Sample questions by scenario:**

    | Scenario | Sample Questions |
    |----------|-----------------|
    | **Default** | "How many tickets are high priority?" · "What is the average score from inspections?" · "What constitutes a failed inspection?" |
    | **Retail** | "Show the top 5 products by total quantity sold last month?" · "Show total revenue by year for last 5 years" · "Show top 10 products by Revenue in the last year" |
    | **Insurance** | "I'm meeting Ida Abolina. Can you summarize her customer information and tell me the number of claims, payments, and communications she's had?" · "Can you provide details of her communications?" · "Based on Ida's policy data has she ever missed a payment?" |

10. Once the build has completed successfully, go to the deployed resource group, find the App Service, and get the app URL from `Default domain`.

11. If you are done trying out the application, you can delete the resources by running `azd down`.


## Post Deployment Steps

1. **Add App Authentication**
   
    Follow steps in [App Authentication](./AppAuthentication.md) to configure authentication in app service. Note: Authentication changes can take up to 10 minutes 

2. **Deleting Resources After a Failed Deployment**  

     - Follow steps in [Delete Resource Group](./DeleteResourceGroup.md) if your deployment fails and/or you need to clean up the resources.

## Sample Questions 

To help you get started, here are some **Sample Questions** you can ask in the app:

**Default scenario (Telecommunications - Network Operations):**

1. How many tickets are high priority?
2. What is the average score from inspections?
3. What constitutes a failed inspection?

**Retail scenario pack:**
- Show total revenue by year for last 5 years as a line chart.
- Show top 10 products by Revenue in the last year in a table.
- Show as a donut chart.

**Insurance scenario pack:**
- I'm meeting Ida Abolina. Can you summarize her customer information and tell me the number of claims, payments, and communications she's had?
- Can you provide details of her communications?
- Based on Ida's policy data has she ever missed a payment?

These questions serve as a great starting point to explore insights from the data.

## Create Fabric Data Agent and Publish to Teams
1. Follow the steps in [CopilotStudioDeployment](./CopilotStudioDeployment.md)

## Advanced: Deploy Local Changes

If you've made local modifications to the code and want to deploy them to Azure, follow these steps to swap the configuration files:

> **Note:** To set up and run the application locally for development, see the [Local Development Setup Guide](./LocalDevelopmentSetup.md).

### Step 1: Rename Azure Configuration Files

**In the root directory:**
1. Rename `azure.yaml` to `azure_custom2.yaml`
2. Rename `azure_custom.yaml` to `azure.yaml`

### Step 2: Rename Infrastructure Files

**In the `infra` directory:**
1. Rename `main.bicep` to `main_custom2.bicep`
2. Rename `main_custom.bicep` to `main.bicep`

### Step 3: Deploy Changes

Run the deployment command:
```shell
azd up
```

> **Note:** These custom files are configured to deploy your local code changes instead of pulling from the GitHub repository.
