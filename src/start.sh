#!/bin/bash

echo Starting the application setup...

# Set root and config paths
ROOT_DIR=$(cd .. && pwd)
AZURE_FOLDER="$ROOT_DIR/.azure"
CONFIG_FILE="$AZURE_FOLDER/config.json"

# Validate config.json
if [ ! -f "$CONFIG_FILE" ]; then
    echo "config.json not found at $CONFIG_FILE"
    exit 1
fi

# Debug: Print the content of config.json
echo "Content of config.json:"
cat "$CONFIG_FILE"

# Extract default environment name
DEFAULT_ENV=$(grep -o '"defaultEnvironment"\s*:\s*"[^\"]*"' "$CONFIG_FILE" | sed -E 's/.*"defaultEnvironment"\s*:\s*"([^"]*)".*/\1/')

# Check if DEFAULT_ENV is empty
if [ -z "$DEFAULT_ENV" ]; then
  echo "Failed to extract defaultEnvironment from config.json"
  exit 1
fi

echo "Default environment: $DEFAULT_ENV"

# Set path to source .env file
ENV_FILE="$AZURE_FOLDER/$DEFAULT_ENV/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo ".env file not found at $ENV_FILE"
    exit 1
fi

# 1. Copy full .env to src/api
API_ENV_FILE="$ROOT_DIR/src/api/.env"
cp "$ENV_FILE" "$API_ENV_FILE"
if [ $? -ne 0 ]; then
    echo "Failed to copy .env to src/api"
    exit 1
fi
echo "Copied .env to src/api"

# Directly set APP_API_BASE_URL in src/App/.env
APP_ENV_FILE="$ROOT_DIR/src/App/.env"
echo "REACT_APP_API_BASE_URL=http://127.0.0.1:8000" > "$APP_ENV_FILE"

if [ -f "$APP_ENV_FILE" ]; then
    echo "Updated src/App/.env with APP_API_BASE_URL"
else
    echo "Failed to update src/App/.env"
    exit 1
fi

echo "Successfully updated REACT_APP_API_BASE_URL in $ENV_FILE"

# Restoring backend Python packages
echo "Restoring backend Python packages..."
cd api
python -m pip install -r requirements.txt || { echo "Failed to restore backend Python packages"; exit 1; }
cd ..

# Restoring frontend npm packages
echo "Restoring frontend npm packages..."
cd App
npm install --force || { echo "Failed to restore frontend npm packages"; exit 1; }
cd ..

# Starting backend in the background
echo "Starting backend..."
(cd api && python app.py --port=8000 &) || { echo "Failed to start backend"; exit 1; }

# Wait for 10 seconds to ensure the backend starts properly
sleep 10

# Starting frontend in the background
echo "Starting frontend..."
(cd App && npm start &) || { echo "Failed to start frontend"; exit 1; }

# Display running services
echo "Backend running at http://127.0.0.1:8000"
echo "Frontend running at http://localhost:3000"