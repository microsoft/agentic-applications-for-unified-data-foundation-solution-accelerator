# Container Registry Change Summary — Dedicated ACR + Identity-Based Pull + Remote Build

## Before (previous approach)

- **One shared registry for everyone**: `infra/main.bicep` hard-coded
  `acrName = 'dataagentscontainerreg'` — a single shared/public Azure Container Registry.
- **Anonymous pull**: App Services were created with
  `linuxFxVersion: DOCKER|dataagentscontainerreg.azurecr.io/da-api:<tag>` and pulled images
  **anonymously**. `infra/deploy_app_service.bicep` configured **no** ACR credentials or identity.
- **Image already existed** in the shared registry; nothing was built at deploy time.
  The optional `docker-build.ps1/.sh` path did a **local Docker** build + push to a separate
  registry, which required Docker to be installed locally.
- **Net effect**: anyone deploying pulled from the same registry with no identity check.

## Now (new approach)

| Aspect             | Before                     | Now                                                                 |
| ------------------ | -------------------------- | ------------------------------------------------------------------- |
| Registry           | 1 shared / public ACR      | **Dedicated ACR per deployment** (`deploy_acr.bicep`, name `cr<suffix>`) |
| Authentication     | Anonymous pull             | **Identity-based** — AcrPull role on App Service managed identities; `acrUseManagedIdentityCreds=true` |
| Anonymous access   | Enabled (shared)           | **Disabled** (`anonymousPullEnabled: false`, `adminUserEnabled: false`) |
| Image at provision | Real shared image          | **Public placeholder** (`aci-helloworld`) so provisioning succeeds before images exist |
| Image build        | Prebuilt / local Docker    | **Remote build** via `az acr build` (no local Docker needed)        |
| Update flow        | N/A                        | Separate **manual** post-deploy script builds → pushes → repoints App Services → restarts |

## New end-to-end flow

1. `azd provision` → creates the **dedicated ACR** + AcrPull role assignments; App Services
   come up on the **placeholder** image with managed-identity pull configured.
2. Run the new **separate** script `infra/scripts/acr_build_and_deploy.(ps1|sh)`:
   - `az acr build` each image into that ACR (remote build)
   - `az webapp config container set` points each App Service at the real ACR image
   - restart the App Services
3. Run the existing post-deploy scripts (agents / Fabric).

## Why each change

- **Dedicated ACR** → isolation; stops depending on the shared/public registry.
- **Managed identity + AcrPull** → removes anonymous access; only authorized identities pull.
- **`az acr build`** → users without Docker can still build. Also fixed `.dockerignore` files
  (`src/App`, `src/api/python`) that excluded the Dockerfile, which breaks remote builds.
- **Placeholder image** → lets infrastructure provision cleanly before the real images exist.

## Files changed

**New**
- `infra/deploy_acr.bicep` — dedicated ACR + AcrPull role assignments.
- `infra/scripts/acr_build_and_deploy.ps1` / `.sh` — separate remote-build post-deploy script.

**Modified**
- `infra/main.bicep` — provision ACR, placeholder image, grant AcrPull, new outputs
  (`AZURE_ENV_CONTAINER_REGISTRY_NAME`, `ACR_LOGIN_SERVER`, `WEB_APP_NAME`, `AZURE_ENV_IMAGE_TAG`).
- `infra/main_custom.bicep` — same wiring for the C# (dotnet) container path.
- `infra/deploy_app_service.bicep` — `acrUseManagedIdentityCreds` + `acrUserManagedIdentityID`.
- `infra/deploy_backend_docker.bicep`, `deploy_frontend_docker.bicep`,
  `deploy_backend_csapi_docker.bicep` — placeholder image + identity pull params.
- `infra/main.parameters.json` — `acrName` override now optional (empty default → derived name).
- `azure.yaml` — post-provision instructions now include the build step first.
- `documents/CustomizingAzdParameters.md` — updated `AZURE_ENV_CONTAINER_REGISTRY_NAME` docs.
- `src/App/.dockerignore`, `src/api/python/.dockerignore` — stop excluding the Dockerfile.

## Validation performed

- `az bicep build` passes for `main.bicep`, `main_custom.bicep`, `deploy_acr.bicep`.
- Repo's `infra/scripts/validate_bicep_params.py` → PASS.
- Both scripts syntax-checked (PowerShell parser + `bash -n`).
