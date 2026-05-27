// ========== main_custom.bicep ========== //
// WAF-aligned variant of main.bicep.
// Key differences from main.bicep:
//   - Deploys App Services via Oryx source-code build (azd deploy) instead of pre-built Docker images.
//   - Adds azd-service-name tags so `azd deploy` can target the api and webapp services.
//   - Adds Log Analytics diagnostic settings for App Service instances.
//   - Frontend App Service has no managed identity.
//   - Backend app settings omit agent-name / API-app-name fields; adds PYTHONUNBUFFERED.
//   - Frontend app settings include REACT_APP_API_BASE_URL and WEBSITE_NODE_DEFAULT_VERSION.
//   - Adds USER_MID and AZURE_EXISTING_AIPROJECT_RESOURCE_ID outputs.

targetScope = 'resourceGroup'
var abbrs = loadJsonContent('./abbreviations.json')

@minLength(3)
@maxLength(20)
@description('A unique application/solution name for all resources in this deployment. This should be 3-20 characters long:')
param solutionName string = 'agenticappudf'

@maxLength(5)
@description('Optional. A unique text value for the solution.')
param solutionUniqueText string = substring(uniqueString(subscription().id, resourceGroup().name, solutionName), 0, 5)

@description('Optional: Existing Log Analytics Workspace Resource ID')
param existingLogAnalyticsWorkspaceId string = ''

@description('Use this parameter to use an existing AI project resource ID')
param existingFoundryProjectResourceId string = ''

@description('Optional. created by user name')
param createdBy string = contains(deployer(), 'userPrincipalName') ? split(deployer().userPrincipalName, '@')[0] : deployer().objectId

@description('Choose the programming language:')
@allowed([
  'python'
  'dotnet'
])
param backendRuntimeStack string = 'python'

@minLength(1)
@description('Secondary location for databases creation (example: eastus2):')
param secondaryLocation string = 'eastus2'

@description('Location for AI services deployment. This is the location where the Search service resource will be deployed.')
param searchServiceLocation string = resourceGroup().location

@minLength(1)
@description('GPT model deployment type:')
@allowed([
  'Standard'
  'GlobalStandard'
])
param deploymentType string = 'GlobalStandard'

@description('Name of the GPT model to deploy:')
param gptModelName string = 'gpt-4.1-mini'

@description('Version of the GPT model to deploy:')
param gptModelVersion string = '2025-04-14'

param azureOpenaiAPIVersion string = '2025-01-01-preview'

param azureAiAgentApiVersion string = '2025-05-01'

@minValue(10)
@description('Capacity of the GPT deployment:')
param gptDeploymentCapacity int = 150

@minLength(1)
@description('Name of the Text Embedding model to deploy:')
@allowed([
  'text-embedding-3-small'
])
param embeddingModel string = 'text-embedding-3-small'

@minValue(10)
@description('Capacity of the Embedding Model deployment')
param embeddingDeploymentCapacity int = 80

@description('Deploy the application components (Cosmos DB, API, Frontend). Set to true to deploy the app.')
param deployApp bool = true

@description('Set to true to deploy Azure SQL Server, otherwise Fabric SQL is used.')
param azureEnvOnly bool = false

var shouldDeployApp = deployApp

param location string = ''
var solutionLocation = empty(location) ? resourceGroup().location : location

var solutionSuffix = toLower(trim(replace(
  replace(
    replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''),
    ' ',
    ''
  ),
  '*',
  ''
)))

@allowed([
  'australiaeast'
  'eastus'
  'eastus2'
  'francecentral'
  'japaneast'
  'swedencentral'
  'uksouth'
  'westus'
  'westus3'
])
@metadata({
  azd: {
    type: 'location'
    usageName: [
      'OpenAI.GlobalStandard.gpt4.1-mini,100'
      'OpenAI.GlobalStandard.text-embedding-3-small,80'
    ]
  }
})
@description('Location for AI Foundry deployment. This is the location where the AI Foundry resources will be deployed.')
param azureAiServiceLocation string

@description('The principal type of the deploying user. Use ServicePrincipal for CI/CD pipelines with OIDC.')
@allowed(['User', 'ServicePrincipal'])
param deployingUserPrincipalType string = 'User'

//Get the current deployer's information
var deployerInfo = deployer()
var deployingUserPrincipalId = deployerInfo.objectId
var existingTags = resourceGroup().tags ?? {}

// ========== Resource Group Tag ========== //

// ========== Managed Identity ========== //
module managedIdentityModule 'deploy_managed_identity.bicep' = {
  name: 'deploy_managed_identity'
  params: {
    miName: '${abbrs.security.managedIdentity}${solutionSuffix}'
    solutionName: solutionSuffix
    solutionLocation: solutionLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== AI Foundry and related resources ========== //
module aifoundry 'deploy_ai_foundry.bicep' = {
  name: 'deploy_ai_foundry'
  params: {
    solutionName: solutionSuffix
    solutionLocation: azureAiServiceLocation
    deploymentType: deploymentType
    gptModelName: gptModelName
    gptModelVersion: gptModelVersion
    gptDeploymentCapacity: gptDeploymentCapacity
    embeddingModel: embeddingModel
    embeddingDeploymentCapacity: embeddingDeploymentCapacity
    managedIdentityObjectId: managedIdentityModule.outputs.managedIdentityOutput.objectId
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    deployingUserPrincipalId: deployingUserPrincipalId
    deployingUserPrincipalType: deployingUserPrincipalType
    searchServiceLocation: searchServiceLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Cosmos DB module ========== //
module cosmosDBModule 'deploy_cosmos_db.bicep' = if (deployApp) {
  name: 'deploy_cosmos_db'
  params: {
    accountName: '${abbrs.databases.cosmosDBDatabase}${solutionSuffix}'
    solutionLocation: secondaryLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== SQL DB module ========== //
module sqlDBModule 'deploy_sql_db.bicep' = if (azureEnvOnly) {
  name: 'deploy_sql_db'
  params: {
    serverName: '${abbrs.databases.sqlDatabaseServer}${solutionSuffix}'
    sqlDBName: '${abbrs.databases.sqlDatabase}${solutionSuffix}'
    solutionLocation: secondaryLocation
    managedIdentityName: managedIdentityModule.outputs.managedIdentityOutput.name
    deployerPrincipalId: deployingUserPrincipalId
  }
  scope: resourceGroup(resourceGroup().name)
}

module hostingplan 'deploy_app_service_plan.bicep' = if (shouldDeployApp) {
  name: 'deploy_app_service_plan'
  params: {
    solutionLocation: solutionLocation
    HostingPlanName: '${abbrs.compute.appServicePlan}${solutionSuffix}'
  }
}

// Resolve the Log Analytics workspace resource ID for diagnostic settings.
// Uses the existing workspace ID when provided; otherwise constructs the ID from AI Foundry outputs.
var resolvedLogAnalyticsWorkspaceId = !empty(existingLogAnalyticsWorkspaceId)
  ? existingLogAnalyticsWorkspaceId
  : '/subscriptions/${aifoundry.outputs.logAnalyticsWorkspaceSubscription}/resourceGroups/${aifoundry.outputs.logAnalyticsWorkspaceResourceGroup}/providers/Microsoft.OperationalInsights/workspaces/${aifoundry.outputs.logAnalyticsWorkspaceResourceName}'

// ========== Backend Deployment (Python) ========== //
module backend_custom 'deploy_backend_custom.bicep' = if (shouldDeployApp && backendRuntimeStack == 'python') {
  name: 'deploy_backend_custom'
  params: {
    name: 'api-${solutionSuffix}'
    solutionLocation: solutionLocation
    appServicePlanId: hostingplan!.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    userassignedIdentityId: managedIdentityModule.outputs.managedIdentityBackendAppOutput.id
    aiServicesName: aifoundry.outputs.aiServicesName
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    enableCosmosDb: shouldDeployApp
    logAnalyticsWorkspaceId: resolvedLogAnalyticsWorkspaceId
    appSettings: {
      AZURE_ENV_GPT_MODEL_NAME: gptModelName
      AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME: embeddingModel
      AZURE_OPENAI_ENDPOINT: aifoundry.outputs.aiServicesTarget
      AZURE_ENV_OPENAI_API_VERSION: azureOpenaiAPIVersion
      AZURE_OPENAI_RESOURCE: aifoundry.outputs.aiServicesName
      AZURE_AI_AGENT_ENDPOINT: aifoundry.outputs.projectEndpoint
      AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
      AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
      USE_CHAT_HISTORY_ENABLED: 'True'
      AZURE_COSMOSDB_ACCOUNT: cosmosDBModule!.outputs.cosmosAccountName
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: cosmosDBModule!.outputs.cosmosContainerName
      AZURE_COSMOSDB_DATABASE: cosmosDBModule!.outputs.cosmosDatabaseName
      AZURE_COSMOSDB_ENABLE_FEEDBACK: 'True'
      AZURE_SQLDB_DATABASE: azureEnvOnly ? sqlDBModule!.outputs.sqlDbName : ''
      AZURE_SQLDB_SERVER: azureEnvOnly ? sqlDBModule!.outputs.sqlServerName : ''
      AZURE_SQLDB_USER_MID: azureEnvOnly ? managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId : ''
      API_UID: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
      AZURE_AI_SEARCH_ENDPOINT: aifoundry.outputs.aiSearchTarget
      AZURE_AI_SEARCH_INDEX: 'knowledge_index'
      AZURE_AI_SEARCH_CONNECTION_NAME: aifoundry.outputs.aiSearchConnectionName

      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: aifoundry.outputs.applicationInsightsConnectionString
      DUMMY_TEST: 'True'
      SOLUTION_NAME: solutionSuffix
      AZURE_ENV_ONLY: azureEnvOnly ? 'True' : 'False'
      APP_ENV: 'Prod'
      AZURE_BASIC_LOGGING_LEVEL: 'INFO'
      AZURE_PACKAGE_LOGGING_LEVEL: 'WARNING'
      AZURE_LOGGING_PACKAGES: ''

      FABRIC_SQL_DATABASE: ''
      FABRIC_SQL_SERVER: ''
      FABRIC_SQL_CONNECTION_STRING: ''
    }
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Backend Deployment (C#) ========== //
// C# backend continues to use the Docker-based deployment module.
module backend_csapi_docker 'deploy_backend_csapi_docker.bicep' = if (shouldDeployApp && backendRuntimeStack == 'dotnet') {
  name: 'deploy_backend_csapi_docker'
  params: {
    name: 'api-cs-${solutionSuffix}'
    solutionLocation: solutionLocation
    imageTag: 'latest_v2'
    containerRegistryName: 'dataagentscontainerreg'
    appServicePlanId: hostingplan!.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    userassignedIdentityId: managedIdentityModule.outputs.managedIdentityBackendAppOutput.id
    aiServicesName: aifoundry.outputs.aiServicesName
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    appSettings: {
      AZURE_ENV_GPT_MODEL_NAME: gptModelName
      AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME: embeddingModel
      AZURE_OPENAI_ENDPOINT: aifoundry.outputs.aiServicesTarget
      AZURE_ENV_OPENAI_API_VERSION: azureOpenaiAPIVersion
      AZURE_OPENAI_RESOURCE: aifoundry.outputs.aiServicesName
      AZURE_AI_AGENT_ENDPOINT: aifoundry.outputs.projectEndpoint
      AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
      AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
      USE_CHAT_HISTORY_ENABLED: 'True'
      AZURE_COSMOSDB_ACCOUNT: cosmosDBModule!.outputs.cosmosAccountName
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: cosmosDBModule!.outputs.cosmosContainerName
      AZURE_COSMOSDB_DATABASE: cosmosDBModule!.outputs.cosmosDatabaseName
      AZURE_COSMOSDB_ENABLE_FEEDBACK: 'True'
      API_UID: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
      AZURE_AI_SEARCH_ENDPOINT: aifoundry.outputs.aiSearchTarget
      AZURE_AI_SEARCH_INDEX: 'knowledge_index'
      AZURE_AI_SEARCH_CONNECTION_NAME: aifoundry.outputs.aiSearchConnectionName

      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: aifoundry.outputs.applicationInsightsConnectionString
      DUMMY_TEST: 'True'
      SOLUTION_NAME: solutionSuffix
      APP_ENV: 'Prod'
      AZURE_ENV_ONLY: azureEnvOnly ? 'True' : 'False'
      USE_DATA_AGENT: 'False'
      AZURE_SQLDB_DATABASE: azureEnvOnly ? sqlDBModule!.outputs.sqlDbName : ''
      AZURE_SQLDB_SERVER: azureEnvOnly ? sqlDBModule!.outputs.sqlServerName : ''

      FABRIC_SQL_DATABASE: ''
      FABRIC_SQL_SERVER: ''
      FABRIC_SQL_CONNECTION_STRING: ''
    }
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Frontend Deployment ========== //
module frontend_custom 'deploy_frontend_custom.bicep' = if (shouldDeployApp) {
  name: 'deploy_frontend_custom'
  params: {
    name: '${abbrs.compute.webApp}${solutionSuffix}'
    solutionLocation: solutionLocation
    appServicePlanId: hostingplan!.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    logAnalyticsWorkspaceId: resolvedLogAnalyticsWorkspaceId
    appSettings: {
      APP_API_BASE_URL: backendRuntimeStack == 'python' ? backend_custom!.outputs.appUrl : backend_csapi_docker!.outputs.appUrl
      CHAT_LANDING_TEXT: ''
    }
  }
  scope: resourceGroup(resourceGroup().name)
}

// ============================================================================
// Outputs
// ============================================================================

@description('Solution suffix used for naming resources')
output SOLUTION_NAME string = solutionSuffix

@description('Name of the deployed resource group')
output RESOURCE_GROUP_NAME string = resourceGroup().name

@description('Cosmos DB account name for conversation history storage')
output AZURE_COSMOSDB_ACCOUNT string = shouldDeployApp ? cosmosDBModule!.outputs.cosmosAccountName : ''

@description('Cosmos DB container name for storing conversations')
output AZURE_COSMOSDB_CONVERSATIONS_CONTAINER string = 'conversations'

@description('Cosmos DB database name for conversation history')
output AZURE_COSMOSDB_DATABASE string = 'db_conversation_history'

@description('GPT model deployment name (e.g., gpt-4o-mini)')
output AZURE_ENV_GPT_MODEL_NAME string = gptModelName

@description('Azure OpenAI service endpoint URL')
output AZURE_OPENAI_ENDPOINT string = aifoundry.outputs.aiServicesTarget

@description('Embedding model deployment name for vector search')
output AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME string = embeddingModel

@description('Azure SQL database name (Azure-only mode)')
output AZURE_SQLDB_DATABASE string = azureEnvOnly ? sqlDBModule!.outputs.sqlDbName : ''

@description('Azure SQL server fully qualified domain name (Azure-only mode)')
output AZURE_SQLDB_SERVER string = azureEnvOnly ? sqlDBModule!.outputs.sqlServerName : ''

@description('Managed identity client ID for SQL authentication (Azure-only mode)')
output AZURE_SQLDB_USER_MID string = azureEnvOnly ? managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId : ''

@description('Backend API managed identity client ID')
output API_UID string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId

@description('Azure AI Agent service endpoint URL')
output AZURE_AI_AGENT_ENDPOINT string = aifoundry.outputs.projectEndpoint

@description('Model deployment name used by Azure AI Agent')
output AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME string = gptModelName

@description('Backend API App Service name')
output API_APP_NAME string = shouldDeployApp ? (backendRuntimeStack == 'python' ? backend_custom!.outputs.appName : backend_csapi_docker!.outputs.appName) : ''

@description('Backend API managed identity object/principal ID')
output API_PID string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.objectId

@description('Backend API managed identity display name')
output MID_DISPLAY_NAME string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.name

@description('Frontend web app resource name')
output WEB_APP_NAME string = shouldDeployApp ? '${abbrs.compute.webApp}${solutionSuffix}' : ''

@description('Frontend web application URL')
output WEB_APP_URL string = shouldDeployApp ? frontend_custom!.outputs.appUrl : ''

@description('Azure AI Search service endpoint URL')
output AZURE_AI_SEARCH_ENDPOINT string = aifoundry.outputs.aiSearchTarget

@description('Azure AI Search index name for document search')
output AZURE_AI_SEARCH_INDEX string = 'knowledge_index'

@description('Azure AI Search service resource name')
output AZURE_AI_SEARCH_NAME string = aifoundry.outputs.aiSearchName

@description('Local path to documents folder for search indexing')
output SEARCH_DATA_FOLDER string = 'data/default/documents'

@description('AI Foundry connection name for Azure AI Search')
output AZURE_AI_SEARCH_CONNECTION_NAME string = aifoundry.outputs.aiSearchConnectionName

@description('AI Foundry connection ID for Azure AI Search')
output AZURE_AI_SEARCH_CONNECTION_ID string = aifoundry.outputs.aiSearchConnectionId

@description('Azure AI Foundry project endpoint URL')
output AZURE_AI_PROJECT_ENDPOINT string = aifoundry.outputs.projectEndpoint

@description('Azure AI Foundry resource ID for role assignments')
output AI_FOUNDRY_RESOURCE_ID string = aifoundry.outputs.aiFoundryResourceId

@description('Azure AI Foundry project name')
output AZURE_AI_PROJECT_NAME string = aifoundry.outputs.aiProjectName

@description('Azure AI Services resource name')
output AI_SERVICE_NAME string = aifoundry.outputs.aiServicesName

@description('Azure AI Foundry project managed identity principal ID')
output FOUNDRY_PROJECT_PID string = aifoundry.outputs.aiProjectPrincipalId

@description('Backend runtime stack (python or dotnet)')
output BACKEND_RUNTIME_STACK string = backendRuntimeStack

@description('Flag indicating whether to deploy App Service')
output AZURE_ENV_DEPLOY_APP bool = deployApp

@description('Flag indicating Azure-only mode (no Fabric)')
output AZURE_ENV_ONLY bool = azureEnvOnly

@description('Backend API managed identity client ID (alias for USER_MID use)')
output USER_MID string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId

@description('Existing or newly created AI project resource ID')
output AZURE_EXISTING_AIPROJECT_RESOURCE_ID string = !empty(existingFoundryProjectResourceId)
  ? existingFoundryProjectResourceId
  : aifoundry.outputs.aiFoundryResourceId
