// ============================================================================
// existing-project-setup.bicep
// Full setup for an existing AI Foundry project:
//   1. Updates AI Services with system-assigned managed identity
//   2. Deploys AI model deployments (GPT + optional embedding)
//   3. Updates AI Project with system-assigned managed identity
//   4. Creates project connections (AppInsights, Search, Storage)
// Called from main.bicep with cross-scope after existing-foundry-project.bicep reads properties.
// ============================================================================

@description('The name of the AI Services account.')
param aiServicesName string

@description('The name of the AI project under the AI Services account.')
param aiProjectName string

@description('The Azure region for the AI Services account.')
param aiLocation string

@description('The kind of AI Services account (e.g., AIServices).')
param aiKind string

@description('The SKU name for the AI Services account.')
param aiSkuName string

@description('The custom subdomain name for the AI Services account.')
param customSubDomainName string

@description('The public network access setting for the AI Services account.')
param publicNetworkAccess string

@description('The default network action for the AI Services account.')
param defaultNetworkAction string

@description('Virtual network rules for the AI Services account.')
param vnetRules array = []

@description('IP rules for the AI Services account.')
param ipRules array = []

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
// Identity Setup
// ============================================================================

// Update AI Services with system-assigned managed identity
resource aiServicesWithIdentity 'Microsoft.CognitiveServices/accounts@2025-12-01' = {
  name: aiServicesName
  location: aiLocation
  kind: aiKind
  sku: {
    name: aiSkuName
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: customSubDomainName
    networkAcls: {
      defaultAction: defaultNetworkAction
      virtualNetworkRules: vnetRules
      ipRules: ipRules
    }
    publicNetworkAccess: publicNetworkAccess
  }
}

// Deploy AI models
@batchSize(1)
resource aiServicesDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-12-01' = [for aiModeldeployment in aiModelDeployments: if (!empty(aiModelDeployments)) {
  parent: aiServicesWithIdentity
  name: aiModeldeployment.name
  properties: {
    model: {
      format: 'OpenAI'
      name: aiModeldeployment.model
    }
    raiPolicyName: aiModeldeployment.raiPolicyName
  }
  sku: {
    name: aiModeldeployment.sku.name
    capacity: aiModeldeployment.sku.capacity
  }
}]

// Update AI Project with system-assigned managed identity
resource aiProjectWithIdentity 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' = if (!empty(aiProjectName)) {
  name: aiProjectName
  parent: aiServicesWithIdentity
  location: aiLocation
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

// ============================================================================
// Connections
// ============================================================================

// Application Insights connection
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (!empty(aiProjectName) && !empty(applicationInsightsId)) {
  parent: aiProjectWithIdentity
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
resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (!empty(aiProjectName) && !empty(aiSearchTarget)) {
  parent: aiProjectWithIdentity
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
resource storageConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (!empty(aiProjectName) && !empty(storageBlobEndpoint)) {
  parent: aiProjectWithIdentity
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

@description('The principal ID of the AI Services system-assigned managed identity.')
output aiServicesPrincipalId string = aiServicesWithIdentity.identity.principalId

@description('The principal ID of the AI Project system-assigned managed identity.')
output aiProjectPrincipalId string = !empty(aiProjectName) ? aiProjectWithIdentity.identity.principalId : ''

@description('The resource ID of the AI Search connection.')
output aiSearchConnectionId string = !empty(aiSearchTarget) ? searchConnection.id : ''
