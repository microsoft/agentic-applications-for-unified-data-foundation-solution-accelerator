#!/bin/bash

set -euo pipefail

git fetch
git pull

# provide execute permission to quotacheck script
sudo chmod +x ./infra/scripts/checkquota_agentic_application.sh
sudo chmod +x ./infra/scripts/quota_check_params.sh
sudo chmod +x ./infra/scripts/acr_build_and_deploy.sh