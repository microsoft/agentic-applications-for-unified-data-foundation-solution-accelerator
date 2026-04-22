// ========== main.bicep ========== //
targetScope = 'resourceGroup'
var abbrs = loadJsonContent('./abbreviations.json')
@minLength(3)
@maxLength(20)
@description('A unique  application/solution name for all resources in this deployment. This should be 3-20 characters long:')
param environmentName string = 'agenticappudf'

@maxLength(5)
@description('Optional. A unique text value for the solution.')
param solutionUniqueText string = substring(uniqueString(subscription().id, resourceGroup().name, environmentName), 0, 5)

@description('Optional: Existing Log Analytics Workspace Resource ID')
param existingLogAnalyticsWorkspaceId string = ''

@description('Use this parameter to use an existing AI project resource ID')
param azureExistingAIProjectResourceId string = ''

@description('Optional. created by user name')
param createdBy string = contains(deployer(), 'userPrincipalName')? split(deployer().userPrincipalName, '@')[0]: deployer().objectId

@description('Choose the programming language:')
@allowed([
  'python'
  'dotnet'
])
param backendRuntimeStack string = 'python'

@minLength(1)
@description('Industry use case for deployment:')
@allowed([
  'Retail-sales-analysis'
  'Insurance-improve-customer-meetings'
])
param usecase string = 'Retail-sales-analysis'

@minLength(1)
@description('Secondary location for databases creation(example:eastus2):')
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

param azureOpenAIApiVersion string = '2025-01-01-preview'

param azureAiAgentApiVersion string = '2025-05-01'

@minValue(10)
@description('Capacity of the GPT deployment:')
// You can increase this, but capacity is limited per model/region, so you will get errors if you go over
// https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits
param gptDeploymentCapacity int = 150

// @description('Optional. The tags to apply to all deployed Azure resources.')
// param tags resourceInput<'Microsoft.Resources/resourceGroups@2025-04-01'>.tags = {}

@minLength(1)
@description('Name of the Text Embedding model to deploy:')
@allowed([
  'text-embedding-3-small'
])
param embeddingModel string = 'text-embedding-3-small'

@minValue(10)
@description('Capacity of the Embedding Model deployment')
param embeddingDeploymentCapacity int = 80

param imageTag string = 'latest_v2'

@description('Deploy the application components (Cosmos DB, API, Frontend). Set to true to deploy the app.')
param deployApp bool = true

@description('Set to true for workshop deployment with sample data and simplified configuration.')
param isWorkshop bool = true

@description('Set to true to deploy Azure SQL Server, otherwise Fabric SQL is used.')
param azureEnvOnly bool = false

@description('Enable chat history.')
param useChatHistoryEnabled bool = true
var useChatHistoryEnabledSetting = useChatHistoryEnabled ? 'True' : 'False'

// If isWorkshop is false, always deploy; if isWorkshop is true, respect deployApp
var shouldDeployApp = !isWorkshop || deployApp

param AZURE_LOCATION string=''
var solutionLocation = empty(AZURE_LOCATION) ? resourceGroup().location : AZURE_LOCATION

var solutionSuffix = toLower(trim(replace(
  replace(
    replace(replace(replace(replace('${environmentName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''),
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
  azd:{
    type: 'location'
    usageName: [
      'OpenAI.GlobalStandard.gpt4.1-mini,100'
      'OpenAI.GlobalStandard.text-embedding-3-small,80'
    ]
  }
})
@description('Location for AI Foundry deployment. This is the location where the AI Foundry resources will be deployed.')
param aiDeploymentsLocation string

@description('Name of the Azure Container Registry')
param acrName string = 'dataagentscontainerreg'

//Get the current deployer's information
var deployerInfo = deployer()
var deployingUserPrincipalId = deployerInfo.objectId
var existingTags = resourceGroup().tags ?? {}

@description('The principal type of the deploying user. Use ServicePrincipal for CI/CD pipelines with OIDC.')
@allowed(['User', 'ServicePrincipal'])
param deployingUserPrincipalType string = 'User'

// ========== Resource Group Tag ========== //
resource resourceGroupTags 'Microsoft.Resources/tags@2023-07-01' = if (!isWorkshop) {
  name: 'default'
  properties: {
   tags: union(
      existingTags,
      {
        TemplateName: 'Unified Data Analysis Agents'
        CreatedBy: createdBy
        DeploymentName: deployment().name
        Type: 'Non-WAF'
      }
    )
  }
}

// ========== Managed Identity ========== //
module managedIdentityModule 'deploy_managed_identity.bicep' = {
  name: 'deploy_managed_identity'
  params: {
    miName:'${abbrs.security.managedIdentity}${solutionSuffix}'
    solutionName: solutionSuffix
    solutionLocation: solutionLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

// ==========AI Foundry and related resources ========== //
module aifoundry 'deploy_ai_foundry.bicep' = {
  name: 'deploy_ai_foundry'
  params: {
    solutionName: solutionSuffix
    solutionLocation: aiDeploymentsLocation
    deploymentType: deploymentType
    gptModelName: gptModelName
    gptModelVersion: gptModelVersion
    gptDeploymentCapacity: gptDeploymentCapacity
    embeddingModel: embeddingModel
    embeddingDeploymentCapacity: embeddingDeploymentCapacity
    managedIdentityObjectId: managedIdentityModule.outputs.managedIdentityOutput.objectId
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
    azureExistingAIProjectResourceId: azureExistingAIProjectResourceId
    deployingUserPrincipalId: deployingUserPrincipalId
    deployingUserPrincipalType: deployingUserPrincipalType
    isWorkshop: isWorkshop
    searchServiceLocation: searchServiceLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Cosmos DB module ========== //
module cosmosDBModule 'deploy_cosmos_db.bicep' = if (isWorkshop && deployApp) {
  name: 'deploy_cosmos_db'
  params: {
    accountName: '${abbrs.databases.cosmosDBDatabase}${solutionSuffix}'
    solutionLocation: secondaryLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

//========== SQL DB module ========== //
module sqlDBModule 'deploy_sql_db.bicep' = if(isWorkshop && azureEnvOnly) {
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

// ========== Backend Deployment (Python) ========== //
module backend_docker 'deploy_backend_docker.bicep' = if (shouldDeployApp && backendRuntimeStack == 'python') {
  name: 'deploy_backend_docker'
  params: {
    name: 'api-${solutionSuffix}'
    solutionLocation: solutionLocation
    imageTag: imageTag
    acrName: acrName
    appServicePlanId: hostingplan!.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    userassignedIdentityId: managedIdentityModule.outputs.managedIdentityBackendAppOutput.id
    // keyVaultName: kvault.outputs.keyvaultName
    aiServicesName: aifoundry.outputs.aiServicesName
    azureExistingAIProjectResourceId: azureExistingAIProjectResourceId
    enableCosmosDb: shouldDeployApp && isWorkshop
    appSettings: {
      AZURE_ENV_GPT_MODEL_NAME: gptModelName
      AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME: embeddingModel
      AZURE_OPENAI_ENDPOINT: aifoundry.outputs.aiServicesTarget
      AZURE_ENV_OPENAI_API_VERSION: azureOpenAIApiVersion
      AZURE_OPENAI_RESOURCE: aifoundry.outputs.aiServicesName
      AZURE_AI_AGENT_ENDPOINT: aifoundry.outputs.projectEndpoint
      AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
      AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
      USE_CHAT_HISTORY_ENABLED: useChatHistoryEnabledSetting
      AZURE_COSMOSDB_ACCOUNT: isWorkshop ? cosmosDBModule!.outputs.cosmosAccountName : ''
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: isWorkshop ? cosmosDBModule!.outputs.cosmosContainerName : ''
      AZURE_COSMOSDB_DATABASE: isWorkshop? cosmosDBModule!.outputs.cosmosDatabaseName : ''
      AZURE_COSMOSDB_ENABLE_FEEDBACK: isWorkshop ? 'True' : ''
      AZURE_SQLDB_DATABASE: (isWorkshop && azureEnvOnly) ? sqlDBModule!.outputs.sqlDbName : ''
      AZURE_SQLDB_SERVER: (isWorkshop && azureEnvOnly) ? sqlDBModule!.outputs.sqlServerName : ''
      AZURE_SQLDB_USER_MID: (isWorkshop && azureEnvOnly) ? managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId : ''
      API_UID: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
      AZURE_AI_SEARCH_ENDPOINT: isWorkshop ? aifoundry.outputs.aiSearchTarget : ''
      AZURE_AI_SEARCH_INDEX: isWorkshop ? 'knowledge_index' : ''
      AZURE_AI_SEARCH_CONNECTION_NAME: isWorkshop ? aifoundry.outputs.aiSearchConnectionName : ''

      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: aifoundry.outputs.applicationInsightsConnectionString
      DUMMY_TEST: 'True'
      SOLUTION_NAME: solutionSuffix
      IS_WORKSHOP: isWorkshop ? 'True' : 'False'
      AZURE_ENV_ONLY: azureEnvOnly ? 'True' : 'False'
      APP_ENV: 'Prod'
      AZURE_BASIC_LOGGING_LEVEL: 'INFO'
      AZURE_PACKAGE_LOGGING_LEVEL: 'WARNING'
      AZURE_LOGGING_PACKAGES: ''

      AGENT_NAME_CHAT: ''
      AGENT_NAME_TITLE: ''

      FABRIC_SQL_DATABASE: ''
      FABRIC_SQL_SERVER: ''
      FABRIC_SQL_CONNECTION_STRING: ''
    }
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Backend Deployment (C#) ========== //
module backend_csapi_docker 'deploy_backend_csapi_docker.bicep' = if (shouldDeployApp && backendRuntimeStack == 'dotnet') {
  name: 'deploy_backend_csapi_docker'
  params: {
    name: 'api-cs-${solutionSuffix}'
    solutionLocation: solutionLocation
    imageTag: imageTag
    acrName: acrName
    appServicePlanId: hostingplan!.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    userassignedIdentityId: managedIdentityModule.outputs.managedIdentityBackendAppOutput.id
    aiServicesName: aifoundry.outputs.aiServicesName
    azureExistingAIProjectResourceId: azureExistingAIProjectResourceId
    appSettings: {
      AZURE_ENV_GPT_MODEL_NAME: gptModelName
      AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME: embeddingModel
      AZURE_OPENAI_ENDPOINT: aifoundry.outputs.aiServicesTarget
      AZURE_ENV_OPENAI_API_VERSION: azureOpenAIApiVersion
      AZURE_OPENAI_RESOURCE: aifoundry.outputs.aiServicesName
      AZURE_AI_AGENT_ENDPOINT: aifoundry.outputs.projectEndpoint
      AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
      AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
      USE_CHAT_HISTORY_ENABLED: useChatHistoryEnabledSetting
      AZURE_COSMOSDB_ACCOUNT: isWorkshop ? cosmosDBModule!.outputs.cosmosAccountName : ''
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: isWorkshop ? cosmosDBModule!.outputs.cosmosContainerName : ''
      AZURE_COSMOSDB_DATABASE: isWorkshop ? cosmosDBModule!.outputs.cosmosDatabaseName : ''
      AZURE_COSMOSDB_ENABLE_FEEDBACK: isWorkshop ? 'True' : ''
      API_UID: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
      AZURE_AI_SEARCH_ENDPOINT: isWorkshop ? aifoundry.outputs.aiSearchTarget : ''
      AZURE_AI_SEARCH_INDEX: isWorkshop ? 'call_transcripts_index' : ''
      AZURE_AI_SEARCH_CONNECTION_NAME: isWorkshop ? aifoundry.outputs.aiSearchConnectionName : ''

      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: aifoundry.outputs.applicationInsightsConnectionString
      DUMMY_TEST: 'True'
      SOLUTION_NAME: solutionSuffix 
      APP_ENV: 'Prod'

      AGENT_NAME_CHAT: ''
      AGENT_NAME_TITLE: ''

      FABRIC_SQL_DATABASE: ''
      FABRIC_SQL_SERVER: ''
      FABRIC_SQL_CONNECTION_STRING: ''
    }
  }
  scope: resourceGroup(resourceGroup().name)
}

var landingText = usecase == 'Retail-sales-analysis' ? 'You can ask questions around sales, products and orders.' : 'You can ask questions around customer policies, claims and communications.'

module frontend_docker 'deploy_frontend_docker.bicep' = if (shouldDeployApp) {
  name: 'deploy_frontend_docker'
  params: {
    name: '${abbrs.compute.webApp}${solutionSuffix}'
    solutionLocation:solutionLocation
    imageTag: imageTag
    acrName: acrName
    appServicePlanId: hostingplan!.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    appSettings:{
      APP_API_BASE_URL: backendRuntimeStack == 'python' ? backend_docker!.outputs.appUrl : backend_csapi_docker!.outputs.appUrl
      CHAT_LANDING_TEXT: landingText
      IS_WORKSHOP: isWorkshop ? 'True' : 'False'
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
output AZURE_COSMOSDB_ACCOUNT string = shouldDeployApp && isWorkshop ? cosmosDBModule!.outputs.cosmosAccountName : ''

@description('Cosmos DB container name for storing conversations')
output AZURE_COSMOSDB_CONVERSATIONS_CONTAINER string = isWorkshop ? 'conversations' : ''

@description('Cosmos DB database name for conversation history')
output AZURE_COSMOSDB_DATABASE string = isWorkshop ? 'db_conversation_history' : ''

@description('GPT model deployment name (e.g., gpt-4o-mini)')
output AZURE_ENV_GPT_MODEL_NAME string = gptModelName

@description('Azure OpenAI service endpoint URL')
output AZURE_OPENAI_ENDPOINT string = aifoundry.outputs.aiServicesTarget

@description('Embedding model deployment name for vector search')
output AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME string = embeddingModel

@description('Azure SQL database name (Azure-only mode)')
output AZURE_SQLDB_DATABASE string = (isWorkshop && azureEnvOnly) ? sqlDBModule!.outputs.sqlDbName : ''

@description('Azure SQL server fully qualified domain name (Azure-only mode)')
output AZURE_SQLDB_SERVER string = (isWorkshop && azureEnvOnly) ? sqlDBModule!.outputs.sqlServerName : ''

@description('Managed identity client ID for SQL authentication (Azure-only mode)')
output AZURE_SQLDB_USER_MID string = (isWorkshop && azureEnvOnly) ? managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId : ''

@description('Backend API managed identity client ID')
output API_UID string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId

@description('Azure AI Agent service endpoint URL')
output AZURE_AI_AGENT_ENDPOINT string = aifoundry.outputs.projectEndpoint

@description('Model deployment name used by Azure AI Agent')
output AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME string = gptModelName

@description('Backend API App Service name')
output API_APP_NAME string = shouldDeployApp ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.appName : backend_csapi_docker!.outputs.appName) : ''

@description('Backend API managed identity object/principal ID')
output API_PID string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.objectId

@description('Backend API managed identity display name')
output MID_DISPLAY_NAME string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.name

@description('Frontend web application URL')
output WEB_APP_URL string = shouldDeployApp ? frontend_docker!.outputs.appUrl : ''

@description('Deployed use case identifier (e.g., Retail-sales-analysis)')
output USE_CASE string = usecase

@description('Azure AI Search service endpoint URL')
output AZURE_AI_SEARCH_ENDPOINT string = isWorkshop ? aifoundry.outputs.aiSearchTarget : ''

@description('Azure AI Search index name for document search')
output AZURE_AI_SEARCH_INDEX string = isWorkshop ? 'knowledge_index' : ''

@description('Azure AI Search service resource name')
output AZURE_AI_SEARCH_NAME string = isWorkshop ? aifoundry.outputs.aiSearchName : ''

@description('Local path to documents folder for search indexing')
output SEARCH_DATA_FOLDER string = isWorkshop ? 'data/default/documents' : ''

@description('AI Foundry connection name for Azure AI Search')
output AZURE_AI_SEARCH_CONNECTION_NAME string = isWorkshop ? aifoundry.outputs.aiSearchConnectionName : ''

@description('AI Foundry connection ID for Azure AI Search')
output AZURE_AI_SEARCH_CONNECTION_ID string = isWorkshop ? aifoundry.outputs.aiSearchConnectionId : ''

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

@description('Flag indicating whether chat history storage is enabled')
output USE_CHAT_HISTORY_ENABLED string = useChatHistoryEnabledSetting

@description('Backend runtime stack (python or dotnet)')
output BACKEND_RUNTIME_STACK string = backendRuntimeStack

@description('Flag indicating workshop deployment mode')
output IS_WORKSHOP bool = isWorkshop

@description('Flag indicating whether to deploy App Service')
output AZURE_ENV_DEPLOY_APP bool = deployApp

@description('Flag indicating Azure-only mode (no Fabric)')
output AZURE_ENV_ONLY bool = azureEnvOnly
