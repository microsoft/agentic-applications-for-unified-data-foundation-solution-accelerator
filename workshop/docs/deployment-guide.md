## Prerequisites

- Azure subscription with Contributor access & Role Based Access Control access
- Microsoft Fabric workspace (F2+ capacity) with admin permissions
- VS Code, Azure Developer CLI ([aka.ms/azd](https://aka.ms/azd)), Python 3.10+, Git

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator.git
```

```bash
cd agentic-applications-for-unified-data-foundation-solution-accelerator
```

### 2. (Optional) Enable Azure-only mode
```bash
azd env set AZURE_ENV_ONLY true
```
*Skip this if you have Microsoft Fabric Access. Uses Azure SQL instead of Fabric SQL.*

### 3. Deploy Azure resources (~7 min)
Authenticate to Azure Developer CLI (azd): 
```bash
azd auth login
```

Deploy azure resources:
```bash
azd up
```
*Choose environment name and region. To authenticate with Azure Developer CLI (azd), use the following command with your Tenant ID: azd auth login --tenant-id <tenant-id>*



### 4. Configure Fabric workspace
Create a new [Fabric workspace](./01-deploy/02-setup-fabric.md). 

*Skip to step 4 if you are using Azure-only mode*

Once you have your workspace ID run the following command: 
```bash
cp .env.example .env
```


Open the `.env` and set `FABRIC_WORKSPACE_ID` from [Microsoft Fabric](https://app.fabric.microsoft.com) URL

### 5. Setup Python environment

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate   # or: source .venv/bin/activate
```

```bash
pip install uv && uv pip install -r scripts/requirements.txt
```

### 6. Build the solution (~5 min)

```bash
az login
```

```bash
python scripts/00_build_solution.py --from 02
```

*Azure-only mode? Use:  `python scripts/00_build_solution.py --from 04`*

### 7. Test the agent

```bash
python scripts/08_test_agent.py
```

### 7.1 Test the Fabric Data Agent
1. Go to your [Microsoft Fabric](https://app.fabric.microsoft.com/) workspace
2. Select "New item" 
3. Search for and select "Data Agent" 
4. Select add data source and select your Ontology resource created in the previous step. 
5. Select Agent instructions and paste the below instructions. 
``` 
You are a helpful assistant that can answer user questions using data.
Support group by in GQL.
```

### 8. Deploy and launch the application

```bash
azd env set AZURE_ENV_DEPLOY_APP true
```

```bash
azd up
```

After deployment completes, open the app URL shown in the output

### 9. (Azure-only mode) Update agent configuration

```bash
python scripts/00_build_solution.py --from 05
```
*Only run this if you set AZURE_ENV_DEPLOY_APP=true. Skip this step if using Fabric mode.*

---

## Try These Questions

| Type | Example |
|------|---------|
| **Structured** | "How many outages occurred last month?" \| "What is the average resolution time?" |
| **Unstructured** | "What are the policies for notifying customers of outages?" |
| **Combined** | "Which outages exceeded the maximum duration defined in our policy?" |

---

## Customize for Your Industry

```bash
python scripts/00_build_solution.py --clean --industry "Insurance" --usecase "Claims processing"
```

**Industries:** Telecommunications | Insurance | Finance | Retail | Manufacturing | Energy

**Tip:** Use GitHub Copilot Chat (Ctrl+I) for help with errors

---

**Repository:** [github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator](https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator)
