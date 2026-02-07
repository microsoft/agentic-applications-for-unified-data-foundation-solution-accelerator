# Quick Deploy Guide

## Prerequisites

- Azure subscription with Contributor access & Role Based Access Control access
- VS Code, Azure Developer CLI ([aka.ms/azd](https://aka.ms/azd)), Python 3.10+, Git
- For Fabric deployment: Microsoft Fabric workspace (F2+ capacity) with admin permissions

## Choose Your Development Environment

Local Visual Studio Code: Open Visual Studio Code. From the File menu, select Open Folder and choose the folder where you want to deploy the workshop.

Or choose one of the options below:

[![Open in GitHub Codespaces](https://img.shields.io/badge/GitHub-Codespaces-blue?logo=github)](https://codespaces.new/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator)
[![Open in VS Code Dev Containers](https://img.shields.io/badge/VS%20Code-Dev%20Containers-blue?logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator)
[![Open in VS Code Web](https://img.shields.io/badge/VS%20Code-Open%20in%20Web-blue?logo=visualstudiocode)](https://vscode.dev/azure/?vscode-azure-exp=foundry&agentPayload=eyJiYXNlVXJsIjogImh0dHBzOi8vcmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbS9taWNyb3NvZnQvYWdlbnRpYy1hcHBsaWNhdGlvbnMtZm9yLXVuaWZpZWQtZGF0YS1mb3VuZGF0aW9uLXNvbHV0aW9uLWFjY2VsZXJhdG9yL21haW4vaW5mcmEvdnNjb2RlX3dlYiIsICJpbmRleFVybCI6ICIvaW5kZXguanNvbiIsICJ2YXJpYWJsZXMiOiB7ImFnZW50SWQiOiAiIiwgImNvbm5lY3Rpb25TdHJpbmciOiAiIiwgInRocmVhZElkIjogIiIsICJ1c2VyTWVzc2FnZSI6ICIiLCAicGxheWdyb3VuZE5hbWUiOiAiIiwgImxvY2F0aW9uIjogIiIsICJzdWJzY3JpcHRpb25JZCI6ICIiLCAicmVzb3VyY2VJZCI6ICIiLCAicHJvamVjdFJlc291cmNlSWQiOiAiIiwgImVuZHBvaW50IjogIiJ9LCAiY29kZVJvdXRlIjogWyJhaS1wcm9qZWN0cy1zZWsiLCAicHl0aG9uIiwgImRlZmF1bHQtYXp1cmUtYXV0aCIsICJlbmRwb2ludCJdfQ==)


---

## Option A: Full Deployment (Fabric + Foundry)

### 1. Configure Fabric workspace

Create a new [Fabric workspace](./01-deploy/02-setup-fabric.md), then:

```bash
cp .env.example .env # or: copy .env.example .env
```

Open `.env` and set `FABRIC_WORKSPACE_ID` from [Microsoft Fabric](https://app.fabric.microsoft.com) URL

### 2. Clone the repository

```bash
git clone https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator.git
```

```bash
cd agentic-applications-for-unified-data-foundation-solution-accelerator
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

### 5. Build the solution

```bash
az login
```

```bash
python scripts/00_build_solution.py --from 02
```

### 6. Test the agent

```bash
python scripts/08_test_agent.py
```

**Sample questions to try:**

- "How many outages occurred last month?"
- "What's the average resolution time?"
- "What are the policies for notifying customers of outages?"
- "Which outages exceeded the maximum duration defined in our policy?"

### 7. Test the Fabric Data Agent

1. Go to your [Microsoft Fabric](https://app.fabric.microsoft.com/) workspace
2. Select "New item" → Search for "Data Agent"
3. Add data source → Select your Ontology resource
4. Add Agent instructions:
```
You are a helpful assistant that can answer user questions using data.
Support group by in GQL.
```

**Sample questions to try:**

- "Which outages had the most customer impact?"
- "Show me the top 5 regions by total outage duration"
- "What's the total number of tickets by priority?"

### 8. Deploy and launch the application

```bash
azd env set AZURE_ENV_DEPLOY_APP true
```

```bash
azd up
```

After deployment completes, open the app URL shown in the output. **Done!**

### 9. Customize for Your Industry (Optional)

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

```bash
python scripts/00_build_solution.py --from 04
```

### 6. Test the agent

```bash
python scripts/08_test_agent.py
```

**Sample questions to try:**

- "How many outages occurred last month?"
- "What's the average resolution time?"
- "What are the policies for notifying customers of outages?"
- "Which outages exceeded the maximum duration defined in our policy?"

### 7. Deploy and launch the application

```bash
azd env set AZURE_ENV_DEPLOY_APP true
```

```bash
azd up
```

### 8. Update agent configuration

```bash
python scripts/00_build_solution.py --from 05
```

After deployment completes, open the app URL shown in the output. **Done!**

### 9. Customize for Your Industry (Optional)

Follow steps in this page to  [Customize for your use case](./02-customize/index.md).


----------

**Repository:** [github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator](https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator)
