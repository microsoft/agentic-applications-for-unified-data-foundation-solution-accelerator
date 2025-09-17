#!/bin/bash

set -euo pipefail

echo ">>> Running setup_env.sh ..."

# Ensure we are root for package installs
if [ "$(id -u)" -ne 0 ]; then
    echo "Re-running as root..."
    exec sudo bash "$0" "$@"
fi

# Install Microsoft ODBC driver repo + msodbcsql17 if not already present
if ! dpkg -s msodbcsql17 >/dev/null 2>&1; then
    echo ">>> Adding Microsoft SQL Server ODBC repository..."
    curl -sSL https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
    curl -sSL https://packages.microsoft.com/config/debian/11/prod.list \
        > /etc/apt/sources.list.d/mssql-release.list

    echo ">>> Installing ODBC dependencies..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    ACCEPT_EULA=Y apt-get install -y \
        msodbcsql17 \
        unixodbc \
        unixodbc-dev

    apt-get clean
    rm -rf /var/lib/apt/lists/*
else
    echo ">>> msodbcsql17 already installed, skipping."
fi

# Switch back to non-root user (vscode) if needed
if [ "$SUDO_USER" != "" ] && [ "$SUDO_USER" != "root" ]; then
    exec sudo -u "$SUDO_USER" bash -c "$0 remainder"
fi

git fetch
git pull

# provide execute permission to quotacheck script
sudo chmod +x ./infra/scripts/checkquota_km.sh
sudo chmod +x ./infra/scripts/quota_check_params.sh
sudo chmod +x ./infra/scripts/docker-build.sh
sudo chmod +x ./infra/scripts/docker-build.ps1