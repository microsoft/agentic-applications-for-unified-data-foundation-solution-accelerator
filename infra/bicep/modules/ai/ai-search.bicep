targetScope = 'resourceGroup'

@minLength(3)
@description('The name of the solution, used as a base for naming all resources.')
param solutionName string

@description('The Azure region where the search service will be deployed.')
param searchServiceLocation string = resourceGroup().location

@description('When true, deploys additional resources for workshop scenarios including AI Search and Storage.')
param isWorkshop bool = false

@description('The name of the AI Services account that owns the AI project.')
param aiServicesName string

@description('The name of the AI Foundry project.')
param aiProjectName string

@description('The resource ID of an existing Azure AI Foundry project. If provided, the existing project will be used instead of creating a new one.')
param azureExistingAIProjectResourceId string = ''

@description('The primary blob endpoint of the storage account (from data/storage-account module).')
param storageBlobEndpoint string = ''

@description('The resource ID of the storage account (from data/storage-account module).')
param storageAccountId string = ''

@description('The name of the storage account (from data/storage-account module).')
param storageAccountName string = ''

var aiSearchName = 'srch-${solutionName}'
var aiSearchConnectionName = 'search-connection-${solutionName}'

var existingAIServicesName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[8] : ''
var existingAIProjectName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[10] : ''
var existingAIServiceSubscription = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[2] : subscription().subscriptionId
var existingAIServiceResourceGroup = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[4] : resourceGroup().name

resource aiSearch 'Microsoft.Search/searchServices@2025-05-01' = if (isWorkshop) {
  name: aiSearchName
  location: searchServiceLocation
  sku: {
    name: 'standard'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'Default'
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

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = if (empty(azureExistingAIProjectResourceId)) {
  name: aiServicesName
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' existing = if (empty(azureExistingAIProjectResourceId)) {
  parent: aiServices
  name: aiProjectName
}

resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (empty(azureExistingAIProjectResourceId) && isWorkshop) {
  parent: aiProject
  name: aiSearchConnectionName
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

module existingProjectConnections 'ai-project-connections.bicep' = if (!empty(azureExistingAIProjectResourceId) && isWorkshop) {
  name: 'deploy_existing_project_connections'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    aiServicesName: existingAIServicesName
    aiProjectName: existingAIProjectName
    aiSearchConnectionName: aiSearchConnectionName
    aiSearchTarget: 'https://${aiSearch.name}.search.windows.net'
    aiSearchId: aiSearch.id
    storageBlobTarget: storageBlobEndpoint
    storageAccountId: storageAccountId
    storageAccountName: storageAccountName
  }
}

resource storageConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (empty(azureExistingAIProjectResourceId) && isWorkshop) {
  parent: aiProject
  name: 'storage-connection'
  properties: {
    category: 'AzureBlob'
    target: storageBlobEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ResourceId: storageAccountId
      AccountName: storageAccountName
      ContainerName: 'default'
    }
  }
}

@description('The name of the AI Search service.')
output aiSearchName string = isWorkshop ? aiSearchName : ''

@description('The resource ID of the AI Search service.')
output aiSearchId string = isWorkshop ? aiSearch.id : ''

@description('The endpoint URL of the AI Search service.')
output aiSearchTarget string = isWorkshop ? 'https://${aiSearch.name}.search.windows.net' : ''

@description('The name of the AI Search service resource.')
output aiSearchService string = isWorkshop ? aiSearch.name : ''

@description('The name of the AI Search connection.')
output aiSearchConnectionName string = isWorkshop ? aiSearchConnectionName : ''

@description('The resource ID of the AI Search connection.')
output aiSearchConnectionId string = isWorkshop
  ? (empty(azureExistingAIProjectResourceId) ? searchConnection.id : existingProjectConnections.outputs.aiSearchConnectionId)
  : ''

@description('The principal ID of the AI Search system-assigned managed identity.')
output searchPrincipalId string = isWorkshop ? aiSearch.identity.principalId : ''
