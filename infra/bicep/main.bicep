

// ========== main.bicep ========== //
targetScope = 'resourceGroup'
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

@description('The primary title displayed in the header of the web app (bold text).')
param appTitlePrimary string = 'Contoso'

@description('The secondary title displayed in the header of the web app (lighter text).')
param appTitleSecondary string = '| Unified Data Analysis Agents'

var useChatHistoryEnabledSetting = useChatHistoryEnabled ? 'True' : 'False'

@description('Enable user access token forwarding to the API.')
param useUserAccessToken bool = false
var useUserAccessTokenSetting = useUserAccessToken ? 'True' : 'False'

// ========== Fabric Capacity Parameters ========== //

@description('Set to true to auto-create a Fabric workspace during post-provision. When false, capacity creation is skipped.')
param createFabricWorkspace bool = false

@description('Optional. Name of an existing Fabric capacity to reuse. If empty, a new capacity is auto-created when conditions are met.')
param azureFabricCapacityName string = ''

@allowed([
  'F2'
  'F4'
  'F8'
  'F16'
  'F32'
  'F64'
  'F128'
  'F256'
  'F512'
  'F1024'
  'F2048'
])
@description('Optional. SKU tier of the Fabric capacity resource.')
param fabricCapacitySku string = 'F2'

@description('Optional. Additional user/service principal object IDs to assign as Fabric Capacity admins.')
param fabricAdminMembers array = []

var useExistingFabricCapacity = !empty(azureFabricCapacityName)
var shouldCreateFabricCapacity = !azureEnvOnly && createFabricWorkspace && !useExistingFabricCapacity
var fabricCapacityResourceName = useExistingFabricCapacity ? azureFabricCapacityName : 'fc${solutionSuffix}'
var fabricCapacityDefaultAdmins = contains(deployerInfo, 'userPrincipalName')
  ? [deployerInfo.userPrincipalName]
  : [deployerInfo.objectId]
var fabricTotalAdminMembers = union(fabricCapacityDefaultAdmins, fabricAdminMembers)

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

// ========== Fabric Capacity ========== //
module fabricCapacity './modules/data/fabric-capacity.bicep' = if (shouldCreateFabricCapacity) {
  name: 'deploy-fabric-capacity'
  params: {
    name: fabricCapacityResourceName
    location: solutionLocation
    skuName: fabricCapacitySku
    adminMembers: fabricTotalAdminMembers
    tags: union(existingTags, {
      TemplateName: 'Unified Data Analysis Agents'
      CreatedBy: createdBy
    })
  }
}

// ========== Monitoring (Log Analytics + Application Insights) ========== //
// ========== Log Analytics module ========== //
module log_analytics './modules/monitoring/log-analytics.bicep' = {
  name: 'deploy_log_analytics'
  params: {
    solutionName: solutionSuffix
    solutionLocation: aiDeploymentsLocation
    existingLogAnalyticsWorkspaceId: existingLogAnalyticsWorkspaceId
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Application Insights module ========== //
module app_insights './modules/monitoring/app-insights.bicep' = {
  name: 'deploy_app_insights'
  params: {
    solutionName: solutionSuffix
    solutionLocation: aiDeploymentsLocation
    logAnalyticsWorkspaceId: log_analytics.outputs.logAnalyticsWorkspaceId
  }
  scope: resourceGroup(resourceGroup().name)
}

// ==========AI Foundry and related resources ========== //
module aifoundry './modules/ai/ai-foundry.bicep' = {
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
    azureExistingAIProjectResourceId: azureExistingAIProjectResourceId
    applicationInsightsId: app_insights.outputs.applicationInsightsId
    applicationInsightsInstrumentationKey: app_insights.outputs.applicationInsightsInstrumentationKey
    isWorkshop: isWorkshop
  }
  scope: resourceGroup(resourceGroup().name)
}

module ai_search './modules/ai/ai-search.bicep' = if (isWorkshop) {
  name: 'deploy_ai_search'
  params: {
    solutionName: solutionSuffix
    searchServiceLocation: searchServiceLocation
    isWorkshop: isWorkshop
    aiServicesName: aifoundry.outputs.aiServicesName
    aiProjectName: aifoundry.outputs.aiProjectName
    useExistingProject: !empty(azureExistingAIProjectResourceId)
    storageBlobEndpoint: isWorkshop ? storage_account!.outputs.storageBlobEndpoint : ''
    storageAccountId: isWorkshop ? storage_account!.outputs.storageAccountId : ''
    storageAccountName: isWorkshop ? storage_account!.outputs.storageAccountName : ''
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Existing Project Setup (models + connections) ========== //
var existingAIServicesName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[8] : ''
var existingAIProjectName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[10] : ''
var existingAIServiceSubscription = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[2] : subscription().subscriptionId
var existingAIServiceResourceGroup = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[4] : resourceGroup().name

module existing_project_setup './modules/ai/existing-project-setup.bicep' = if (!empty(azureExistingAIProjectResourceId)) {
  name: 'setup_existing_project'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    aiServicesName: existingAIServicesName
    aiProjectName: existingAIProjectName
    aiModelDeployments: aifoundry.outputs.aiModelDeployments
    applicationInsightsId: app_insights.outputs.applicationInsightsId
    applicationInsightsInstrumentationKey: app_insights.outputs.applicationInsightsInstrumentationKey
    aiSearchTarget: isWorkshop ? ai_search!.outputs.aiSearchTarget : ''
    aiSearchId: isWorkshop ? ai_search!.outputs.aiSearchId : ''
    aiSearchConnectionName: isWorkshop ? ai_search!.outputs.aiSearchConnectionName : ''
    storageBlobEndpoint: isWorkshop ? storage_account!.outputs.storageBlobEndpoint : ''
    storageAccountId: isWorkshop ? storage_account!.outputs.storageAccountId : ''
    storageAccountName: isWorkshop ? storage_account!.outputs.storageAccountName : ''
  }
}

// ========== Storage Account module ========== //
module storage_account './modules/data/storage-account.bicep' = if (isWorkshop) {
  name: 'deploy_storage_account'
  params: {
    solutionName: solutionSuffix
    solutionLocation: aiDeploymentsLocation
    tags: {}
  }
  scope: resourceGroup(resourceGroup().name)
}

// ========== Cosmos DB module ========== //
module cosmosDBModule './modules/data/cosmos-db.bicep' = if (isWorkshop && deployApp) {
  name: 'deploy_cosmos_db'
  params: {
    accountName: 'cosmos-${solutionSuffix}'
    solutionLocation: secondaryLocation
  }
  scope: resourceGroup(resourceGroup().name)
}

//========== SQL DB module ========== //
module sqlDBModule './modules/data/sql-db.bicep' = if(isWorkshop && azureEnvOnly) {
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

// ========== Compute image names ========== //
var backendApiImageName = 'DOCKER|${acrName}.azurecr.io/da-api:${imageTag}'
var backendCsApiImageName = 'DOCKER|${acrName}.azurecr.io/da-api-dotnet:${imageTag}'
var frontendImageName = 'DOCKER|${acrName}.azurecr.io/da-app:${imageTag}'
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
module backend_docker './modules/compute/app-service.bicep' = if (shouldDeployApp && backendRuntimeStack == 'python') {
  name: 'deploy_backend_docker'
  params: {
    solutionName: 'api-${solutionSuffix}'
    solutionLocation: solutionLocation
    appServicePlanId: hostingplan!.outputs.name
    appImageName: backendApiImageName
    appSettings: {
      APPINSIGHTS_INSTRUMENTATIONKEY: app_insights.outputs.applicationInsightsInstrumentationKey
      REACT_APP_LAYOUT_CONFIG: reactAppLayoutConfig
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
      AZURE_SQLDB_USER_MID: ''
      API_UID: ''
      AZURE_AI_SEARCH_ENDPOINT: isWorkshop ? ai_search!.outputs.aiSearchTarget : ''
      AZURE_AI_SEARCH_INDEX: isWorkshop ? 'knowledge_index' : ''
      AZURE_AI_SEARCH_CONNECTION_NAME: isWorkshop ? ai_search!.outputs.aiSearchConnectionName : ''

      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: app_insights.outputs.applicationInsightsConnectionString
      DUMMY_TEST: 'True'
      SOLUTION_NAME: solutionSuffix
      IS_WORKSHOP: isWorkshop ? 'True' : 'False'
      AZURE_ENV_ONLY: azureEnvOnly ? 'True' : 'False'
      USE_USER_ACCESS_TOKEN: useUserAccessTokenSetting
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
      API_UID: ''
      AZURE_AI_SEARCH_ENDPOINT: isWorkshop ? ai_search!.outputs.aiSearchTarget : ''
      AZURE_AI_SEARCH_INDEX: isWorkshop ? 'call_transcripts_index' : ''
      AZURE_AI_SEARCH_CONNECTION_NAME: isWorkshop ? ai_search!.outputs.aiSearchConnectionName : ''

      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: app_insights.outputs.applicationInsightsConnectionString
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

// ========== Frontend Deployment ========== //
module frontend_docker './modules/compute/app-service.bicep' = if (shouldDeployApp) {
  name: 'deploy_frontend_docker'
  params: {
    solutionName: 'app-${solutionSuffix}'
    solutionLocation: solutionLocation
    appServicePlanId: hostingplan!.outputs.name
    appImageName: frontendImageName
    appSettings: {
      APPINSIGHTS_INSTRUMENTATIONKEY: app_insights.outputs.applicationInsightsInstrumentationKey
      APP_API_BASE_URL: backendRuntimeStack == 'python' ? backend_docker!.outputs.appUrl : backend_csapi_docker!.outputs.appUrl
      CHAT_LANDING_TEXT: landingText
      IS_WORKSHOP: isWorkshop ? 'True' : 'False'
      APP_TITLE_PRIMARY: appTitlePrimary
      APP_TITLE_SECONDARY: appTitleSecondary
    }
  }
  scope: resourceGroup(resourceGroup().name)
}

module role_assignments './modules/identity/role-assignments.bicep' = {
  name: 'deploy_role_assignments'
  params: {
    solutionName: solutionSuffix
    isWorkshop: isWorkshop
    shouldDeployApp: shouldDeployApp
    azureExistingAIProjectResourceId: azureExistingAIProjectResourceId
    aiServicesName: aifoundry.outputs.aiServicesName
    aiSearchName: isWorkshop ? ai_search!.outputs.aiSearchName : ''
    storageAccountName: isWorkshop ? storage_account!.outputs.storageAccountName : ''
    aiProjectPrincipalId: empty(azureExistingAIProjectResourceId) ? aifoundry.outputs.aiProjectPrincipalId : ''
    searchPrincipalId: isWorkshop ? ai_search!.outputs.searchPrincipalId : ''
    deployingUserPrincipalId: deployingUserPrincipalId
    deployingUserPrincipalType: deployingUserPrincipalType
    backendAppPrincipalId: shouldDeployApp && backendRuntimeStack == 'python' ? backend_docker!.outputs.identityPrincipalId : ''
    backendCsApiPrincipalId: shouldDeployApp && backendRuntimeStack == 'dotnet' ? backend_csapi_docker!.outputs.identityPrincipalId : ''
    cosmosAccountName: shouldDeployApp && isWorkshop ? cosmosDBModule!.outputs.cosmosAccountName : ''
    existingAiProjectPrincipalId: !empty(azureExistingAIProjectResourceId) ? existing_project_setup!.outputs.aiProjectPrincipalId : ''
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
output AZURE_SQLDB_USER_MID string = ''

@description('Backend API managed identity client ID (system-assigned, resolved at runtime)')
output API_UID string = ''

@description('Azure AI Agent service endpoint URL')
output AZURE_AI_AGENT_ENDPOINT string = aifoundry.outputs.projectEndpoint

@description('Model deployment name used by Azure AI Agent')
output AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME string = gptModelName

@description('Backend API App Service name')
output API_APP_NAME string = shouldDeployApp ? (backendRuntimeStack == 'python' ? 'api-${solutionSuffix}' : 'api-cs-${solutionSuffix}') : ''

@description('Backend API managed identity object/principal ID (system-assigned)')
output API_PID string = shouldDeployApp ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.identityPrincipalId : backend_csapi_docker!.outputs.identityPrincipalId) : ''

@description('Backend API App Service name')
output MID_DISPLAY_NAME string = shouldDeployApp ? (backendRuntimeStack == 'python' ? 'api-${solutionSuffix}' : 'api-cs-${solutionSuffix}') : ''

@description('Frontend web application URL')
output WEB_APP_URL string = shouldDeployApp ? frontend_docker!.outputs.appUrl : ''

@description('Deployed use case identifier (e.g., Retail-sales-analysis)')
output USE_CASE string = usecase

@description('Azure AI Search service endpoint URL')
output AZURE_AI_SEARCH_ENDPOINT string = isWorkshop ? ai_search!.outputs.aiSearchTarget : ''

@description('Azure AI Search index name for document search')
output AZURE_AI_SEARCH_INDEX string = isWorkshop ? 'knowledge_index' : ''

@description('Azure AI Search service resource name')
output AZURE_AI_SEARCH_NAME string = isWorkshop ? ai_search!.outputs.aiSearchName : ''

@description('Local path to documents folder for search indexing')
output SEARCH_DATA_FOLDER string = isWorkshop ? 'data/default/documents' : ''

@description('AI Foundry connection name for Azure AI Search')
output AZURE_AI_SEARCH_CONNECTION_NAME string = isWorkshop ? ai_search!.outputs.aiSearchConnectionName : ''

@description('AI Foundry connection ID for Azure AI Search')
output AZURE_AI_SEARCH_CONNECTION_ID string = isWorkshop ? (!empty(azureExistingAIProjectResourceId) ? existing_project_setup!.outputs.aiSearchConnectionId : ai_search!.outputs.aiSearchConnectionId) : ''

@description('Azure AI Foundry project endpoint URL')
output AZURE_AI_PROJECT_ENDPOINT string = aifoundry.outputs.projectEndpoint

@description('Azure AI Foundry resource ID for role assignments')
output AI_FOUNDRY_RESOURCE_ID string = aifoundry.outputs.aiFoundryResourceId

@description('Azure AI Foundry project name')
output AZURE_AI_PROJECT_NAME string = aifoundry.outputs.aiProjectName

@description('Azure AI Services resource name')
output AI_SERVICE_NAME string = aifoundry.outputs.aiServicesName

@description('Azure AI Foundry project managed identity principal ID')
output FOUNDRY_PROJECT_PID string = !empty(azureExistingAIProjectResourceId) ? existing_project_setup!.outputs.aiProjectPrincipalId : aifoundry.outputs.aiProjectPrincipalId

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

@description('Flag indicating whether user access token forwarding is enabled')
output USE_USER_ACCESS_TOKEN string = useUserAccessTokenSetting

@description('The name of the Fabric capacity resource.')
output AZURE_FABRIC_CAPACITY_NAME string = createFabricWorkspace ? fabricCapacityResourceName : ''

@description('The identities assigned as Fabric Capacity Admin members.')
output FABRIC_ADMIN_MEMBERS array = shouldCreateFabricCapacity ? fabricTotalAdminMembers : []

@description('The unique solution suffix of the deployed resources.')
output SOLUTION_SUFFIX string = solutionSuffix
