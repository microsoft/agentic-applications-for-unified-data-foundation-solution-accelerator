# Local Development Setup Guide

This guide provides comprehensive instructions for setting up the Agentic Applications For Unified Data Foundation Solution Accelerator for local development across Windows and Linux platforms.

## Important Setup Notes

### Architecture

This application consists of **two separate services** that run independently:

1. **Backend API** - REST API server for the frontend application (implemented in both Python and .NET)
2. **Frontend** - React-based user interface

> **⚠️ Critical: Each service must run in its own terminal/console window**
>
> - **Do NOT close terminals** while services are running
> - Open **2 separate terminal windows** for local development
> - Each service will occupy its terminal and show live logs
>
> **Terminal Organization:**
> - **Terminal 1**: Backend API - HTTP server on port 8000
> - **Terminal 2**: Frontend - Development server on port 3000

### Path Conventions

**All paths in this guide are relative to the repository root directory:**

```bash
agentic-applications-for-unified-data-foundation-solution-accelerator/    ← Repository root (start here)
├── src/
│   ├── api/                         
│   │   ├── python/
│   │   │   ├── .venv/               ← Python virtual environment
│   │   │   ├── app.py               ← API entry point
│   │   │   └── .env                 ← Python Backend API config file
│   │   └── dotnet/                   
│   │       ├── Program.cs           ← API entry point
│   │       └── appsettings.json     ← Dotnet Backend API config file
│   └── App/                           
│       ├── node_modules/                    
│       └── .env                     ← Frontend config file
└── documents/                       ← Documentation (you are here)
```

## Step 1: Prerequisites - Install Required Tools

**Note**: You can choose either Python or .NET for the backend API. Install the corresponding SDK based on your preference:
- **Python Backend**: Requires Python 3.12+
- **.NET Backend**: Requires .NET SDK 8.0+

### Windows Development

#### Option 1: Native Windows (PowerShell)

```powershell
# Install Git
winget install Git.Git

# Install Node.js for frontend
winget install OpenJS.NodeJS.LTS

# For Python Backend (Option A):
winget install Python.Python.3.12

# For .NET Backend (Option B):
winget install Microsoft.DotNet.SDK.8
```

#### Option 2: Windows with WSL2 (Recommended)

```bash
# Install WSL2 first (run in PowerShell as Administrator):
# wsl --install -d Ubuntu

# Then in WSL2 Ubuntu terminal for Frontend::
sudo apt update && sudo apt install git curl nodejs npm -y

# For Python Backend (Option A):
sudo apt install python3.12 python3.12-venv -y

# For .NET Backend (Option B):
wget https://dot.net/v1/dotnet-install.sh -O dotnet-install.sh
chmod +x dotnet-install.sh
./dotnet-install.sh --channel 8.0
echo 'export PATH=$PATH:$HOME/.dotnet' >> ~/.bashrc
source ~/.bashrc
```

### Linux Development

#### Ubuntu/Debian

```bash
# For Frontend:
sudo apt update && sudo apt install git curl nodejs npm -y

# For Python Backend (Option A):
sudo apt install python3.12 python3.12-venv -y

# For .NET Backend (Option B):
wget https://dot.net/v1/dotnet-install.sh -O dotnet-install.sh
chmod +x dotnet-install.sh
./dotnet-install.sh --channel 8.0
echo 'export PATH=$PATH:$HOME/.dotnet' >> ~/.bashrc
source ~/.bashrc
```

#### RHEL/CentOS/Fedora

```bash
# For Frontend:
sudo dnf install git curl gcc nodejs npm -y

# For Python Backend (Option A):
sudo dnf install python3.12 python3.12-devel -y

# For .NET Backend (Option B):
wget https://dot.net/v1/dotnet-install.sh -O dotnet-install.sh
chmod +x dotnet-install.sh
./dotnet-install.sh --channel 8.0
echo 'export PATH=$PATH:$HOME/.dotnet' >> ~/.bashrc
source ~/.bashrc
```

### Clone the Repository

```bash
git clone https://github.com/microsoft/agentic-applications-for-unified-data-foundation-solution-accelerator.git

cd agentic-applications-for-unified-data-foundation-solution-accelerator
```

**Before starting any step, ensure you are in the repository root directory:**

```bash
# Verify you're in the correct location
pwd  # Linux/macOS - should show: .../agentic-applications-for-unified-data-foundation-solution-accelerator
Get-Location  # Windows PowerShell - should show: ...\agentic-applications-for-unified-data-foundation-solution-accelerator

# If not, navigate to repository root
cd path/to/agentic-applications-for-unified-data-foundation-solution-accelerator
```

## Step 2: Development Tools Setup

### Visual Studio Code (Recommended)

#### Required Extensions

Create `.vscode/extensions.json` in the workspace root and copy the following JSON:

```json
{
    "recommendations": [
        "ms-python.python",
        "ms-python.pylint",
        "ms-python.black-formatter",
        "ms-python.isort",
        "ms-vscode-remote.remote-wsl",
        "ms-vscode-remote.remote-containers",
        "redhat.vscode-yaml",
        "ms-vscode.azure-account",
        "ms-python.mypy-type-checker"
    ]
}
```

VS Code will prompt you to install these recommended extensions when you open the workspace.

#### Settings Configuration

Create `.vscode/settings.json` and copy the following JSON:

```json
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.terminal.activateEnvironment": true,
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "files.associations": {
        "*.yaml": "yaml",
        "*.yml": "yaml"
    }
}
```

## Step 3: Authentication Setup

Before configuring services, authenticate with Azure:

```bash
# Login to Azure CLI
az login

# Set your subscription
az account set --subscription "your-subscription-id"

# Verify authentication
az account show
```

### Required Azure RBAC Permissions

To run the application locally, your Azure account needs the following role assignment on the deployed resources:

#### AI Foundry Access

**Linux/macOS/WSL (Bash):**
```bash
# Get your principal ID
PRINCIPAL_ID=$(az ad signed-in-user show --query id -o tsv)

# Assign Azure AI User role
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Azure AI User" \
  --scope "\subscriptions\<subscription-id>\resourceGroups\<resource-group>\providers\Microsoft.CognitiveServices\accounts\<ai-foundry-account>"
```

**Windows (PowerShell):**
```powershell
# Get your principal ID
$PRINCIPAL_ID = az ad signed-in-user show --query id -o tsv

# Assign Azure AI User role
az role assignment create `
  --assignee $PRINCIPAL_ID `
  --role "Azure AI User" `
  --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<ai-foundry-account>"
```

### Fabric Workspace Access

Your access requirements depend on whether you're deploying or running locally:

- **For Deployment**: Admin role on the Fabric workspace is required to provision and configure resources
- **For Local Development**: Contributor role on the Fabric workspace is sufficient to run the application locally

If you don't have the necessary permissions, ask the workspace admin to assign you the appropriate role.

**Note**: RBAC permission changes can take 5-10 minutes to propagate. If you encounter "Forbidden" errors after assigning roles, wait a few minutes and try again.

## Step 4: Backend API Setup & Run Instructions

> **📋 Terminal Reminder**: Open a **terminal window (Terminal 1)** for the Backend API. All commands assume you start from the **repository root directory**.

The Backend API provides REST endpoints for the frontend and handles API requests. This solution supports **two backend implementations**:

- **Option A: Python Backend** (FastAPI) - Located in `src/api/python/`
- **Option B: .NET Backend** (ASP.NET Core) - Located in `src/api/dotnet/`

**Choose one backend to run based on your preference and the SDK you installed in Step 1.**

---

### Option A: Python Backend Setup

#### 4A.1. Navigate to Python API Directory

```bash
# From repository root
cd src/api/python
```

#### 4A.2. Configure Python API Environment Variables

Create a `.env` file in the `src/api/python` directory:

```bash
# Copy the sample file
cp .env.sample .env  # Linux
# or
Copy-Item .env.sample .env  # Windows PowerShell
```

Edit the `.env` file with your Azure configuration values from api resource.

#### 4A.3. Install Python API Dependencies

```bash
# Create and activate virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # Linux
# or
.venv\Scripts\activate  # Windows PowerShell

# Install dependencies
pip install -r requirements.txt
```

#### 4A.4. Run the Python Backend API

```bash
# Run with the application entry point
python app.py
```

The Python Backend API will start at:
- API: `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`

---

### Option B: .NET Backend Setup

#### 4B.1. Navigate to .NET API Directory

```bash
# From repository root
cd src/api/dotnet
```

#### 4B.2. Configure .NET API Settings

Create an `appsettings.json` file in the `src/api/dotnet` directory:

```bash
# Copy the sample file
cp appsettings.json.sample appsettings.json  # Linux
# or
Copy-Item appsettings.json.sample appsettings.json  # Windows PowerShell
```
Edit the `appsettings.json` file with your Azure configuration values from api resource.

#### 4B.3. Restore .NET Dependencies

```bash
# Restore NuGet packages
dotnet restore
```

#### 4B.4. Run the .NET Backend API

```bash
# Run the application
dotnet run
```

**Alternative**: For hot reload during development:

```bash
dotnet watch run
```

The .NET Backend API will start at:
- API: `http://localhost:8000`
- Swagger Documentation: `http://localhost:8000/swagger`

---

## Step 5: Frontend (UI) Setup & Run Instructions

> **📋 Terminal Reminder**: Open a **second dedicated terminal window (Terminal 2)** for the Frontend. Keep Terminal 1 (Backend API) running. All commands assume you start from the **repository root directory**.

The UI is located under `src/App`.

### 5.1. Navigate to Frontend Directory

```bash
# From repository root
cd src/App
```

### 5.2. Install UI Dependencies

```bash
npm install
```

### 5.4. Start Development Server

```bash
npm start
```

The app will start at:

```
http://localhost:3000
```

## Step 6: Verify the Services Are Running

Before using the application, confirm services are running in separate terminals:

### Terminal Status Checklist

| Terminal | Service | Command | Expected Output | URL |
|----------|---------|---------|-----------------|-----|
| **Terminal 1** | Backend API (Python or .NET) | `python app.py` or `dotnet run` | Server startup message | http://localhost:8000 |
| **Terminal 2** | Frontend | `npm start` | `Local: http://localhost:3000/` | http://localhost:3000 |

### Quick Verification

**1. Check Backend API:**
```bash
# In a new terminal (Terminal 3)
# For Python backend:
curl http://localhost:8000/health

# For .NET backend:
curl http://localhost:8000/health
```

**2. Check Frontend:**
- Open browser to http://localhost:3000
- Should see the application UI

## Troubleshooting

### Common Issues

#### Service not starting?
- Ensure you're in the correct directory
- Verify virtual environment is activated (Python backend)
- Check that port is not already in use (8000 for backend, 3000 for frontend)
- Review error messages in the terminal

#### Can't access services?
- Verify firewall isn't blocking the required ports
- Try `http://localhost:port` instead of `http://127.0.0.1:port`
- Ensure services show "startup complete" messages

#### Python Version Issues

```bash
# Check available Python versions
python3 --version
python3.12 --version

# If python3.12 not found, install it:
# Ubuntu: sudo apt install python3.12
# Windows: winget install Python.Python.3.12
```

#### .NET Version Issues

```bash
# Check .NET SDK version
dotnet --version

# Should show 8.0.x or higher
# If not installed:
# Windows: winget install Microsoft.DotNet.SDK.8
# Linux: Follow the .NET installation steps in Step 1
```

#### Virtual Environment Issues

```bash
# Recreate virtual environment
rm -rf .venv  # Linux
# or Remove-Item -Recurse .venv  # Windows PowerShell

python -m venv .venv
# Activate and reinstall
source .venv/bin/activate  # Linux
# or .venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt
```

#### Permission Issues (Linux)

```bash
# Fix ownership of files
sudo chown -R $USER:$USER .
```

#### Windows-Specific Issues

```powershell
# PowerShell execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Long path support (Windows 10 1607+, run as Administrator)
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force

# SSL certificate issues
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org uv
```

### Environment Variable Issues

```bash
# Check environment variables are loaded
env | grep AZURE  # Linux
Get-ChildItem Env:AZURE*  # Windows PowerShell

# Validate .env file format
cat .env | grep -v '^#' | grep '='  # Should show key=value pairs
```

## Step 7: Next Steps

Once all services are running (as confirmed in Step 6), you can:

1. **Access the Application**: Open `http://localhost:3000` in your browser to explore the frontend UI
2. **Explore the Codebase**: 
   - Python backend: `src/api/python`
   - .NET backend: `src/api/dotnet`
   - Frontend: `src/App`
3. **Test API Endpoints**: Use the API documentation available at your backend URL

## Related Documentation

- [Deployment Guide](DeploymentGuide.md) - Production deployment instructions
- [Technical Architecture](TechnicalArchitecture.md) - System architecture overview