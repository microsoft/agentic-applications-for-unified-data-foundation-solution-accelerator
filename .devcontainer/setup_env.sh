#!/bin/bash

set -euo pipefail

git fetch
git pull

# Ensure PowerShell is available for OBO authentication setup in Codespaces / VS Code Web
if ! command -v pwsh >/dev/null 2>&1; then
	echo "Installing PowerShell..."
	sudo apt-get update
	sudo apt-get install -y --no-install-recommends wget gpg apt-transport-https software-properties-common
	wget -q https://packages.microsoft.com/config/debian/11/packages-microsoft-prod.deb -O /tmp/packages-microsoft-prod.deb
	sudo dpkg -i /tmp/packages-microsoft-prod.deb
	sudo apt-get update
	sudo apt-get install -y --no-install-recommends powershell
	rm -f /tmp/packages-microsoft-prod.deb
	sudo apt-get clean
	sudo rm -rf /var/lib/apt/lists/*
fi

# provide execute permission to quotacheck script
sudo chmod +x ./infra/scripts/pre-provision/checkquota_agentic_application.sh
sudo chmod +x ./infra/scripts/pre-provision/quota_check_params.sh
sudo chmod +x ./infra/scripts/build/build-and-push-acr.sh