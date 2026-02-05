// Creates Azure dependent resources for Azure AI studio
param solutionName string
param solutionLocation string
param deploymentType string
param gptModelName string
param gptModelVersion string
// param azureOpenAIApiVersion string
param gptDeploymentCapacity int
param embeddingModel string
param embeddingDeploymentCapacity int
param managedIdentityObjectId string=''
param existingLogAnalyticsWorkspaceId string = ''
param azureExistingAIProjectResourceId string = ''
param deployingUserPrincipalId string = ''
param tags object = {}
param isWorkShopDeployment bool = false

var abbrs = loadJsonContent('./abbreviations.json')
var aiServicesName = '${abbrs.ai.aiServices}${solutionName}'
var workspaceName = '${abbrs.managementGovernance.logAnalyticsWorkspace}${solutionName}'
var applicationInsightsName = '${abbrs.managementGovernance.applicationInsights}${solutionName}'
var location = solutionLocation //'eastus2'
var aiProjectName = '${abbrs.ai.aiFoundryProject}${solutionName}'
var aiSearchName = '${abbrs.ai.aiSearch}${solutionName}'
var storageName = '${abbrs.storage.storageAccount}${toLower(replace(solutionName, '-', ''))}'
var aiSearchConnectionName = 'myVectorStoreProjectConnectionName-${solutionName}'

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
], isWorkShopDeployment ? [
  {
    name: embeddingModel
    model: embeddingModel
    sku: {
      name: 'GlobalStandard'
      capacity: embeddingDeploymentCapacity
    }
    raiPolicyName: 'Microsoft.Default'
  }
] : [])

var useExisting = !empty(existingLogAnalyticsWorkspaceId)
var existingLawSubscription = useExisting ? split(existingLogAnalyticsWorkspaceId, '/')[2] : ''
var existingLawResourceGroup = useExisting ? split(existingLogAnalyticsWorkspaceId, '/')[4] : ''
var existingLawName = useExisting ? split(existingLogAnalyticsWorkspaceId, '/')[8] : ''

var existingOpenAIEndpoint = !empty(azureExistingAIProjectResourceId) ? format('https://{0}.openai.azure.com/', split(azureExistingAIProjectResourceId, '/')[8]) : ''
var existingProjEndpoint = !empty(azureExistingAIProjectResourceId) ? format('https://{0}.services.ai.azure.com/api/projects/{1}', split(azureExistingAIProjectResourceId, '/')[8], split(azureExistingAIProjectResourceId, '/')[10]) : ''
var existingAIServicesName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[8] : ''
var existingAIProjectName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[10] : ''
var existingAIServiceSubscription = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[2] : subscription().subscriptionId
var existingAIServiceResourceGroup = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[4] : resourceGroup().name

resource existingLogAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = if (useExisting) {
  name: existingLawName
  scope: resourceGroup(existingLawSubscription ,existingLawResourceGroup)
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (!useExisting){
  name: workspaceName
  location: location
  tags: {}
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Disabled'
    WorkspaceResourceId: useExisting ? existingLogAnalyticsWorkspace.id : logAnalytics.id
  }
}

// Storage Account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = if(isWorkShopDeployment) {
  name: storageName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

// Blob Service
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = if(isWorkShopDeployment) {
  parent: storageAccount
  name: 'default'
}

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' =  if (empty(azureExistingAIProjectResourceId)) {
  name: aiServicesName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: aiServicesName
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

module existing_aiServicesModule 'existing_foundry_project.bicep' = if (!empty(azureExistingAIProjectResourceId)) {
  name: 'existing_foundry_project'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    aiServicesName: existingAIServicesName
    aiProjectName: existingAIProjectName
  }
}

@batchSize(1)
resource aiServicesDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = [for aiModeldeployment in aiModelDeployments: if (empty(azureExistingAIProjectResourceId)) {
  parent: aiServices //aiServices_m
  name: aiModeldeployment.name
  properties: {
    model: {
      format: 'OpenAI'
      name: aiModeldeployment.model
    }
    raiPolicyName: aiModeldeployment.raiPolicyName
  }
  sku:{
    name: aiModeldeployment.sku.name
    capacity: aiModeldeployment.sku.capacity
  }
}]

resource aiSearch 'Microsoft.Search/searchServices@2024-06-01-preview' = if(isWorkShopDeployment) {
  name: aiSearchName
  location: solutionLocation
  sku: {
    name: 'basic'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    networkRuleSet: {
      ipRules: []
    }
    encryptionWithCmk: {
      enforcement: 'Unspecified'
    }
    disableLocalAuth: true
    semanticSearch: 'free'
  }
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' =  if (empty(azureExistingAIProjectResourceId)) {
  parent: aiServices
  name: aiProjectName
  location: solutionLocation
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

// Connect AI Search to Project
resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = if (empty(azureExistingAIProjectResourceId) && isWorkShopDeployment) {
  parent: aiProject
  name: 'search-connection'
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${aiSearch.name}.search.windows.net'
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: aiSearch.id
    }
  }
}

// Connect Application Insights to Project
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = if (empty(azureExistingAIProjectResourceId)) {
  parent: aiProject
  name: applicationInsightsName
  properties: {
    category: 'AppInsights'
    target: applicationInsights.id
    authType: 'ApiKey'
    isSharedToAll: true
    isDefault: true
    credentials: {
      key: applicationInsights.properties.InstrumentationKey
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: applicationInsights.id
    }
  }
}

// Role Definitions

resource azureAIUser 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Azure AI User
}

resource cognitiveServicesOpenAIUser 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
}

resource searchIndexDataReader 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
}

resource searchServiceContributor 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
}

resource searchIndexDataContributor 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
}

resource assignFoundryRoleToMI 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId))  {
  name: guid(resourceGroup().id, aiServices.id, azureAIUser.id)
  scope: aiServices
  properties: {
    principalId: managedIdentityObjectId
    roleDefinitionId: azureAIUser.id
    principalType: 'ServicePrincipal'
  }
}

module assignFoundryRoleToMIExisting 'deploy_foundry_role_assignment.bicep' = if (!empty(azureExistingAIProjectResourceId)) {
  name: 'assignFoundryRoleToMI'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    roleDefinitionId: azureAIUser.id
    roleAssignmentName: guid(resourceGroup().id, managedIdentityObjectId, azureAIUser.id, 'foundry')
    aiServicesName: existingAIServicesName
    aiProjectName: existingAIProjectName
    principalId: managedIdentityObjectId
    aiLocation: existing_aiServicesModule.outputs.location
    aiKind: existing_aiServicesModule.outputs.kind
    aiSkuName: existing_aiServicesModule.outputs.skuName
    customSubDomainName: existing_aiServicesModule.outputs.customSubDomainName
    publicNetworkAccess: existing_aiServicesModule.outputs.publicNetworkAccess
    enableSystemAssignedIdentity: true
    defaultNetworkAction: existing_aiServicesModule.outputs.defaultNetworkAction
    vnetRules: existing_aiServicesModule.outputs.vnetRules
    ipRules: existing_aiServicesModule.outputs.ipRules
    aiModelDeployments: aiModelDeployments // Pass the model deployments to the module if model not already deployed
  }
}

resource assignOpenAIRoleToAISearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && isWorkShopDeployment)  {
  name: guid(resourceGroup().id, aiServices.id, cognitiveServicesOpenAIUser.id)
  scope: aiServices
  properties: {
    principalId: aiSearch.identity.principalId
    roleDefinitionId: cognitiveServicesOpenAIUser.id
    principalType: 'ServicePrincipal'
  }
}

module existingOpenAiProject 'deploy_foundry_role_assignment.bicep' = if (!empty(azureExistingAIProjectResourceId) && isWorkShopDeployment) {
  name: 'assignOpenAIRoleToAISearchExisting'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    roleDefinitionId: cognitiveServicesOpenAIUser.id
    roleAssignmentName: guid(resourceGroup().id, aiSearch.id, cognitiveServicesOpenAIUser.id, 'openai-foundry')
    aiServicesName: existingAIServicesName
    aiProjectName: existingAIProjectName
    principalId: aiSearch.identity.principalId
    enableSystemAssignedIdentity: true
  }
}

resource assignSearchIndexDataReaderToAiProject 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && isWorkShopDeployment) {
  name: guid(resourceGroup().id, aiProject.id, searchIndexDataReader.id)
  scope: aiSearch
  properties: {
    principalId: aiProject.identity.principalId
    roleDefinitionId: searchIndexDataReader.id
    principalType: 'ServicePrincipal'
  }
}

resource assignSearchIndexDataReaderToExistingAiProject 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(azureExistingAIProjectResourceId) && isWorkShopDeployment) {
  name: guid(resourceGroup().id, existingAIProjectName, searchIndexDataReader.id, 'Existing')
  scope: aiSearch
  properties: {
    principalId: existingOpenAiProject.outputs.aiProjectPrincipalId
    roleDefinitionId: searchIndexDataReader.id
    principalType: 'ServicePrincipal'
  }
}

resource assignSearchServiceContributorToAiProject 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && isWorkShopDeployment) {
  name: guid(resourceGroup().id, aiProject.id, searchServiceContributor.id)
  scope: aiSearch
  properties: {
    principalId: aiProject.identity.principalId
    roleDefinitionId: searchServiceContributor.id
    principalType: 'ServicePrincipal'
  }
}

resource assignSearchServiceContributorToExistingAiProject 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(azureExistingAIProjectResourceId) && isWorkShopDeployment) {
  name: guid(resourceGroup().id, existingAIProjectName, searchServiceContributor.id, 'Existing')
  scope: aiSearch
  properties: {
    principalId: existingOpenAiProject.outputs.aiProjectPrincipalId
    roleDefinitionId: searchServiceContributor.id
    principalType: 'ServicePrincipal'
  }
}

resource assignSearchIndexDataContributorToMI 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && isWorkShopDeployment) {
  name: guid(resourceGroup().id, aiProject.id, searchIndexDataContributor.id)
  scope: aiSearch
  properties: {
    principalId: managedIdentityObjectId
    roleDefinitionId: searchIndexDataContributor.id
    principalType: 'ServicePrincipal'
  }
}

// Storage Role Definitions
resource storageBlobDataContributor 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
}

resource storageBlobDataReader 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1' // Storage Blob Data Reader
}

// Grant AI Project identity access to Storage
resource projectStorageBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && isWorkShopDeployment) {
  scope: storageAccount
  name: guid(storageAccount.id, aiProject.id, storageBlobDataContributor.id)
  properties: {
    principalId: aiProject.identity.principalId
    roleDefinitionId: storageBlobDataContributor.id
    principalType: 'ServicePrincipal'
  }
}

resource existingProjectStorageBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(azureExistingAIProjectResourceId) && isWorkShopDeployment) {
  scope: storageAccount
  name: guid(storageAccount.id, existingAIProjectName, storageBlobDataContributor.id)
  properties: {
    principalId: existingOpenAiProject.outputs.aiProjectPrincipalId
    roleDefinitionId: storageBlobDataContributor.id
    principalType: 'ServicePrincipal'
  }
}

resource projectStorageBlobReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && isWorkShopDeployment) {
  scope: storageAccount
  name: guid(storageAccount.id, aiProject.id, storageBlobDataReader.id)
  properties: {
    principalId: aiProject.identity.principalId
    roleDefinitionId: storageBlobDataReader.id
    principalType: 'ServicePrincipal'
  }
}

resource existingProjectStorageBlobReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(azureExistingAIProjectResourceId) && isWorkShopDeployment) {
  scope: storageAccount
  name: guid(storageAccount.id, existingAIProjectName, storageBlobDataReader.id)
  properties: {
    principalId: existingOpenAiProject.outputs.aiProjectPrincipalId
    roleDefinitionId: storageBlobDataReader.id
    principalType: 'ServicePrincipal'
  }
}

// Grant AI Search identity access to Storage (for indexers)
resource searchStorageBlobDataReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isWorkShopDeployment) {
  scope: storageAccount
  name: guid(storageAccount.id, aiSearch.id, storageBlobDataReader.id)
  properties: {
    principalId: aiSearch.identity.principalId
    roleDefinitionId: storageBlobDataReader.id
    principalType: 'ServicePrincipal'
  }
}

// Default container for AI Foundry
resource defaultContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = if (isWorkShopDeployment) {
  parent: blobService
  name: 'default'
  properties: {
    publicAccess: 'None'
  }
}

// Connect Storage to Project
resource storageConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = if (isWorkShopDeployment) {
  parent: aiProject
  name: 'storage-connection'
  properties: {
    category: 'AzureBlob'
    target: storageAccount.properties.primaryEndpoints.blob
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ResourceId: storageAccount.id
      AccountName: storageAccount.name
      ContainerName: 'default'
    }
  }
  dependsOn: [defaultContainer]
}

// Role Definitions for deploying user
resource cognitiveServicesUser 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User
}

// Grant deploying user access to AI Services
resource userAIServicesAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId)) {
  scope: aiServices
  name: guid(aiServices.id, deployingUserPrincipalId, cognitiveServicesUser.id)
  properties: {
    principalId: deployingUserPrincipalId
    roleDefinitionId: cognitiveServicesUser.id
    principalType: 'User'
  }
}

// Grant deploying user Azure AI User role on AI Services
resource userAzureAIAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId)) {
  scope: aiServices
  name: guid(aiServices.id, deployingUserPrincipalId, azureAIUser.id)
  properties: {
    principalId: deployingUserPrincipalId
    roleDefinitionId: azureAIUser.id
    principalType: 'User'
  }
}

// Grant deploying user access to AI Search
resource userSearchIndexContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isWorkShopDeployment) {
  scope: aiSearch
  name: guid(aiSearch.id, deployingUserPrincipalId, searchIndexDataContributor.id)
  properties: {
    principalId: deployingUserPrincipalId
    roleDefinitionId: searchIndexDataContributor.id
    principalType: 'User'
  }
}

resource userSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isWorkShopDeployment) {
  scope: aiSearch
  name: guid(aiSearch.id, deployingUserPrincipalId, searchServiceContributor.id)
  properties: {
    principalId: deployingUserPrincipalId
    roleDefinitionId: searchServiceContributor.id
    principalType: 'User'
  }
}

// Grant deploying user access to Storage
resource userStorageBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isWorkShopDeployment) {
  scope: storageAccount
  name: guid(storageAccount.id, deployingUserPrincipalId, storageBlobDataContributor.id)
  properties: {
    principalId: deployingUserPrincipalId
    roleDefinitionId: storageBlobDataContributor.id
    principalType: 'User'
  }
}

output aiServicesTarget string = !empty(existingOpenAIEndpoint) ? existingOpenAIEndpoint : aiServices.properties.endpoints['OpenAI Language Model Instance API'] //aiServices_m.properties.endpoint
output aiServicesName string = !empty(existingAIServicesName) ? existingAIServicesName : aiServicesName

output aiSearchName string = isWorkShopDeployment ? aiSearchName : ''
output aiSearchId string = isWorkShopDeployment ? aiSearch.id : ''
output aiSearchTarget string = isWorkShopDeployment ? 'https://${aiSearch.name}.search.windows.net' : ''
output aiSearchService string = isWorkShopDeployment ? aiSearch.name : ''
output aiProjectName string = !empty(existingAIProjectName) ? existingAIProjectName : aiProject.name
output aiSearchConnectionName string = isWorkShopDeployment ? aiSearchConnectionName : ''

output applicationInsightsId string = applicationInsights.id
output logAnalyticsWorkspaceResourceName string = useExisting ? existingLogAnalyticsWorkspace.name : logAnalytics.name
output logAnalyticsWorkspaceResourceGroup string = useExisting ? existingLawResourceGroup : resourceGroup().name
output logAnalyticsWorkspaceSubscription string = useExisting ? existingLawSubscription : subscription().subscriptionId

output projectEndpoint string = !empty(existingProjEndpoint) ? existingProjEndpoint : aiProject.properties.endpoints['AI Foundry API']
output applicationInsightsConnectionString string = applicationInsights.properties.ConnectionString
output aiFoundryResourceId string = !empty(azureExistingAIProjectResourceId) ? azureExistingAIProjectResourceId : aiServices.id
