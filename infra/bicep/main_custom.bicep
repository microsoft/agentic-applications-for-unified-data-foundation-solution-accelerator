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

// ============================================================================
// Parameters
// ============================================================================

// ── Core ──

@minLength(3)
@maxLength(20)
@description('Required. A unique application/solution name for all resources in this deployment.')
param solutionName string = 'agenticappudf'

@maxLength(5)
@description('Optional. A unique text suffix appended to resource names for uniqueness.')
param solutionUniqueText string = substring(uniqueString(subscription().id, resourceGroup().name, solutionName), 0, 5)

@description('Optional. Primary Azure region for resource deployment. Defaults to resource group location.')
param location string = ''

@description('Optional. Secondary location for database resources (example: eastus2).')
param secondaryLocation string = 'eastus2'

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
@description('Required. Location for AI Foundry and model deployments.')
param azureAiServiceLocation string

@description('Optional. Location for AI Search service deployment. Defaults to resource group location.')
param searchServiceLocation string = resourceGroup().location

// ── AI Configuration ──

@allowed([
  'Standard'
  'GlobalStandard'
])
@description('Optional. GPT model deployment type.')
param deploymentType string = 'GlobalStandard'

@description('Optional. Name of the GPT model to deploy.')
param gptModelName string = 'gpt-4.1-mini'

@description('Optional. Version of the GPT model to deploy.')
param gptModelVersion string = '2025-04-14'

@description('Optional. Azure OpenAI API version.')
param azureOpenaiAPIVersion string = '2025-01-01-preview'

@description('Optional. Azure AI Agent API version.')
param azureAiAgentApiVersion string = '2025-05-01'

@minValue(10)
@description('Optional. Capacity of the GPT deployment (TPM in thousands).')
param gptDeploymentCapacity int = 150

@allowed([
  'text-embedding-3-small'
])
@description('Optional. Name of the Text Embedding model to deploy.')
param embeddingModel string = 'text-embedding-3-small'

@minValue(10)
@description('Optional. Capacity of the Embedding Model deployment.')
param embeddingDeploymentCapacity int = 80

// ── Compute ──

@allowed([
  'python'
  'dotnet'
])
@description('Optional. Backend runtime stack.')
param backendRuntimeStack string = 'python'

// ── Feature Flags ──

@description('Optional. Deploy the application components (Cosmos DB, API, Frontend).')
param deployApp bool = true

@description('Optional. Deploy Azure SQL Server instead of Fabric SQL.')
param azureEnvOnly bool = false

// ── Existing Resources ──

@description('Optional. Resource ID of an existing Log Analytics workspace. Empty creates a new one.')
param existingLogAnalyticsWorkspaceId string = ''

@description('Optional. Resource ID of an existing AI Foundry project. Empty creates a new one.')
param existingFoundryProjectResourceId string = ''

// ── Identity ──

@allowed(['User', 'ServicePrincipal'])
@description('Optional. Principal type of the deploying user. Use ServicePrincipal for CI/CD pipelines with OIDC.')
param deployingUserPrincipalType string = 'User'

@description('Optional. Created by user name for resource tagging.')
param createdBy string = contains(deployer(), 'userPrincipalName') ? split(deployer().userPrincipalName, '@')[0] : deployer().objectId

// ── App Configuration ──

@allowed([
  'Retail-sales-analysis'
  'Insurance-improve-customer-meetings'
])
@description('Optional. Industry use case for deployment.')
param usecase string = 'Retail-sales-analysis'

// ============================================================================
// Variables
// ============================================================================

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

var deployerInfo = deployer()
var deployingUserPrincipalId = deployerInfo.objectId
var existingTags = resourceGroup().tags ?? {}
var shouldDeployApp = deployApp

// ========== Resource Group Tag ========== //

// ========== Monitoring (Log Analytics + Application Insights) ========== //
// ========== Log Analytics module ========== //
module log_analytics './modules/monitoring/log-analytics.bicep' = {
  name: 'deploy_log_analytics'
  params: {
    solutionName: solutionSuffix
    solutionLocation: azureAiServiceLocation
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Application Insights module ========== //
module app_insights './modules/monitoring/app-insights.bicep' = {
  name: 'deploy_app_insights'
  params: {
    solutionName: solutionSuffix
    solutionLocation: azureAiServiceLocation
    logAnalyticsWorkspaceId: log_analytics.outputs.logAnalyticsWorkspaceId
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== AI Foundry and related resources ========== //
var aiModelDeployments = concat([
  {
    name: gptModelName
    model: gptModelName
    sku: {
      name: deploymentType
      capacity: gptDeploymentCapacity
    }
    version: gptModelVersion
    raiPolicyName: 'Microsoft.Default'
  }
], [
  {
    name: embeddingModel
    model: embeddingModel
    sku: {
      name: 'GlobalStandard'
      capacity: embeddingDeploymentCapacity
    }
    version: '1'
    raiPolicyName: 'Microsoft.Default'
  }
])

module aifoundry './modules/ai/ai-foundry.bicep' = if (empty(existingFoundryProjectResourceId)) {
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
    applicationInsightsId: app_insights.outputs.applicationInsightsId
    applicationInsightsInstrumentationKey: app_insights.outputs.applicationInsightsInstrumentationKey
    aiSearchTarget: ai_search!.outputs.aiSearchTarget
    aiSearchId: ai_search!.outputs.aiSearchId
    aiSearchConnectionName: ai_search!.outputs.aiSearchConnectionName
    storageBlobEndpoint: storage_account!.outputs.storageBlobEndpoint
    storageAccountId: storage_account!.outputs.storageAccountId
    storageAccountName: storage_account!.outputs.storageAccountName
  }
  scope: resourceGroup(resourceGroup().name)
}

module ai_search './modules/ai/ai-search.bicep' = {
  name: 'deploy_ai_search'
  params: {
    solutionName: solutionSuffix
    searchServiceLocation: searchServiceLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Existing Project Setup (models + connections) ========== //
var existingAIServicesName = !empty(existingFoundryProjectResourceId) ? split(existingFoundryProjectResourceId, '/')[8] : ''
var existingAIProjectName = !empty(existingFoundryProjectResourceId) ? split(existingFoundryProjectResourceId, '/')[10] : ''
var existingAIServiceSubscription = !empty(existingFoundryProjectResourceId) ? split(existingFoundryProjectResourceId, '/')[2] : subscription().subscriptionId
var existingAIServiceResourceGroup = !empty(existingFoundryProjectResourceId) ? split(existingFoundryProjectResourceId, '/')[4] : resourceGroup().name

module existing_project_setup './modules/ai/existing-project-setup.bicep' = if (!empty(existingFoundryProjectResourceId)) {
  name: 'setup_existing_project'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    aiFoundryName: existingAIServicesName
    aiProjectName: existingAIProjectName
    aiModelDeployments: aiModelDeployments
    applicationInsightsId: app_insights.outputs.applicationInsightsId
    applicationInsightsInstrumentationKey: app_insights.outputs.applicationInsightsInstrumentationKey
    aiSearchTarget: ai_search!.outputs.aiSearchTarget
    aiSearchId: ai_search!.outputs.aiSearchId
    aiSearchConnectionName: ai_search!.outputs.aiSearchConnectionName
    storageBlobEndpoint: storage_account!.outputs.storageBlobEndpoint
    storageAccountId: storage_account!.outputs.storageAccountId
    storageAccountName: storage_account!.outputs.storageAccountName
  }
}

// ========== AI outputs (ternary: existing vs new) ========== //
var useExisting = !empty(existingFoundryProjectResourceId)
var aiFoundryEndpoint = useExisting ? existing_project_setup!.outputs.aiFoundryEndpoint : aifoundry!.outputs.aiFoundryEndpoint
var projectEndpoint = useExisting ? existing_project_setup!.outputs.projectEndpoint : aifoundry!.outputs.projectEndpoint
var aiFoundryName = useExisting ? existing_project_setup!.outputs.aiFoundryNameOutput : aifoundry!.outputs.aiFoundryName
var aiProjectName = useExisting ? existing_project_setup!.outputs.aiProjectNameOutput : aifoundry!.outputs.aiProjectName
var aiFoundryResourceId = useExisting ? existing_project_setup!.outputs.aiFoundryResourceId : aifoundry!.outputs.aiFoundryResourceId
var aiProjectPrincipalId = useExisting ? existing_project_setup!.outputs.aiProjectPrincipalId : aifoundry!.outputs.aiProjectPrincipalId
var aiSearchConnectionId = useExisting ? existing_project_setup!.outputs.aiSearchConnectionId : aifoundry!.outputs.aiSearchConnectionId

// ========== Storage Account module ========== //
module storage_account './modules/data/storage-account.bicep' = {
  name: 'deploy_storage_account'
  params: {
    solutionName: solutionSuffix
    solutionLocation: azureAiServiceLocation
    tags: {}
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Cosmos DB module ========== //
module cosmosDBModule './modules/data/cosmos-db.bicep' = if (deployApp) {
  name: 'deploy_cosmos_db'
  params: {
    accountName: 'cosmos-${solutionSuffix}'
    solutionLocation: secondaryLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== SQL DB module ========== //
module sqlDBModule './modules/data/sql-db.bicep' = if (azureEnvOnly) {
  name: 'deploy_sql_db'
  params: {
    serverName: 'sql-${solutionSuffix}'
    sqlDBName: 'sqldb-${solutionSuffix}'
    solutionLocation: secondaryLocation
    deployerPrincipalId: deployingUserPrincipalId
  }
  scope: resourceGroup(resourceGroup().name)
}

module hostingplan './modules/compute/app-service-plan.bicep' = if (shouldDeployApp) {
  name: 'deploy_app_service_plan'
  params: {
    solutionLocation: solutionLocation
    HostingPlanName: 'asp-${solutionSuffix}'
  }
}

// Resolve the Log Analytics workspace resource ID for diagnostic settings.
// Uses the existing workspace ID when provided; otherwise constructs the ID from AI Foundry outputs.
var resolvedLogAnalyticsWorkspaceId = !empty(existingLogAnalyticsWorkspaceId)
  ? existingLogAnalyticsWorkspaceId
  : '/subscriptions/${log_analytics.outputs.logAnalyticsWorkspaceSubscription}/resourceGroups/${log_analytics.outputs.logAnalyticsWorkspaceResourceGroup}/providers/Microsoft.OperationalInsights/workspaces/${log_analytics.outputs.logAnalyticsWorkspaceResourceName}'

// ========== Compute settings ========== //
var backendCsApiImageName = 'DOCKER|dataagentscontainerreg.azurecr.io/da-api-dotnet:latest_v2'
var reactAppLayoutConfig = '''{
  "appConfig": {
      "CHAT_CHATHISTORY": {
        "CHAT": 70,
        "CHATHISTORY": 30
      }
    }
  }
}'''

// ========== Backend Deployment (Python) ========== //
module backend_custom './modules/compute/app-service-custom.bicep' = if (shouldDeployApp && backendRuntimeStack == 'python') {
  name: 'deploy_backend_custom'
  params: {
    solutionName: 'api-${solutionSuffix}'
    solutionLocation: solutionLocation
    appServicePlanId: hostingplan!.outputs.name
    linuxFxVersion: 'PYTHON|3.11'
    appCommandLine: 'uvicorn app:app --host 0.0.0.0 --port 8000'
    enableSystemAssignedIdentity: true
    azdServiceName: 'api'
    logAnalyticsWorkspaceId: resolvedLogAnalyticsWorkspaceId
    appSettings: {
      APPINSIGHTS_INSTRUMENTATIONKEY: app_insights.outputs.applicationInsightsInstrumentationKey
      REACT_APP_LAYOUT_CONFIG: reactAppLayoutConfig
      PYTHONUNBUFFERED: '1'
      SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
      ENABLE_ORYX_BUILD: 'true'
      AZURE_ENV_GPT_MODEL_NAME: gptModelName
      AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME: embeddingModel
      AZURE_OPENAI_ENDPOINT: aiFoundryEndpoint
      AZURE_ENV_OPENAI_API_VERSION: azureOpenaiAPIVersion
      AZURE_OPENAI_RESOURCE: aiFoundryName
      AZURE_AI_AGENT_ENDPOINT: projectEndpoint
      AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
      AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
      USE_CHAT_HISTORY_ENABLED: 'True'
      AZURE_COSMOSDB_ACCOUNT: cosmosDBModule!.outputs.cosmosAccountName
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: cosmosDBModule!.outputs.cosmosContainerName
      AZURE_COSMOSDB_DATABASE: cosmosDBModule!.outputs.cosmosDatabaseName
      AZURE_COSMOSDB_ENABLE_FEEDBACK: 'True'
      AZURE_SQLDB_DATABASE: azureEnvOnly ? sqlDBModule!.outputs.sqlDbName : ''
      AZURE_SQLDB_SERVER: azureEnvOnly ? sqlDBModule!.outputs.sqlServerName : ''
      AZURE_SQLDB_USER_MID: ''
      API_UID: ''
      AZURE_AI_SEARCH_ENDPOINT: ai_search!.outputs.aiSearchTarget
      AZURE_AI_SEARCH_INDEX: 'knowledge_index'
      AZURE_AI_SEARCH_CONNECTION_NAME: ai_search!.outputs.aiSearchConnectionName

      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: app_insights.outputs.applicationInsightsConnectionString
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
module backend_csapi_docker './modules/compute/app-service.bicep' = if (shouldDeployApp && backendRuntimeStack == 'dotnet') {
  name: 'deploy_backend_csapi_docker'
  params: {
    solutionName: 'api-cs-${solutionSuffix}'
    solutionLocation: solutionLocation
    appServicePlanId: hostingplan!.outputs.name
    appImageName: backendCsApiImageName
    appSettings: {
      APPINSIGHTS_INSTRUMENTATIONKEY: app_insights.outputs.applicationInsightsInstrumentationKey
      REACT_APP_LAYOUT_CONFIG: reactAppLayoutConfig
      AZURE_ENV_GPT_MODEL_NAME: gptModelName
      AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME: embeddingModel
      AZURE_OPENAI_ENDPOINT: aiFoundryEndpoint
      AZURE_ENV_OPENAI_API_VERSION: azureOpenaiAPIVersion
      AZURE_OPENAI_RESOURCE: aiFoundryName
      AZURE_AI_AGENT_ENDPOINT: projectEndpoint
      AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
      AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
      USE_CHAT_HISTORY_ENABLED: 'True'
      AZURE_COSMOSDB_ACCOUNT: cosmosDBModule!.outputs.cosmosAccountName
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: cosmosDBModule!.outputs.cosmosContainerName
      AZURE_COSMOSDB_DATABASE: cosmosDBModule!.outputs.cosmosDatabaseName
      AZURE_COSMOSDB_ENABLE_FEEDBACK: 'True'
      API_UID: ''
      AZURE_AI_SEARCH_ENDPOINT: ai_search!.outputs.aiSearchTarget
      AZURE_AI_SEARCH_INDEX: 'call_transcripts_index'
      AZURE_AI_SEARCH_CONNECTION_NAME: ai_search!.outputs.aiSearchConnectionName

      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: app_insights.outputs.applicationInsightsConnectionString
      DUMMY_TEST: 'True'
      SOLUTION_NAME: solutionSuffix
      APP_ENV: 'Prod'

      FABRIC_SQL_DATABASE: ''
      FABRIC_SQL_SERVER: ''
      FABRIC_SQL_CONNECTION_STRING: ''
    }
  }
  scope: resourceGroup(resourceGroup().name)
}

var landingText = usecase == 'Retail-sales-analysis' ? 'You can ask questions around sales, products and orders.' : 'You can ask questions around customer policies, claims and communications.'

// ========== Frontend Deployment ========== //
module frontend_custom './modules/compute/app-service-custom.bicep' = if (shouldDeployApp) {
  name: 'deploy_frontend_custom'
  params: {
    solutionName: 'app-${solutionSuffix}'
    solutionLocation: solutionLocation
    appServicePlanId: hostingplan!.outputs.name
    linuxFxVersion: 'NODE|20-lts'
    appCommandLine: 'npx serve -s build -l 8080'
    enableSystemAssignedIdentity: false
    azdServiceName: 'webapp'
    logAnalyticsWorkspaceId: resolvedLogAnalyticsWorkspaceId
    appSettings: {
      APPINSIGHTS_INSTRUMENTATIONKEY: app_insights.outputs.applicationInsightsInstrumentationKey
      APP_API_BASE_URL: backendRuntimeStack == 'python' ? backend_custom!.outputs.appUrl : backend_csapi_docker!.outputs.appUrl
      CHAT_LANDING_TEXT: landingText
    }
  }
  scope: resourceGroup(resourceGroup().name)
}

module role_assignments './modules/identity/role-assignments.bicep' = {
  name: 'deploy_role_assignments'
  params: {
    solutionName: solutionSuffix
    shouldDeployApp: shouldDeployApp
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    aiFoundryName: aiFoundryName
    aiSearchName: ai_search!.outputs.aiSearchName
    storageAccountName: storage_account!.outputs.storageAccountName
    aiProjectPrincipalId: aiProjectPrincipalId
    searchPrincipalId: ai_search!.outputs.searchPrincipalId
    deployingUserPrincipalId: deployingUserPrincipalId
    deployingUserPrincipalType: deployingUserPrincipalType
    backendAppPrincipalId: shouldDeployApp && backendRuntimeStack == 'python' ? backend_custom!.outputs.identityPrincipalId : ''
    backendCsApiPrincipalId: shouldDeployApp && backendRuntimeStack == 'dotnet' ? backend_csapi_docker!.outputs.identityPrincipalId : ''
    cosmosAccountName: shouldDeployApp ? cosmosDBModule!.outputs.cosmosAccountName : ''
    existingAiProjectPrincipalId: !empty(existingFoundryProjectResourceId) ? existing_project_setup!.outputs.aiProjectPrincipalId : ''
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
output AZURE_OPENAI_ENDPOINT string = aiFoundryEndpoint

@description('Embedding model deployment name for vector search')
output AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME string = embeddingModel

@description('Azure SQL database name (Azure-only mode)')
output AZURE_SQLDB_DATABASE string = azureEnvOnly ? sqlDBModule!.outputs.sqlDbName : ''

@description('Azure SQL server fully qualified domain name (Azure-only mode)')
output AZURE_SQLDB_SERVER string = azureEnvOnly ? sqlDBModule!.outputs.sqlServerName : ''

@description('Managed identity client ID for SQL authentication (Azure-only mode)')
output AZURE_SQLDB_USER_MID string = ''

@description('Backend API managed identity client ID (system-assigned, resolved at runtime)')
output API_UID string = ''

@description('Azure AI Agent service endpoint URL')
output AZURE_AI_AGENT_ENDPOINT string = projectEndpoint

@description('Model deployment name used by Azure AI Agent')
output AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME string = gptModelName

@description('Backend API App Service name')
output API_APP_NAME string = shouldDeployApp ? (backendRuntimeStack == 'python' ? 'api-${solutionSuffix}' : 'api-cs-${solutionSuffix}') : ''

@description('Backend API managed identity object/principal ID (system-assigned)')
output API_PID string = shouldDeployApp ? (backendRuntimeStack == 'python' ? backend_custom!.outputs.identityPrincipalId : backend_csapi_docker!.outputs.identityPrincipalId) : ''

@description('Backend API App Service name')
output MID_DISPLAY_NAME string = shouldDeployApp ? (backendRuntimeStack == 'python' ? 'api-${solutionSuffix}' : 'api-cs-${solutionSuffix}') : ''

@description('Frontend web application URL')
output WEB_APP_URL string = shouldDeployApp ? frontend_custom!.outputs.appUrl : ''

@description('Deployed use case identifier (e.g., Retail-sales-analysis)')
output USE_CASE string = usecase

@description('Azure AI Search service endpoint URL')
output AZURE_AI_SEARCH_ENDPOINT string = ai_search!.outputs.aiSearchTarget

@description('Azure AI Search index name for document search')
output AZURE_AI_SEARCH_INDEX string = 'knowledge_index'

@description('Azure AI Search service resource name')
output AZURE_AI_SEARCH_NAME string = ai_search!.outputs.aiSearchName

@description('Local path to documents folder for search indexing')
output SEARCH_DATA_FOLDER string = 'data/default/documents'

@description('AI Foundry connection name for Azure AI Search')
output AZURE_AI_SEARCH_CONNECTION_NAME string = ai_search!.outputs.aiSearchConnectionName

@description('AI Foundry connection ID for Azure AI Search')
output AZURE_AI_SEARCH_CONNECTION_ID string = aiSearchConnectionId

@description('Azure AI Foundry project endpoint URL')
output AZURE_AI_PROJECT_ENDPOINT string = projectEndpoint

@description('Azure AI Foundry resource ID for role assignments')
output AI_FOUNDRY_RESOURCE_ID string = aiFoundryResourceId

@description('Azure AI Foundry project name')
output AZURE_AI_PROJECT_NAME string = aiProjectName

@description('Azure AI Services resource name')
output AI_SERVICE_NAME string = aiFoundryName

@description('Azure AI Foundry project managed identity principal ID')
output FOUNDRY_PROJECT_PID string = aiProjectPrincipalId

@description('Backend runtime stack (python or dotnet)')
output BACKEND_RUNTIME_STACK string = backendRuntimeStack

@description('Flag indicating whether to deploy App Service')
output AZURE_ENV_DEPLOY_APP bool = deployApp

@description('Flag indicating Azure-only mode (no Fabric)')
output AZURE_ENV_ONLY bool = azureEnvOnly

@description('Backend API managed identity client ID (system-assigned, resolved at runtime)')
output USER_MID string = ''

@description('Existing or newly created AI project resource ID')
output AZURE_EXISTING_AIPROJECT_RESOURCE_ID string = aiFoundryResourceId
