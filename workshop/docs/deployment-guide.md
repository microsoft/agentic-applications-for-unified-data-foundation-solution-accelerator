# Build faster with Solution Accelerators | Foundry IQ + Fabric IQ

## Prerequisites

- Azure subscription with Contributor access
- Microsoft Fabric workspace (F2+ capacity) with admin permissions
- VS Code, Azure Developer CLI ([aka.ms/azd](https://aka.ms/azd)), Python 3.10+, Git

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator.git
cd agentic-applications-for-unified-data-foundation-solution-accelerator
```

### 2. Deploy Azure resources (~7 min)

```bash
azd auth login
azd up
```

Choose environment name and region (eastus2 or westus2 recommended). If needed:

```bash
azd auth login --tenant-id <tenant-id>
```

### 3. Configure Fabric workspace

```bash
cp .env.example .env
```

Edit `.env`: Set `FABRIC_WORKSPACE_ID` from app.fabric.microsoft.com URL

### 4. Setup Python environment

```bash
python -m venv .venv
.venv\Scripts\activate   # or: source .venv/bin/activate
pip install uv && uv pip install -r scripts/requirements.txt
```

### 5. Build the solution (~5 min)

```bash
python scripts/00_build_solution.py --from 02
```

No Fabric? Use: `python scripts/00_build_solution.py --from 04`

### 6. Test the agent

```bash
python scripts/08_test_agent.py
```

### 7. Deploy and launch the application

```bash
azd env set AZURE_ENV_DEPLOY_APP true
azd up
```

After deployment completes, open the app URL shown in the output

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
