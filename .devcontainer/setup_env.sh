#!/bin/bash

set -euo pipefail

git fetch
git pull

# provide execute permission to quotacheck script
sudo chmod +x ./infra/scripts/pre-provision/checkquota_agentic_application.sh
sudo chmod +x ./infra/scripts/pre-provision/quota_check_params.sh
sudo chmod +x ./infra/scripts/build/docker-build.sh
sudo chmod +x ./infra/scripts/build/docker-build.ps1