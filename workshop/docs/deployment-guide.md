# Quick Deploy Guide

## Prerequisites

- Azure subscription with Contributor access & Role Based Access Control access
- VS Code, Azure Developer CLI ([aka.ms/azd](https://aka.ms/azd)), Python 3.10+, Git
- For Fabric deployment: Microsoft Fabric workspace (F8+ capacity) with admin permissions
- [Microsoft ODBC Driver 18](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver16)

## Choose Your Development Environment

Local Visual Studio Code: Open Visual Studio Code. From the File menu, select Open Folder and choose the folder where you want to deploy the workshop.

Or choose one of the options below:

[![Open in GitHub Codespaces](https://img.shields.io/badge/GitHub-Codespaces-blue?logo=github)](https://codespaces.new/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator)
[![Open in VS Code Web](https://img.shields.io/badge/VS%20Code-Open%20in%20Web-blue?logo=visualstudiocode)](https://vscode.dev/azure/?vscode-azure-exp=foundry&agentPayload=eyJiYXNlVXJsIjogImh0dHBzOi8vcmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbS9taWNyb3NvZnQvYWdlbnRpYy1hcHBsaWNhdGlvbnMtZm9yLXVuaWZpZWQtZGF0YS1mb3VuZGF0aW9uLXNvbHV0aW9uLWFjY2VsZXJhdG9yL3JlZnMvaGVhZHMvbWFpbi9pbmZyYS92c2NvZGVfd2ViIiwgImluZGV4VXJsIjogIi9pbmRleC5qc29uIiwgInZhcmlhYmxlcyI6IHsiYWdlbnRJZCI6ICIiLCAiY29ubmVjdGlvblN0cmluZyI6ICIiLCAidGhyZWFkSWQiOiAiIiwgInVzZXJNZXNzYWdlIjogIiIsICJwbGF5Z3JvdW5kTmFtZSI6ICIiLCAibG9jYXRpb24iOiAiIiwgInN1YnNjcmlwdGlvbklkIjogIiIsICJyZXNvdXJjZUlkIjogIiIsICJwcm9qZWN0UmVzb3VyY2VJZCI6ICIiLCAiZW5kcG9pbnQiOiAiIn0sICJjb2RlUm91dGUiOiBbImFpLXByb2plY3RzLXNkayIsICJweXRob24iLCAiZGVmYXVsdC1henVyZS1hdXRoIiwgImVuZHBvaW50Il19)


---

> Note: Please use this optional prompt if you would like to use GitHub Copilot to run the workshop: 
```
Can you please follow the step by step in https://microsoft.github.io/agentic-applications-for-unified-data-foundation-solution-accelerator/deployment-guide/ and follow Option A for me. My Fabric Workspace id = <YOUR_FABRIC_WORKSPACE_ID>.
Important instructions:
Do NOT make any code changes to the repository files. 
Only follow the deployment guide instructions exactly as documented. 
Run the commands step by step and wait for each to complete before proceeding.
If I encounter any errors or issues, help me troubleshoot and resolve them before continuing.
Explain what each step does before running it.
If a step fails, suggest solutions based on the error message. 
```

---

## Option A: Full Deployment (Fabric + Foundry)

### 1. Configure Fabric workspace

Create a new [Fabric workspace](./01-deploy/02-setup-fabric.md).


### 2. Clone the repository

```bash
git clone https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator.git
```

```bash
cd agentic-applications-for-unified-data-foundation-solution-accelerator
```

```bash
cp .env.example .env # or: copy .env.example .env
```

### 2.1 Get Fabric workspace Id
Open `.env` and set `FABRIC_WORKSPACE_ID` from [Microsoft Fabric](https://app.fabric.microsoft.com) URL

| Setting | Where to find it |
|---------|------------------|
| Workspace ID | URL after `/groups/` |
| Workspace name | Workspace settings |

### 3. Deploy Azure resources

```bash
azd auth login
```

```bash
azd up
```


When you start the deployment, you will need to set the following parameters: 

| **Setting**                                 | **Description**                                                                                           | **Default value**      |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ---------------------- |
| **Azure Region**                            | The region where resources will be created.                                                               | *(empty)*              |
| **Environment Name**                        | A unique **3–20 character alphanumeric value** used to prefix resources, preventing conflicts with others.            | env\_name              |
| **AI Model Location**                        | The region where AI model will be created            | *(empty)              |

*Different tenant? Use: `azd auth login --tenant-id <tenant-id>`*



### 4. Setup Python environment

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate   # or: source .venv/bin/activate
```

```bash
pip install uv && uv pip install -r scripts/requirements.txt
```

### 5. Build the solution

```bash
az login
```

> **VS Code Web users:** Use `az login --use-device-code` since browser-based login is not supported in VS Code Web.

```bash
python scripts/00_build_solution.py --from 02
```

> **Note:** Press **Enter** key to start or **Ctrl+C** to cancel the process.

### 6. Test the agent

```bash
python scripts/08_test_agent.py
```

**Sample questions to try:**

- "How many tickets are high priority"
- "What is the average score from inspections?"
- "What constitutes a failed inspection?"
- "Do any inspections violate quality control standards in our Inspection Procedures?"

### 7. Create the Ontology

Follow the step-by-step guide to create an Ontology in Microsoft Fabric for your scenario:

👉 [Create Ontology Guide](./01-deploy/05-ontology-creation.md)

This sets up entity types (Tickets, Inspections), data bindings from your Lakehouse tables, and relationships between them.

### 8. Test the Fabric Data Agent

1. Go to your [Microsoft Fabric](https://app.fabric.microsoft.com/) workspace
2. Select "New item" → Search for "Data Agent" → select data agent, provide a name and click create
3. Add data source → Select your Ontology resource for this workshop
4. Click Agent instructions from top menu and add the below agent instructions:
    ```
    You are a helpful assistant that can answer user questions using data.
    Support group by in GQL.
    ```
5. Click Publish from the top menu and select Publish. 

> Note: The Ontology set up may take a few minutes so retry after some time if you don't see good responses. 

**Sample questions to try:**

- "How many tickets are high priority"
- "What is the average score from inspections?"
- "What constitutes a failed inspection?"
- "Do any inspections violate quality control standards in our Inspection Procedures?"

### 9. Deploy and launch the application

```bash
azd env set AZURE_ENV_DEPLOY_APP true
```

```bash
azd up
```

### 10. Set up app permissions

```bash
python scripts/00_build_solution.py --from 09
```

> **Note:** Press **Enter** key to start or **Ctrl+C** to cancel the process.

After the agent configuration & API permission set up completes, open the app URL shown in the output.

### 11. Customize for Your Industry (Optional)

Follow steps in this page to  [Customize for your use case](./02-customize/index.md).

---

## Option B: Azure-Only Deployment

### 1. Clone the repository

```bash
git clone https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator.git
```

```bash
cd agentic-applications-for-unified-data-foundation-solution-accelerator
```

### 2. Enable Azure-only mode

```bash
azd env set AZURE_ENV_ONLY true
```

### 3. Deploy Azure resources

```bash
azd auth login
```

```bash
azd up
```

*Choose environment name and region. Different tenant? Use: `azd auth login --tenant-id <tenant-id>`*

### 4. Setup Python environment

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate   # or: source .venv/bin/activate
```

```bash
pip install uv && uv pip install -r scripts/requirements.txt
```

```bash
cp .env.example .env # or: copy .env.example .env
```


### 5. Build the solution

```bash
az login
```

> **VS Code Web users:** Use `az login --use-device-code` since browser-based login is not supported in VS Code Web.

```bash
python scripts/00_build_solution.py --from 04
```

> **Note:** Press **Enter** key to start or **Ctrl+C** to cancel the process.

### 6. Test the agent

```bash
python scripts/08_test_agent.py
```

**Sample questions to try:**

- "How many outages occurred last month?"
- "What's the average resolution time?"
- "What are the policies for notifying customers of outages?"
- "Which outages exceeded the maximum duration defined in our policy?"

### 7. Deploy the application

```bash
azd env set AZURE_ENV_DEPLOY_APP true
```

```bash
azd up
```

### 8. Set up app permissions

```bash
python scripts/00_build_solution.py --from 09
```

> **Note:** Press **Enter** key to start or **Ctrl+C** to cancel the process.

After the agent configuration & API permission set up completes, open the app URL shown in the output. 

### 9. Customize for Your Industry (Optional)

Follow steps in this page to  [Customize for your use case](./02-customize/index.md).


----------

**Repository:** [github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator](https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator)
