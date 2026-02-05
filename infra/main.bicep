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
param backendRuntimeStack string

@minLength(1)
@description('Industry use case for deployment:')
@allowed([
  'Retail-sales-analysis'
  'Insurance-improve-customer-meetings'
])
param usecase string 

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

@description('Optional. The tags to apply to all deployed Azure resources.')
param tags resourceInput<'Microsoft.Resources/resourceGroups@2025-04-01'>.tags = {}

@minLength(1)
@description('Name of the Text Embedding model to deploy:')
@allowed([
  'text-embedding-ada-002'
])
param embeddingModel string = 'text-embedding-ada-002'

@minValue(10)
@description('Capacity of the Embedding Model deployment')
param embeddingDeploymentCapacity int = 80

param imageTag string = 'latest_v2'

@description('Deploy the application components (Cosmos DB, API, Frontend). Set to true to deploy the app.')
param deployApp bool = false

param isWorkShopDeployment bool = false

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
      // 'OpenAI.GlobalStandard.text-embedding-ada-002,80'
    ]
  }
})
@description('Location for AI Foundry deployment. This is the location where the AI Foundry resources will be deployed.')
param aiDeploymentsLocation string

var solutionPrefix = 'da${padLeft(take(uniqueId, 12), 12, '0')}'

@description('Name of the Azure Container Registry')
param acrName string = isWorkShopDeployment ? 'dataagentscontainerregworkshop' : 'dataagentscontainerreg'

//Get the current deployer's information
var deployerInfo = deployer()
var deployingUserPrincipalId = deployerInfo.objectId

// ========== Resource Group Tag ========== //
resource resourceGroupTags 'Microsoft.Resources/tags@2021-04-01' = {
  name: 'default'
  properties: {
    tags: union(
      reference(
        resourceGroup().id, 
        '2021-04-01', 
        'Full'
      ).tags ?? {},
      {
        TemplateName: 'Unified Data Analysis Agents'
        CreatedBy: createdBy
      },
      tags
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
    isWorkShopDeployment: isWorkShopDeployment
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
module cosmosDBModule 'deploy_cosmos_db.bicep' = if (isWorkShopDeployment && deployApp) {
  name: 'deploy_cosmos_db'
  params: {
    accountName: '${abbrs.databases.cosmosDBDatabase}${solutionPrefix}'
    solutionLocation: secondaryLocation
    // keyVaultName: kvault.outputs.keyvaultName
  }
  scope: resourceGroup(resourceGroup().name)
}

// //========== SQL DB module ========== //
// module sqlDBModule 'deploy_sql_db.bicep' = {
//   name: 'deploy_sql_db'
//   params: {
//     serverName: '${abbrs.databases.sqlDatabaseServer}${solutionPrefix}'
//     sqlDBName: '${abbrs.databases.sqlDatabase}${solutionPrefix}'
//     solutionLocation: secondaryLocation
//     keyVaultName: kvault.outputs.keyvaultName
//     managedIdentityName: managedIdentityModule.outputs.managedIdentityOutput.name
//     sqlUsers: [
//       {
//         principalId: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
//         principalName: managedIdentityModule.outputs.managedIdentityBackendAppOutput.name
//         databaseRoles: ['db_datareader', 'db_datawriter']
//       }
//     ]
//   }
//   scope: resourceGroup(resourceGroup().name)
// }

module hostingplan 'deploy_app_service_plan.bicep' = if (deployApp) {
  name: 'deploy_app_service_plan'
  params: {
    solutionLocation: solutionLocation
    HostingPlanName: '${abbrs.compute.appServicePlan}${solutionPrefix}'
  }
}

// ========== Backend Deployment (Python) ========== //
module backend_docker 'deploy_backend_docker.bicep' = if (deployApp && backendRuntimeStack == 'python') {
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
    enableCosmosDb: deployApp && isWorkShopDeployment
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
      AZURE_COSMOSDB_ACCOUNT: isWorkShopDeployment ? cosmosDBModule!.outputs.cosmosAccountName : ''
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: isWorkShopDeployment ? cosmosDBModule!.outputs.cosmosContainerName : ''
      AZURE_COSMOSDB_DATABASE: isWorkShopDeployment? cosmosDBModule!.outputs.cosmosDatabaseName : ''
      AZURE_COSMOSDB_ENABLE_FEEDBACK: isWorkShopDeployment ? 'True' : ''
      // SQLDB_DATABASE: '' //sqlDBModule.outputs.sqlDbName
      // SQLDB_SERVER: '' //sqlDBModule.outputs.sqlServerName
      // SQLDB_USER_MID: '' //managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
      API_UID: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
      // AZURE_AI_SEARCH_ENDPOINT: '' //aifoundry.outputs.aiSearchTarget
      // AZURE_AI_SEARCH_INDEX: '' //'call_transcripts_index'
      // AZURE_AI_SEARCH_CONNECTION_NAME: '' //aifoundry.outputs.aiSearchConnectionName

      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: aifoundry.outputs.applicationInsightsConnectionString
      DUMMY_TEST: 'True'
      SOLUTION_NAME: solutionPrefix
      IS_WORKSHOP_DEPLOYMENT: isWorkShopDeployment ? 'True' : 'False'
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
module backend_csapi_docker 'deploy_backend_csapi_docker.bicep' = if (deployApp && backendRuntimeStack == 'dotnet') {
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
      AZURE_COSMOSDB_ACCOUNT: isWorkShopDeployment ? cosmosDBModule!.outputs.cosmosAccountName : ''
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: isWorkShopDeployment ? cosmosDBModule!.outputs.cosmosContainerName : ''
      AZURE_COSMOSDB_DATABASE: isWorkShopDeployment ? cosmosDBModule!.outputs.cosmosDatabaseName : ''
      AZURE_COSMOSDB_ENABLE_FEEDBACK: isWorkShopDeployment ? 'True' : ''
      // SQLDB_DATABASE: '' //sqlDBModule.outputs.sqlDbName
      // SQLDB_SERVER: '' //sqlDBModule.outputs.sqlServerName
      // SQLDB_USER_MID: '' //managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
      API_UID: managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
      // AZURE_AI_SEARCH_ENDPOINT: '' //aifoundry.outputs.aiSearchTarget
      // AZURE_AI_SEARCH_INDEX: '' //'call_transcripts_index'
      // AZURE_AI_SEARCH_CONNECTION_NAME: '' //aifoundry.outputs.aiSearchConnectionName

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

module frontend_docker 'deploy_frontend_docker.bicep' = if (deployApp) {
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
      IS_WORKSHOP_DEPLOYMENT: isWorkShopDeployment ? 'True' : 'False'
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
output APPINSIGHTS_INSTRUMENTATIONKEY string = deployApp ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.appInsightInstrumentationKey : backend_csapi_docker!.outputs.appInsightInstrumentationKey) : ''
output AZURE_AI_PROJECT_CONN_STRING string = aifoundry.outputs.projectEndpoint
output AZURE_AI_AGENT_API_VERSION string = azureAiAgentApiVersion
output AZURE_AI_PROJECT_NAME string = aifoundry.outputs.aiProjectName
output AZURE_COSMOSDB_ACCOUNT string = deployApp && isWorkShopDeployment ? cosmosDBModule!.outputs.cosmosAccountName : ''
output AZURE_COSMOSDB_CONVERSATIONS_CONTAINER string = isWorkShopDeployment ? 'conversations' : ''
output AZURE_COSMOSDB_DATABASE string = isWorkShopDeployment ? 'db_conversation_history' : ''
output AZURE_COSMOSDB_ENABLE_FEEDBACK string = isWorkShopDeployment ? 'True' : ''
output AZURE_OPENAI_DEPLOYMENT_MODEL string = gptModelName
output AZURE_OPENAI_DEPLOYMENT_MODEL_CAPACITY int = gptDeploymentCapacity
output AZURE_OPENAI_ENDPOINT string = aifoundry.outputs.aiServicesTarget
output AZURE_OPENAI_MODEL_DEPLOYMENT_TYPE string = deploymentType
// output AZURE_OPENAI_EMBEDDING_MODEL string = embeddingModel
// output AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY int = embeddingDeploymentCapacity
output AZURE_OPENAI_API_VERSION string = azureOpenAIApiVersion
output AZURE_OPENAI_RESOURCE string = aifoundry.outputs.aiServicesName
//output REACT_APP_LAYOUT_CONFIG string = backend_docker.outputs.reactAppLayoutConfig
output REACT_APP_LAYOUT_CONFIG string = deployApp ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.reactAppLayoutConfig : backend_csapi_docker!.outputs.reactAppLayoutConfig) : ''
// output SQLDB_DATABASE string = sqlDBModule.outputs.sqlDbName
// output SQLDB_SERVER string = sqlDBModule.outputs.sqlServerName
// output SQLDB_USER_MID string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.clientId
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
output API_APP_NAME string = deployApp ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.appName : backend_csapi_docker!.outputs.appName) : ''
output API_PID string = managedIdentityModule.outputs.managedIdentityBackendAppOutput.objectId

//output API_APP_URL string = backend_docker.outputs.appUrl
output API_APP_URL string = deployApp ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.appUrl : backend_csapi_docker!.outputs.appUrl) : ''
output WEB_APP_URL string = deployApp ? frontend_docker!.outputs.appUrl : ''
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
output AZURE_AI_SEARCH_ENDPOINT string = aifoundry.outputs.aiSearchTarget
output AZURE_AI_PROJECT_ENDPOINT string = aifoundry.outputs.projectEndpoint
