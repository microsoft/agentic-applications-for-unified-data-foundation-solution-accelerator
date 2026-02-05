# Configure dev environment

## Python Environment

### Create and Activate

```bash
cd scripts
python -m venv .venv
```

=== "Windows"

    ```powershell
    .venv\Scripts\activate
    ```

=== "macOS/Linux"

    ```bash
    source .venv/bin/activate
    ```

### Install Dependencies

=== "Fast (Recommended)"

    ```bash
    pip install uv && uv pip install -r requirements.txt
    ```

=== "Standard"

    ```bash
    pip install -r requirements.txt
    ```

### Verify Setup

```bash
python -c "import azure.ai.projects; print('Ready!')"
```

## Configure Fabric

### Get Your Workspace ID

1. Go to [Microsoft Fabric](https://app.fabric.microsoft.com/)
2. Open your workspace
3. Copy the workspace ID from the URL:

```
https://app.fabric.microsoft.com/groups/{workspace-id}/...
```

### Update Environment File

Copy `.env.example` to `.env` and update your Fabric settings:

```bash
cp .env.example .env
```

Edit `.env` in the project root:

```env
# --- Microsoft Fabric (required) ---
FABRIC_WORKSPACE_ID=your-workspace-id-here

# --- Data Folder (pre-populated with default scenario) ---
DATA_FOLDER=data/default
```

## Checkpoint

Before proceeding:

- [x] `azd up` completed successfully
- [x] Python environment activated
- [x] Dependencies installed
- [x] Fabric workspace ID configured

!!! success "Ready to Run"
    Continue to the next step to see it in action.

---

[← Create Fabric workspace](02-setup-fabric.md) | [Build solution →](04-run-scenario.md)
