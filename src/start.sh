#!/bin/bash

echo "Starting the application setup..."

# Set root and config paths (resolve relative to script location, not cwd)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
AZURE_FOLDER="$ROOT_DIR/.azure"
CONFIG_FILE="$AZURE_FOLDER/config.json"
API_PYTHON_ENV_FILE="$ROOT_DIR/src/api/python/.env"
API_DOTNET_DIR="$ROOT_DIR/src/api/dotnet"

# ============================================================
#  Locate .env file (Azure deployment or local fallback)
# ============================================================

locate_env_file() {
    # Check if .azure folder exists
    if [ ! -d "$AZURE_FOLDER" ]; then
        echo ".azure folder not found. This is normal if Azure deployment hasn't been run yet."
        check_local_env
        return
    fi

    # Check if config.json exists
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "config.json not found in .azure folder. This is normal if Azure deployment hasn't been run yet."
        check_local_env
        return
    fi

    # Extract default environment name
    DEFAULT_ENV=$(grep -o '"defaultEnvironment"\s*:\s*"[^"]*"' "$CONFIG_FILE" | sed -E 's/.*"defaultEnvironment"\s*:\s*"([^"]*)".*/\1/')

    if [ -z "$DEFAULT_ENV" ]; then
        echo "Failed to extract defaultEnvironment from config.json."
        check_local_env
        return
    fi

    # Load .env file from Azure deployment
    ENV_FILE="$AZURE_FOLDER/$DEFAULT_ENV/.env"

    if [ -f "$ENV_FILE" ]; then
        echo "Found .env file in Azure deployment folder: $ENV_FILE"

        # Pre-check backend runtime stack from Azure .env
        _PRE_STACK=$(grep -m1 '^BACKEND_RUNTIME_STACK=' "$ENV_FILE" | cut -d'=' -f2-)
        # Strip surrounding quotes from value
        _PRE_STACK="${_PRE_STACK%\"}"
        _PRE_STACK="${_PRE_STACK#\"}"

        # Check if backend config already exists and ask for overwrite
        if [ "${_PRE_STACK,,}" = "dotnet" ]; then
            if [ -f "$API_DOTNET_DIR/appsettings.json" ]; then
                echo "Found existing appsettings.json in src/api/dotnet"
                read -p "Do you want to overwrite it with the Azure deployment .env? (y/N): " OVERWRITE_ENV
                if [[ "$OVERWRITE_ENV" =~ ^[Yy]$ ]]; then
                    echo "Overwriting with Azure deployment configuration..."
                else
                    echo "Preserving existing appsettings.json. Using local configuration."
                    SKIP_DOTNET_CONFIG="true"
                fi
            fi
        else
            if [ -f "$API_PYTHON_ENV_FILE" ]; then
                echo "Found existing .env file in src/api/python"
                read -p "Do you want to overwrite it with the Azure deployment .env? (y/N): " OVERWRITE_ENV
                if [[ "$OVERWRITE_ENV" =~ ^[Yy]$ ]]; then
                    echo "Overwriting with Azure deployment configuration..."
                else
                    echo "Preserving existing .env files. Using local configuration."
                    ENV_FILE="$API_PYTHON_ENV_FILE"
                fi
            fi
        fi
        return
    fi

    check_local_env
}

check_local_env() {
    echo "Checking for local .env files..."

    # Check python subfolder
    if [ -f "$API_PYTHON_ENV_FILE" ]; then
        echo "Using existing .env file from src/api/python for configuration."
        ENV_FILE="$API_PYTHON_ENV_FILE"
        return
    fi

    # Check parent api folder as legacy fallback
    if [ -f "$ROOT_DIR/src/api/.env" ]; then
        echo "Using existing .env file from src/api for configuration."
        ENV_FILE="$ROOT_DIR/src/api/.env"
        return
    fi

    echo ""
    echo "ERROR: No .env files found in any location."
    echo ""
    echo "Please choose one of the following options:"
    echo "  1. Run 'azd up' to deploy Azure resources and generate .env files"
    echo "  2. Manually create $API_PYTHON_ENV_FILE with required environment variables"
    echo "  3. Copy an existing .env file to src/api/python/.env"
    echo ""
    exit 1
}

locate_env_file

echo ""
echo "Using environment file: $ENV_FILE"

# ============================================================
#  Load all variables from .env as process env vars
#  This ensures Python/dotnet subprocesses inherit them
#  (fixes history.py reading env vars before load_dotenv)
# ============================================================
while IFS='=' read -r key value; do
    # Skip empty lines and comments
    [[ -z "$key" || "$key" == \#* ]] && continue
    # Strip trailing carriage return (Windows CRLF)
    key="${key%$'\r'}"
    value="${value%$'\r'}"
    # Strip surrounding quotes from value
    value="${value%\"}"
    value="${value#\"}"
    export "$key=$value"
done < "$ENV_FILE"

# Extract AZURE_SQLDB_SERVER short name for az cli commands (with fallback from SQLDB_SERVER)
if [ -z "$AZURE_SQLDB_SERVER" ] && [ -n "$SQLDB_SERVER" ]; then
    AZURE_SQLDB_SERVER="$SQLDB_SERVER"
fi
if [ -n "$AZURE_SQLDB_SERVER" ]; then
    AZURE_SQLDB_SERVER_NAME="${AZURE_SQLDB_SERVER%%.*}"
fi

# Normalize booleans to lowercase
IS_WORKSHOP=$(echo "${IS_WORKSHOP:-false}" | tr '[:upper:]' '[:lower:]')
AZURE_ENV_ONLY=$(echo "${AZURE_ENV_ONLY:-false}" | tr '[:upper:]' '[:lower:]')

# Default USE_CHAT_HISTORY_ENABLED to true if not set (for existing deployments)
USE_CHAT_HISTORY_ENABLED=$(echo "${USE_CHAT_HISTORY_ENABLED:-true}" | tr '[:upper:]' '[:lower:]')
export USE_CHAT_HISTORY_ENABLED

# Default backend to python if not set
BACKEND_RUNTIME_STACK="${BACKEND_RUNTIME_STACK:-python}"

echo ""
echo "Configuration:"
echo "  BACKEND_RUNTIME_STACK=$BACKEND_RUNTIME_STACK"
echo "  IS_WORKSHOP=$IS_WORKSHOP"
echo "  AZURE_ENV_ONLY=$AZURE_ENV_ONLY"
echo "  USE_CHAT_HISTORY_ENABLED=$USE_CHAT_HISTORY_ENABLED"
echo ""

# ============================================================
#  Read agent names and Fabric SQL settings from config files
# ============================================================
AGENT_IDS_FILE="$ROOT_DIR/data/default/config/agent_ids.json"
FABRIC_IDS_FILE="$ROOT_DIR/data/default/config/fabric_ids.json"

# Get agent names from env first, fallback to agent_ids.json
if [ -z "$AGENT_NAME_CHAT" ]; then
    if [ -f "$AGENT_IDS_FILE" ]; then
        AGENT_NAME_CHAT=$(python3 -c "import json; print(json.load(open('$AGENT_IDS_FILE'))['chat_agent_name'])" 2>/dev/null)
        AGENT_NAME_TITLE=$(python3 -c "import json; print(json.load(open('$AGENT_IDS_FILE'))['title_agent_name'])" 2>/dev/null)
        export AGENT_NAME_CHAT AGENT_NAME_TITLE
        echo "Loaded agent names from agent_ids.json: AGENT_NAME_CHAT=$AGENT_NAME_CHAT, AGENT_NAME_TITLE=$AGENT_NAME_TITLE"
    else
        echo "[WARN] agent_ids.json not found at $AGENT_IDS_FILE. Agent names will not be configured."
    fi
else
    echo "Loaded agent names from env: AGENT_NAME_CHAT=$AGENT_NAME_CHAT, AGENT_NAME_TITLE=$AGENT_NAME_TITLE"
fi

# Load Fabric SQL settings (needed unless workshop + azure-only mode)
# Python code: get_db_connection() uses Azure SQL only when IS_WORKSHOP=true AND AZURE_ENV_ONLY=true
# All other combinations use Fabric SQL
USE_FABRIC_SQL="true"
if [ "$IS_WORKSHOP" = "true" ] && [ "$AZURE_ENV_ONLY" = "true" ]; then
    USE_FABRIC_SQL="false"
fi

if [ "$USE_FABRIC_SQL" = "true" ]; then
    if [ -z "$FABRIC_SQL_SERVER" ]; then
        if [ -f "$FABRIC_IDS_FILE" ]; then
            FABRIC_SQL_SERVER=$(python3 -c "import json; print(json.load(open('$FABRIC_IDS_FILE'))['sql_endpoint'])" 2>/dev/null)
            FABRIC_SQL_DATABASE=$(python3 -c "import json; print(json.load(open('$FABRIC_IDS_FILE'))['lakehouse_name'])" 2>/dev/null)
            export FABRIC_SQL_SERVER FABRIC_SQL_DATABASE
            echo "Loaded Fabric SQL from fabric_ids.json: SERVER=$FABRIC_SQL_SERVER, DATABASE=$FABRIC_SQL_DATABASE"
        else
            echo "[WARN] Fabric SQL mode required but fabric_ids.json not found. Database connections may fail."
        fi
    else
        echo "Loaded Fabric SQL from env: SERVER=$FABRIC_SQL_SERVER, DATABASE=$FABRIC_SQL_DATABASE"
    fi
else
    echo "Using Azure SQL mode (IS_WORKSHOP=true, AZURE_ENV_ONLY=true). AZURE_SQLDB_SERVER=$AZURE_SQLDB_SERVER"
fi

# ============================================================
#  Configure backend .env / appsettings
# ============================================================

# --- Python backend configuration ---
if [ "$BACKEND_RUNTIME_STACK" = "python" ]; then
    # Guard: skip copy when source and destination are the same file
    if [ "$(realpath "$ENV_FILE")" = "$(realpath "$API_PYTHON_ENV_FILE")" ]; then
        echo "Using existing src/api/python/.env"
    else
        cp "$ENV_FILE" "$API_PYTHON_ENV_FILE"
    fi

    # Upsert helper: update existing key or append if not present
    upsert_env() {
        local key="$1" val="$2" file="$3"
        if grep -qi "^${key}=" "$file" 2>/dev/null; then
            sed -i.bak "s/^${key}=.*/${key}=${val}/" "$file" && rm -f "${file}.bak"
        else
            echo "${key}=${val}" >> "$file"
        fi
    }

    if [ -n "$AGENT_NAME_CHAT" ]; then
        upsert_env "AGENT_NAME_CHAT" "$AGENT_NAME_CHAT" "$API_PYTHON_ENV_FILE"
        upsert_env "AGENT_NAME_TITLE" "$AGENT_NAME_TITLE" "$API_PYTHON_ENV_FILE"
    fi
    # Upsert Fabric SQL settings when needed
    if [ "$USE_FABRIC_SQL" = "true" ] && [ -n "$FABRIC_SQL_SERVER" ]; then
        upsert_env "FABRIC_SQL_SERVER" "$FABRIC_SQL_SERVER" "$API_PYTHON_ENV_FILE"
        upsert_env "FABRIC_SQL_DATABASE" "$FABRIC_SQL_DATABASE" "$API_PYTHON_ENV_FILE"
    fi

    # Add or update APP_ENV=dev
    upsert_env "APP_ENV" "dev" "$API_PYTHON_ENV_FILE"
    echo "Configured src/api/python/.env"
fi

# --- Dotnet backend configuration ---
if [ "$BACKEND_RUNTIME_STACK" = "dotnet" ] && [ -d "$API_DOTNET_DIR" ]; then
    if [ "$SKIP_DOTNET_CONFIG" = "true" ]; then
        echo "Preserving existing src/api/dotnet/appsettings.json"
    else
        # Generate appsettings.json from sample with env values populated
        echo "Generating src/api/dotnet/appsettings.json from environment values..."
        if [ -f "$API_DOTNET_DIR/appsettings.json.sample" ]; then
            python3 -c "
import json, os, sys

with open('$API_DOTNET_DIR/appsettings.json.sample', 'r') as f:
    config = json.load(f)

env_keys = [
    'FABRIC_SQL_CONNECTION_STRING', 'FABRIC_SQL_DATABASE', 'FABRIC_SQL_SERVER',
    'AGENT_NAME_CHAT', 'AGENT_NAME_TITLE', 'API_UID',
    'APPINSIGHTS_INSTRUMENTATIONKEY', 'APPLICATIONINSIGHTS_CONNECTION_STRING',
    'AZURE_AI_AGENT_API_VERSION', 'AZURE_AI_AGENT_ENDPOINT', 'AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME',
    'AZURE_ENV_OPENAI_API_VERSION', 'AZURE_ENV_GPT_MODEL_NAME', 'AZURE_OPENAI_ENDPOINT',
    'AZURE_OPENAI_RESOURCE', 'DISPLAY_CHART_DEFAULT', 'SOLUTION_NAME',
    'USE_AI_PROJECT_CLIENT', 'USE_CHAT_HISTORY_ENABLED'
]

# Fallback mappings: new_key -> old_key (for backward compatibility)
fallback_keys = {
    'AZURE_ENV_GPT_MODEL_NAME': 'AZURE_OPENAI_DEPLOYMENT_MODEL',
    'AZURE_ENV_OPENAI_API_VERSION': 'AZURE_OPENAI_API_VERSION'
}

for key in env_keys:
    val = os.environ.get(key, '')
    # Try fallback if primary key is empty
    if not val and key in fallback_keys:
        val = os.environ.get(fallback_keys[key], '')
    if val or key in config:
        config[key] = val

config['APP_ENV'] = 'dev'

with open('$API_DOTNET_DIR/appsettings.json', 'w') as f:
    json.dump(config, f, indent=2)
"
        fi
        echo "Configured src/api/dotnet/appsettings.json with environment values"
    fi
fi

# Set process env vars for local development (dotnet inherits these via IConfiguration)
export APP_ENV="dev"
export USE_CHAT_HISTORY_ENABLED
if [ -n "$AGENT_NAME_CHAT" ]; then
    export AGENT_NAME_CHAT
    export AGENT_NAME_TITLE
fi
if [ "$USE_FABRIC_SQL" = "true" ] && [ -n "$FABRIC_SQL_SERVER" ]; then
    export FABRIC_SQL_SERVER
    export FABRIC_SQL_DATABASE
fi

# ============================================================
#  Write frontend .env
# ============================================================
APP_ENV_FILE="$ROOT_DIR/src/App/.env"
cat > "$APP_ENV_FILE" <<EOF
REACT_APP_API_BASE_URL=http://127.0.0.1:8000
REACT_APP_IS_WORKSHOP=$IS_WORKSHOP
REACT_APP_CHAT_LANDING_TEXT=You can ask questions around sales, products and orders.
EOF
echo "Updated src/App/.env with frontend configuration"

# ============================================================
#  Authenticate with Azure
# ============================================================
echo ""
echo "Checking Azure login status..."
if az account show --query id --output tsv >/dev/null 2>&1; then
    echo "Already authenticated with Azure."
else
    echo "Not authenticated. Attempting Azure login..."
    az login --use-device-code --output none
    az account show --query "[name, id]" --output tsv
    echo "Logged in successfully."
fi

# Get signed-in user ID
signed_user_id=$(az ad signed-in-user show --query id -o tsv)

# ============================================================
#  Cosmos DB role assignment (only when account is configured)
# ============================================================
if [ -n "$AZURE_COSMOSDB_ACCOUNT" ]; then
    roleExists=$(az cosmosdb sql role assignment list \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --account-name "$AZURE_COSMOSDB_ACCOUNT" \
        --query "[?roleDefinitionId.ends_with(@, '00000000-0000-0000-0000-000000000002') && principalId == '$signed_user_id']" \
        -o tsv 2>/dev/null)
    if [ -n "$roleExists" ]; then
        echo "User already has the Cosmos DB Built-in Data Contributor role."
    else
        echo "Assigning Cosmos DB Built-in Data Contributor role..."
        MSYS_NO_PATHCONV=1 az cosmosdb sql role assignment create \
            --resource-group "$AZURE_RESOURCE_GROUP" \
            --account-name "$AZURE_COSMOSDB_ACCOUNT" \
            --role-definition-id 00000000-0000-0000-0000-000000000002 \
            --principal-id "$signed_user_id" \
            --scope "/" \
            --output none
        echo "Cosmos DB Built-in Data Contributor role assigned successfully."
    fi
else
    echo "[INFO] No Cosmos DB account configured, skipping role assignment."
fi

# ============================================================
#  Azure SQL Server AAD admin (only when AZURE_SQLDB_SERVER is set)
# ============================================================
if [ -n "$AZURE_SQLDB_SERVER" ]; then
    SQLADMIN_USERNAME=$(az account show --query user.name --output tsv)
    echo "Assigning Azure SQL Server AAD admin role to $SQLADMIN_USERNAME..."
    az sql server ad-admin create \
        --display-name "$SQLADMIN_USERNAME" \
        --object-id "$signed_user_id" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --server "$AZURE_SQLDB_SERVER_NAME" \
        --output tsv >/dev/null 2>&1
    echo "Azure SQL Server AAD admin role assigned successfully."
else
    echo "[INFO] No Azure SQL Server configured, skipping admin role assignment."
fi

# ============================================================
#  Azure AI User role assignment (only when AI_FOUNDRY_RESOURCE_ID is set)
# ============================================================
if [ -n "$AI_FOUNDRY_RESOURCE_ID" ]; then
    echo "Checking Azure AI User role assignment..."
    aiUserRoleExists=$(az role assignment list \
        --assignee "$signed_user_id" \
        --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" \
        --scope "$AI_FOUNDRY_RESOURCE_ID" \
        --query "[0].id" -o tsv 2>/dev/null)
    if [ -n "$aiUserRoleExists" ]; then
        echo "User already has the Azure AI User role."
    else
        echo "Assigning Azure AI User role to AI Foundry account..."
        az role assignment create \
            --assignee "$signed_user_id" \
            --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" \
            --scope "$AI_FOUNDRY_RESOURCE_ID" \
            --output none
        echo "Azure AI User role assigned successfully."
    fi
else
    echo "[INFO] No AI Foundry resource configured, skipping AI User role assignment."
fi

# ============================================================
#  Restore and start backend
# ============================================================
if [ "$BACKEND_RUNTIME_STACK" = "dotnet" ]; then
    echo ""
    echo "Restoring dotnet backend packages..."
    cd "$ROOT_DIR/src/api/dotnet"
    dotnet restore --verbosity quiet || { echo "Failed to restore dotnet backend packages"; exit 1; }
    cd "$ROOT_DIR"
else
    echo ""
    # Create virtual environment if it doesn't exist
    cd "$ROOT_DIR"
    if [ ! -d ".venv" ]; then
        echo "Creating Python virtual environment..."
        python3 -m venv .venv || { echo "Failed to create virtual environment"; exit 1; }
        echo "Virtual environment created successfully."
    else
        echo "Virtual environment already exists."
    fi

    # Activate virtual environment and install packages
    echo "Activating virtual environment and installing backend packages..."
    source .venv/bin/activate
    python -m pip install --upgrade pip --quiet
    python -m pip install uv --quiet
    cd "$ROOT_DIR/src/api/python"
    python -m uv pip install -r requirements.txt || { echo "Failed to restore backend Python packages"; deactivate; exit 1; }
    echo "Backend Python packages installed successfully."
    deactivate
    cd "$ROOT_DIR"
fi

# Restore frontend packages
echo "Restoring frontend npm packages..."
cd "$ROOT_DIR/src/App"
npm install --force --silent || { echo "Failed to restore frontend npm packages"; exit 1; }
cd "$ROOT_DIR"

# Kill any existing processes on ports 8000 and 3000 before starting
for port in 8000 3000; do
    pid=$(lsof -ti :"$port" 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "Port $port is already in use by PID $pid. Stopping it..."
        kill -9 $pid 2>/dev/null || true
    fi
done

# Start backend and frontend; trap cleans up both on exit/interrupt
cleanup() {
    echo ""
    echo "Shutting down servers..."
    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        kill "$FRONTEND_PID" 2>/dev/null || true
        wait "$FRONTEND_PID" 2>/dev/null || true
    fi
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi
    echo "Servers stopped."
}

trap cleanup EXIT INT TERM

echo ""
if [ "$BACKEND_RUNTIME_STACK" = "dotnet" ]; then
    echo "Starting dotnet backend..."
    cd "$ROOT_DIR/src/api/dotnet"
    dotnet run --urls=http://127.0.0.1:8000 &
    BACKEND_PID=$!
else
    echo "Starting Python backend..."
    cd "$ROOT_DIR"
    source .venv/bin/activate
    cd src/api/python
    python app.py --port=8000 &
    BACKEND_PID=$!
fi
echo "Backend started at http://127.0.0.1:8000"

echo "Waiting for backend to initialize..."
sleep 10

echo ""
echo "Both servers have been started."
echo "Backend running at http://127.0.0.1:8000"
echo "Frontend running at http://localhost:3000"

echo "Starting frontend server..."
cd "$ROOT_DIR/src/App"
npm start &
FRONTEND_PID=$!

wait $FRONTEND_PID