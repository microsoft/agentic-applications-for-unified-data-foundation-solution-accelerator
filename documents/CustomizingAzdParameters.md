## [Optional]: Customizing resource names 

By default this template will use the environment name as the prefix to prevent naming collisions within Azure. The parameters below show the default values. You only need to run the statements below if you need to change the values. 


> To override any of the parameters, run `azd env set <PARAMETER_NAME> <VALUE>` before running `azd up`. On the first azd command, it will prompt you for the environment name. Be sure to choose 3-20 charaters alphanumeric unique name. 

## Parameters

| Name                                      | Type    | Default Value            | Purpose                                                                    |
| ----------------------------------------- | ------- | ------------------------ | -------------------------------------------------------------------------- |
| `AZURE_LOCATION`                          | string  | ` `                      | Sets the Azure region for resource deployment.                             |
| `AZURE_ENV_NAME`                          | string  | `env_name`               | Sets the environment name prefix for all Azure resources (3-20 chars).     |
| `AZURE_SECONDARY_LOCATION`                | string  | `eastus2`                | Specifies a secondary Azure region for databases.                          |
| `AZURE_OPENAI_MODEL_DEPLOYMENT_TYPE`      | string  | `GlobalStandard`         | Defines the model deployment type (allowed: `Standard`, `GlobalStandard`). |
| `AZURE_OPENAI_DEPLOYMENT_MODEL`           | string  | `gpt-4.1-mini`           | Specifies the GPT model name (e.g., `gpt-4.1-mini`).                      |
| `AZURE_ENV_MODEL_VERSION`                 | string  | `2025-04-14`             | Sets the GPT model version.                                                |
| `AZURE_OPENAI_API_VERSION`                | string  | `2025-01-01-preview`     | Specifies the API version for Azure OpenAI.                                |
| `AZURE_OPENAI_DEPLOYMENT_MODEL_CAPACITY`  | integer | `150`                    | Sets the GPT model capacity (minimum: 10).                                 |
| `AZURE_ENV_IMAGETAG`                      | string  | `latest_workshop`        | Sets the container image tag.                                              |
| `AZURE_ENV_USE_CASE`                      | string  | `Retail-sales-analysis`  | Specifies the use case (allowed: `Retail-sales-analysis`, `Insurance-improve-customer-meetings`). |
| `AZURE_ENV_LOG_ANALYTICS_WORKSPACE_ID`    | string  | ` `                      | Reuses an existing Log Analytics Workspace. Guide: [Existing Workspace ID](/documents/re-use-log-analytics.md). |
| `AZURE_EXISTING_AI_PROJECT_RESOURCE_ID`   | string  | ` `                      | Reuses an existing AI Foundry project instead of creating a new one.       |
| `BACKEND_RUNTIME_STACK`                   | string  | `python`                 | Backend language (allowed: `python`, `dotnet`).                            |
| `AZURE_ENV_AI_DEPLOYMENTS_LOCATION`       | string  |                          | Location for AI Foundry deployment (e.g., `eastus`, `swedencentral`).      |
| `AZURE_ENV_ACR_NAME`                      | string  | `dataagentscontainerregworkshop` | Name of the Azure Container Registry to pull images from.           |
| `AZURE_ENV_SEARCH_SERVICE_LOCATION`       | string  | *(resource group location)* | Location for Azure AI Search service deployment.                        |
| `AZURE_ENV_DEPLOY_APP`                    | bool    | `true`                   | Deploy application components (API, Frontend, Cosmos DB).                  |
| `IS_WORKSHOP`                             | bool    | `true`                   | Enable workshop mode with sample data and simplified configuration.        |
| `AZURE_ENV_ONLY`                          | bool    | `false`                  | Deploy Azure SQL Server instead of Fabric SQL.                             |
| `DEPLOYING_USER_PRINCIPAL_TYPE`           | string  | `User`                   | Principal type of deployer (allowed: `User`, `ServicePrincipal`).          |



## How to Set a Parameter

To customize any of the above values, run the following command **before** `azd up`:

```bash
azd env set <PARAMETER_NAME> <VALUE>
```

**Example:**

```bash
azd env set AZURE_LOCATION westus2
```
