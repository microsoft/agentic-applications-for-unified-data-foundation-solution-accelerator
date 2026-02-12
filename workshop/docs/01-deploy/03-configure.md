# Configure dev environment

## Python Environment

### Create and Activate

```bash
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
    pip install uv && uv pip install -r scripts/requirements.txt
    ```

=== "Standard"

    ```bash
    pip install -r scripts/requirements.txt
    ```

### Verify Setup

```bash
python -c "import azure.ai.projects; print('Ready')"
```

## Configure Fabric

!!! note "Using Azure-Only Mode?"
    If you set `AZURE_ENV_ONLY=true` before deployment, **skip this section**. Fabric configuration is not required when using Azure SQL.

### Get Your Workspace ID

1. Go to [Microsoft Fabric](https://app.fabric.microsoft.com/)
2. Open your workspace
3. Note the workspace ID from the URL — you'll pass it as a parameter in the next step:

```
https://app.fabric.microsoft.com/groups/{workspace-id}/...
```


## Checkpoint

Before proceeding:

- [x] `azd up` completed successfully
- [x] Python environment activated
- [x] Dependencies installed
- [x] Fabric workspace ID noted (skip if using Azure-only mode)

!!! success "Ready to Run"
    Continue to the next step to see it in action.

---

[← Create Fabric workspace](02-setup-fabric.md) | [Build solution →](04-run-scenario.md)
