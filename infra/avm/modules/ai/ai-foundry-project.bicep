// ============================================================================
// Module: AI Foundry Project
// Description: AI Foundry Project under an AI Services account
// Includes: Project creation, connections (Search, Storage, AppInsights)
// ============================================================================

@description('Name of the AI Foundry project.')
param projectName string

@description('Name of the parent AI Services account.')
param aiServicesAccountName string

@description('Azure region for the project.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Whether to create connections to AI Search.')
param enableSearchConnection bool = false

@description('AI Search service name (required if enableSearchConnection is true).')
param aiSearchName string = ''

@description('AI Search connection name.')
param aiSearchConnectionName string = ''

@description('Whether to create connection to Storage.')
param enableStorageConnection bool = false

@description('Storage account name (required if enableStorageConnection is true).')
param storageAccountName string = ''

@description('Storage blob endpoint.')
param storageBlobEndpoint string = ''

@description('Storage account resource ID.')
param storageAccountResourceId string = ''

@description('Application Insights name for tracing connection.')
param applicationInsightsName string = ''

@description('Application Insights resource ID.')
param applicationInsightsResourceId string = ''

@description('Application Insights instrumentation key.')
param applicationInsightsInstrumentationKey string = ''

// ============================================================================
// Parent reference
// ============================================================================
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: aiServicesAccountName
}

// ============================================================================
// AI Foundry Project
// ============================================================================
resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: aiServices
  name: projectName
  location: location
  tags: tags
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

// ============================================================================
// Connections
// ============================================================================

// AI Search Connection
resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = if (enableSearchConnection && !empty(aiSearchName)) {
  parent: aiProject
  name: aiSearchConnectionName
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${aiSearchName}.search.windows.net'
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: resourceId('Microsoft.Search/searchServices', aiSearchName)
    }
  }
}

// Storage Connection
resource storageConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = if (enableStorageConnection && !empty(storageAccountName)) {
  parent: aiProject
  name: 'storage-connection'
  properties: {
    category: 'AzureBlob'
    target: storageBlobEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: storageAccountResourceId
      AccountName: storageAccountName
      ContainerName: 'default'
    }
  }
}

// Application Insights Connection
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = if (!empty(applicationInsightsResourceId)) {
  parent: aiProject
  name: applicationInsightsName
  properties: {
    category: 'AppInsights'
    target: applicationInsightsResourceId
    authType: 'ApiKey'
    isSharedToAll: true
    isDefault: true
    credentials: {
      key: applicationInsightsInstrumentationKey
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: applicationInsightsResourceId
    }
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the AI Foundry project.')
output resourceId string = aiProject.id

@description('Name of the AI Foundry project.')
output name string = aiProject.name

@description('AI Foundry project endpoint.')
output endpoint string = aiProject.properties.endpoints['AI Foundry API']

@description('System-assigned identity principal ID of the project.')
output identityPrincipalId string = aiProject.identity.principalId

@description('AI Search connection name.')
output searchConnectionName string = enableSearchConnection ? aiSearchConnectionName : ''

@description('AI Search connection ID.')
output searchConnectionId string = (enableSearchConnection && !empty(aiSearchName)) ? searchConnection.id : ''
