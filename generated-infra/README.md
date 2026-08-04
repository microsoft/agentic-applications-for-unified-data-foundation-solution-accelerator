# Generated infrastructure composition

Composed automatically by `infra_composer_agent` from the request:

> 2 app services, 1 container app, 1 storage account, 1 cosmos db, application insights, log analytics, managed identity, and key vault

## Modules included

- `compute/app-service-plan.bicep`  _(auto-included dependency)_
- `compute/app-service.bicep`
- `compute/container-app-environment.bicep`  _(auto-included dependency)_
- `compute/container-app.bicep`
- `data/storage-account.bicep`
- `data/cosmos-db-nosql.bicep`
- `monitoring/log-analytics.bicep`
- `monitoring/app-insights.bicep`
- `identity/managed-identity.bicep`
- `security/key-vault.bicep`

Deploy with:

```
az deployment group create --resource-group <rg> --template-file main.bicep
```
