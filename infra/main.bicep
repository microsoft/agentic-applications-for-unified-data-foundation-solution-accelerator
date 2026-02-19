// ========== main.bicep ========== //
targetScope = 'resourceGroup'
var abbrs = loadJsonContent('./abbreviations.json')
@minLength(3)
@maxLength(20)
@description('A unique prefix for all resources in this deployment. This should be 3-20 characters long:')
param environmentName string

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

// @minLength(1)
// @description('Location for the Content Understanding service deployment:')
// @allowed(['swedencentral', 'australiaeast'])
// @metadata({
//   azd: {
//     type: 'location'
//   }
// })
// param contentUnderstandingLocation string = 'swedencentral'
var contentUnderstandingLocation = ''

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
param gptModelName string = 'gpt-4o-mini'

@description('Version of the GPT model to deploy:')
param gptModelVersion string = '2024-07-18'

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
  'text-embedding-ada-002'
])
param embeddingModel string = 'text-embedding-ada-002'

@minValue(10)
@description('Capacity of the Embedding Model deployment')
param embeddingDeploymentCapacity int = 80

param imageTag string = isWorkshop ? 'latest_workshop' : 'latest_v2'

@description('Deploy the application components (Cosmos DB, API, Frontend). Set to true to deploy the app.')
param deployApp bool = false

@description('Set to true for workshop deployment with sample data and simplified configuration.')
param isWorkshop bool = true

@description('Set to true to deploy Azure SQL Server, otherwise Fabric SQL is used.')
param azureEnvOnly bool = false

// If isWorkshop is false, always deploy; if isWorkshop is true, respect deployApp
var shouldDeployApp = !isWorkshop || deployApp

param AZURE_LOCATION string=''
var solutionLocation = empty(AZURE_LOCATION) ? resourceGroup().location : AZURE_LOCATION

var uniqueId = toLower(uniqueString(subscription().id, environmentName, solutionLocation))

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
      'OpenAI.GlobalStandard.gpt-4o-mini,150'
      'OpenAI.GlobalStandard.text-embedding-ada-002,80'
    ]
  }
})
@description('Location for AI Foundry deployment. This is the location where the AI Foundry resources will be deployed.')
param aiDeploymentsLocation string

var solutionPrefix = 'da${padLeft(take(uniqueId, 12), 12, '0')}'

@description('Name of the Azure Container Registry')
param acrName string = isWorkshop ? 'dataagentscontainerregworkshop' : 'dataagentscontainerreg'

//Get the current deployer's information
var deployerInfo = deployer()
var deployingUserPrincipalId = deployerInfo.objectId
var existingTags = resourceGroup().tags ?? {}

// ========== Resource Group Tag ========== //
resource resourceGroupTags 'Microsoft.Resources/tags@2021-04-01' = if (!isWorkshop) {
  name: 'default'
  properties: {
   tags: union(
      existingTags,
      {
        TemplateName: 'Unified Data Analysis Agents'
        CreatedBy: createdBy
        DeploymentName: deployment().name
      }
    )
  }
}

// ========== Managed Identity ========== //
module managedIdentityModule 'deploy_managed_identity.bicep' = {
  name: 'deploy_managed_identity'
  params: {
    miName:'${abbrs.security.managedIdentity}${solutionPrefix}'
    solutionName: solutionPrefix
    solutionLocation: solutionLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

// ==========Key Vault Module ========== //
// module kvault 'deploy_keyvault.bicep' = {
//   name: 'deploy_keyvault'
//   params: {
//     keyvaultName: '${abbrs.security.keyVault}${solutionPrefix}'
//     solutionLocation: solutionLocation
//     managedIdentityObjectId:managedIdentityModule.outputs.managedIdentityOutput.objectId
//   }
//   scope: resourceGroup(resourceGroup().name)
// }

// ==========AI Foundry and related resources ========== //
module aifoundry 'deploy_ai_foundry.bicep' = {
  name: 'deploy_ai_foundry'
  params: {
    solutionName: solutionPrefix
    solutionLocation: aiDeploymentsLocation
    deploymentType: deploymentType
    gptModelName: gptModelName
    gptModelVersion: gptModelVersion
    // azureOpenAIApiVersion: azureOpenAIApiVersion
    gptDeploymentCapacity: gptDeploymentCapacity
    embeddingModel: embeddingModel
    embeddingDeploymentCapacity: embeddingDeploymentCapacity
    managedIdentityObjectId: managedIdentityModule.outputs.managedIdentityOutput.objectId
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
    azureExistingAIProjectResourceId: azureExistingAIProjectResourceId
    deployingUserPrincipalId: deployingUserPrincipalId
    isWorkshop: isWorkshop
    searchServiceLocation: searchServiceLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

// ==========CS API Module ========== //
// module csapi 'deploy_csapi_app_service.bicep' = {
//    name: 'deployCsApiModule'
//   params: {
//     location: resourceGroup().location
//     siteName: '${environmentName}-csapi-${uniqueString(resourceGroup().id)}'
//     keyVaultName: '${environmentName}-csapi-${uniqueString(resourceGroup().id)}-kv'
//     openAiSecretName: 'AZURE_OPENAI_KEY'
//     sqlSecretName: 'FABRIC_SQL_CONNECTION_STRING'
//     openAiSecretValue: ''
//     sqlSecretValue: ''
//     skuName: 'P1v2'
//   }
// }


// ========== Cosmos DB module ========== //
module cosmosDBModule 'deploy_cosmos_db.bicep' = if (isWorkshop && deployApp) {
  name: 'deploy_cosmos_db'
  params: {
    accountName: '${abbrs.databases.cosmosDBDatabase}${solutionPrefix}'
    solutionLocation: secondaryLocation
    // keyVaultName: kvault.outputs.keyvaultName
  }
  scope: resourceGroup(resourceGroup().name)
}

//========== SQL DB module ========== //
module sqlDBModule 'deploy_sql_db.bicep' = if(isWorkshop && azureEnvOnly) {
  name: 'deploy_sql_db'
  params: {
    serverName: '${abbrs.databases.sqlDatabaseServer}${solutionPrefix}'
    sqlDBName: '${abbrs.databases.sqlDatabase}${solutionPrefix}'
    solutionLocation: secondaryLocation
    //keyVaultName: kvault.outputs.keyvaultName
    managedIdentityName: managedIdentityModule.outputs.managedIdentityOutput.name
    deployerPrincipalId: deployingUserPrincipalId
    // sqlUsers: [
    //   {
    //     principalId: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
    //     principalName: managedIdentityModule.outputs.managedIdentityBackendAppOutput.name
    //     databaseRoles: ['db_datareader', 'db_datawriter']
    //   }
    // ]
  }
  scope: resourceGroup(resourceGroup().name)
}

module hostingplan 'deploy_app_service_plan.bicep' = if (shouldDeployApp) {
  name: 'deploy_app_service_plan'
  params: {
    solutionLocation: solutionLocation
    HostingPlanName: '${abbrs.compute.appServicePlan}${solutionPrefix}'
  }
}

// ========== Backend Deployment (Python) ========== //
module backend_docker 'deploy_backend_docker.bicep' = if (shouldDeployApp && backendRuntimeStack == 'python') {
  name: 'deploy_backend_docker'
  params: {
    name: 'api-${solutionPrefix}'
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
    // aiSearchName: aifoundry.outputs.aiSearchName 
    appSettings: {
      AZURE_OPENAI_DEPLOYMENT_MODEL: gptModelName
      AZURE_OPENAI_ENDPOINT: aifoundry.outputs.aiServicesTarget
      AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
      AZURE_OPENAI_RESOURCE: aifoundry.outputs.aiServicesName
      AZURE_AI_AGENT_ENDPOINT: aifoundry.outputs.projectEndpoint
      AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
      AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
      USE_CHAT_HISTORY_ENABLED: 'True'
      AZURE_COSMOSDB_ACCOUNT: isWorkshop ? cosmosDBModule!.outputs.cosmosAccountName : ''
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: isWorkshop ? cosmosDBModule!.outputs.cosmosContainerName : ''
      AZURE_COSMOSDB_DATABASE: isWorkshop? cosmosDBModule!.outputs.cosmosDatabaseName : ''
      AZURE_COSMOSDB_ENABLE_FEEDBACK: isWorkshop ? 'True' : ''
      SQLDB_DATABASE: (isWorkshop && azureEnvOnly) ? sqlDBModule!.outputs.sqlDbName : ''
      SQLDB_SERVER: (isWorkshop && azureEnvOnly) ? sqlDBModule!.outputs.sqlServerName : ''
      SQLDB_USER_MID: (isWorkshop && azureEnvOnly) ? managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId : ''
      API_UID: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
      AZURE_AI_SEARCH_ENDPOINT: isWorkshop ? aifoundry.outputs.aiSearchTarget : ''
      AZURE_AI_SEARCH_INDEX: isWorkshop ? 'knowledge_index' : ''
      AZURE_AI_SEARCH_CONNECTION_NAME: isWorkshop ? aifoundry.outputs.aiSearchConnectionName : ''

      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: aifoundry.outputs.applicationInsightsConnectionString
      DUMMY_TEST: 'True'
      SOLUTION_NAME: solutionPrefix
      IS_WORKSHOP: isWorkshop ? 'True' : 'False'
      AZURE_ENV_ONLY: azureEnvOnly ? 'True' : 'False'
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

// ========== Backend Deployment (C#) ========== //
module backend_csapi_docker 'deploy_backend_csapi_docker.bicep' = if (shouldDeployApp && backendRuntimeStack == 'dotnet') {
  name: 'deploy_backend_csapi_docker'
  params: {
    name: 'api-cs-${solutionPrefix}'
    solutionLocation: solutionLocation
    imageTag: imageTag
    acrName: acrName
    appServicePlanId: hostingplan!.outputs.name
    applicationInsightsId: aifoundry.outputs.applicationInsightsId
    userassignedIdentityId: managedIdentityModule.outputs.managedIdentityBackendAppOutput.id
    // keyVaultName: kvault.outputs.keyvaultName
    aiServicesName: aifoundry.outputs.aiServicesName
    azureExistingAIProjectResourceId: azureExistingAIProjectResourceId
    // aiSearchName: aifoundry.outputs.aiSearchName 
    appSettings: {
      AZURE_OPENAI_DEPLOYMENT_MODEL: gptModelName
      AZURE_OPENAI_ENDPOINT: aifoundry.outputs.aiServicesTarget
      AZURE_OPENAI_API_VERSION: azureOpenAIApiVersion
      AZURE_OPENAI_RESOURCE: aifoundry.outputs.aiServicesName
      AZURE_AI_AGENT_ENDPOINT: aifoundry.outputs.projectEndpoint
      AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
      AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
      USE_CHAT_HISTORY_ENABLED: 'True'
      AZURE_COSMOSDB_ACCOUNT: isWorkshop ? cosmosDBModule!.outputs.cosmosAccountName : ''
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: isWorkshop ? cosmosDBModule!.outputs.cosmosContainerName : ''
      AZURE_COSMOSDB_DATABASE: isWorkshop ? cosmosDBModule!.outputs.cosmosDatabaseName : ''
      AZURE_COSMOSDB_ENABLE_FEEDBACK: isWorkshop ? 'True' : ''
      // SQLDB_DATABASE: '' //sqlDBModule.outputs.sqlDbName
      // SQLDB_SERVER: '' //sqlDBModule.outputs.sqlServerName
      // SQLDB_USER_MID: '' //managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
      API_UID: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
      AZURE_AI_SEARCH_ENDPOINT: isWorkshop ? aifoundry.outputs.aiSearchTarget : ''
      AZURE_AI_SEARCH_INDEX: isWorkshop ? 'call_transcripts_index' : ''
      AZURE_AI_SEARCH_CONNECTION_NAME: isWorkshop ? aifoundry.outputs.aiSearchConnectionName : ''

      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: aifoundry.outputs.applicationInsightsConnectionString
      DUMMY_TEST: 'True'
      SOLUTION_NAME: solutionPrefix
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
    name: '${abbrs.compute.webApp}${solutionPrefix}'
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

output SOLUTION_NAME string = solutionPrefix
output RESOURCE_GROUP_NAME string = resourceGroup().name
output RESOURCE_GROUP_LOCATION string = solutionLocation
output ENVIRONMENT_NAME string = environmentName
output AZURE_CONTENT_UNDERSTANDING_LOCATION string = contentUnderstandingLocation
output AZURE_SECONDARY_LOCATION string = secondaryLocation
//output APPINSIGHTS_INSTRUMENTATIONKEY string = backend_docker.outputs.appInsightInstrumentationKey
output APPINSIGHTS_INSTRUMENTATIONKEY string = shouldDeployApp ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.appInsightInstrumentationKey : backend_csapi_docker!.outputs.appInsightInstrumentationKey) : ''
output AZURE_AI_PROJECT_CONN_STRING string = aifoundry.outputs.projectEndpoint
output AZURE_AI_AGENT_API_VERSION string = azureAiAgentApiVersion
output AZURE_AI_PROJECT_NAME string = aifoundry.outputs.aiProjectName
output AZURE_COSMOSDB_ACCOUNT string = shouldDeployApp && isWorkshop ? cosmosDBModule!.outputs.cosmosAccountName : ''
output AZURE_COSMOSDB_CONVERSATIONS_CONTAINER string = isWorkshop ? 'conversations' : ''
output AZURE_COSMOSDB_DATABASE string = isWorkshop ? 'db_conversation_history' : ''
output AZURE_COSMOSDB_ENABLE_FEEDBACK string = isWorkshop ? 'True' : ''
output AZURE_OPENAI_DEPLOYMENT_MODEL string = gptModelName
output AZURE_OPENAI_DEPLOYMENT_MODEL_CAPACITY int = gptDeploymentCapacity
output AZURE_OPENAI_ENDPOINT string = aifoundry.outputs.aiServicesTarget
output AZURE_OPENAI_MODEL_DEPLOYMENT_TYPE string = deploymentType
output AZURE_OPENAI_EMBEDDING_MODEL string = embeddingModel
// output AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY int = embeddingDeploymentCapacity
output AZURE_OPENAI_API_VERSION string = azureOpenAIApiVersion
output AZURE_OPENAI_RESOURCE string = aifoundry.outputs.aiServicesName
//output REACT_APP_LAYOUT_CONFIG string = backend_docker.outputs.reactAppLayoutConfig
output REACT_APP_LAYOUT_CONFIG string = shouldDeployApp ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.reactAppLayoutConfig : backend_csapi_docker!.outputs.reactAppLayoutConfig) : ''
output SQLDB_DATABASE string = (isWorkshop && azureEnvOnly) ? sqlDBModule!.outputs.sqlDbName : ''
output SQLDB_SERVER string = (isWorkshop && azureEnvOnly) ? sqlDBModule!.outputs.sqlServerName : ''
output SQLDB_USER_MID string = (isWorkshop && azureEnvOnly) ? managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId : ''
output API_UID string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
output USE_AI_PROJECT_CLIENT string = 'False'
output USE_CHAT_HISTORY_ENABLED string = 'True'
output DISPLAY_CHART_DEFAULT string = 'False'
output AZURE_AI_AGENT_ENDPOINT string = aifoundry.outputs.projectEndpoint
output AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME string = gptModelName
output ACR_NAME string = acrName
output AZURE_ENV_IMAGETAG string = imageTag

output AI_SERVICE_NAME string = aifoundry.outputs.aiServicesName
//output API_APP_NAME string = backend_docker.outputs.appName
output API_APP_NAME string = shouldDeployApp ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.appName : backend_csapi_docker!.outputs.appName) : ''
output API_PID string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.objectId
output MID_DISPLAY_NAME string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.name
//output API_APP_URL string = backend_docker.outputs.appUrl
output API_APP_URL string = shouldDeployApp ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.appUrl : backend_csapi_docker!.outputs.appUrl) : ''
output WEB_APP_URL string = shouldDeployApp ? frontend_docker!.outputs.appUrl : ''
output APPLICATIONINSIGHTS_CONNECTION_STRING string = aifoundry.outputs.applicationInsightsConnectionString
output AGENT_NAME_CHAT string = ''
output AGENT_NAME_TITLE string = ''
output FABRIC_SQL_DATABASE string = ''
output FABRIC_SQL_SERVER string = ''
output FABRIC_SQL_CONNECTION_STRING string = ''

output MANAGED_IDENTITY_CLIENT_ID string = managedIdentityModule.outputs.managedIdentityOutput.clientId
output AI_FOUNDRY_RESOURCE_ID string = aifoundry.outputs.aiFoundryResourceId
output BACKEND_RUNTIME_STACK string = backendRuntimeStack
output USE_CASE string = usecase
output AZURE_AI_SEARCH_ENDPOINT string = isWorkshop ? aifoundry.outputs.aiSearchTarget : ''
output AZURE_AI_SEARCH_INDEX string = isWorkshop ? 'knowledge_index' : ''
output AZURE_AI_SEARCH_NAME string = isWorkshop ? aifoundry.outputs.aiSearchName : ''
output SEARCH_DATA_FOLDER string = isWorkshop ? 'data/default/documents' : ''
output AZURE_AI_SEARCH_CONNECTION_NAME string = isWorkshop ? aifoundry.outputs.aiSearchConnectionName : ''
output AZURE_AI_SEARCH_CONNECTION_ID string = isWorkshop ? aifoundry.outputs.aiSearchConnectionId : ''
output AZURE_AI_PROJECT_ENDPOINT string = aifoundry.outputs.projectEndpoint
output IS_WORKSHOP bool = isWorkshop
output AZURE_ENV_DEPLOY_APP bool = deployApp
output AZURE_ENV_ONLY bool = azureEnvOnly
