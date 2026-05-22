// ============================================================================
// existing-project-setup.bicep
// For existing AI Foundry projects: deploys models + creates connections.
// Follows MACAE pattern — uses `existing` refs only, no identity re-PUT.
// ============================================================================

@description('The name of the existing AI Services account.')
param aiFoundryName string

@description('The name of the existing AI project.')
param aiProjectName string

@description('Array of AI model deployments to create.')
param aiModelDeployments array = []

// ── Connection params (optional, workshop-only) ──

@description('The resource ID of the Application Insights instance.')
param applicationInsightsId string = ''

@description('The instrumentation key of the Application Insights instance.')
param applicationInsightsInstrumentationKey string = ''

@description('The endpoint URL of the AI Search service.')
param aiSearchTarget string = ''

@description('The resource ID of the AI Search service.')
param aiSearchId string = ''

@description('The name of the AI Search connection.')
param aiSearchConnectionName string = ''

@description('The blob endpoint URL of the storage account.')
param storageBlobEndpoint string = ''

@description('The resource ID of the storage account.')
param storageAccountId string = ''

@description('The name of the storage account.')
param storageAccountName string = ''

// ============================================================================
// Existing Resource References
// ============================================================================

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: aiFoundryName
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' existing = {
  parent: aiServices
  name: aiProjectName
}

// ============================================================================
// Model Deployments
// ============================================================================

@batchSize(1)
resource aiServicesDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-12-01' = [for deployment in aiModelDeployments: if (!empty(aiModelDeployments)) {
  parent: aiServices
  name: deployment.name
  properties: {
    model: {
      format: 'OpenAI'
      name: deployment.model
    }
    raiPolicyName: deployment.raiPolicyName
  }
  sku: {
    name: deployment.sku.name
    capacity: deployment.sku.capacity
  }
}]

// ============================================================================
// Connections
// ============================================================================

// Application Insights connection
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (!empty(applicationInsightsId)) {
  parent: aiProject
  name: 'appi-connection'
  properties: {
    category: 'AppInsights'
    target: applicationInsightsId
    authType: 'ApiKey'
    isSharedToAll: true
    isDefault: true
    credentials: {
      key: applicationInsightsInstrumentationKey
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: applicationInsightsId
    }
  }
}

// AI Search connection
resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (!empty(aiSearchTarget)) {
  parent: aiProject
  name: aiSearchConnectionName
  properties: {
    category: 'CognitiveSearch'
    target: aiSearchTarget
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: aiSearchId
    }
  }
}

// Storage Blob connection
resource storageConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (!empty(storageBlobEndpoint)) {
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

// ============================================================================
// Outputs
// ============================================================================

@description('The principal ID of the AI Foundry system-assigned managed identity.')
output aiFoundryPrincipalId string = contains(aiServices, 'identity') && contains(aiServices.identity, 'principalId') ? aiServices.identity.principalId : ''

@description('The principal ID of the AI Project system-assigned managed identity.')
output aiProjectPrincipalId string = contains(aiProject, 'identity') && contains(aiProject.identity, 'principalId') ? aiProject.identity.principalId : ''

@description('The resource ID of the AI Search connection.')
output aiSearchConnectionId string = !empty(aiSearchTarget) ? searchConnection.id : ''

@description('The endpoint URL for the Azure OpenAI service.')
output aiFoundryEndpoint string = 'https://${aiFoundryName}.openai.azure.com/'

@description('The endpoint URL for the AI Foundry project.')
output projectEndpoint string = 'https://${aiFoundryName}.services.ai.azure.com/api/projects/${aiProjectName}'

@description('The name of the AI Foundry account.')
output aiFoundryNameOutput string = aiFoundryName

@description('The name of the AI Foundry project.')
output aiProjectNameOutput string = aiProjectName

@description('The resource ID of the AI Foundry account.')
output aiFoundryResourceId string = aiServices.id
