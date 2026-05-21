// ============================================================================
// Module: AI Foundry
// Description: AVM wrapper for Azure AI Services account + AI Foundry Project
//              Includes: AI Services, Project, Connections (Search, Storage, AppInsights)
// AVM Module: avm/res/cognitive-services/account
// WAF: https://learn.microsoft.com/azure/well-architected/service-guides/azure-openai
// ============================================================================

@description('Solution name suffix used to derive resource names.')
param solutionName string

var aiFoundryName = 'aif-${solutionName}'
var projectName = 'proj-${solutionName}'

@description('Azure region for the resources.')
param location string

@description('Tags to apply to resources.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('SKU name for the AI Services account.')
param skuName string = 'S0'

@description('Whether to disable local authentication.')
param disableLocalAuth bool = true

@description('Whether to allow project management (AI Foundry).')
param allowProjectManagement bool = true

@description('Public network access setting.')
param publicNetworkAccess string = 'Enabled'

// --- WAF: Monitoring ---
@description('Optional. Diagnostic settings for the resource.')
param diagnosticSettings array?

// --- Model Deployments ---
@description('Optional. Array of model deployments to create.')
param deployments array?

// --- Role Assignments ---
@description('Optional. Array of role assignments to create on the AI Services account.')
param roleAssignments array?

// --- Project Connections ---
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

// --- WAF: Private Networking ---
@description('Whether to enable private networking for AI Services.')
param enablePrivateNetworking bool = false

@description('Subnet resource ID for the private endpoint.')
param privateEndpointSubnetId string = ''

@description('Private DNS zone resource IDs for AI Services (cognitiveservices, openai, aiservices).')
param privateDnsZoneResourceIds array = []

var privateDnsZoneConfigs = [for (zoneId, i) in privateDnsZoneResourceIds: {
  name: 'dns-zone-${i}'
  privateDnsZoneResourceId: zoneId
}]

// ============================================================================
// AI Services (AVM Module)
// ============================================================================
module aiFoundryAccount 'br/public:avm/res/cognitive-services/account:0.13.2' = {
  name: take('avm.res.cognitive-services.account.${aiFoundryName}', 64)
  params: {
    name: aiFoundryName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    sku: skuName
    kind: 'AIServices'
    disableLocalAuth: disableLocalAuth
    allowProjectManagement: allowProjectManagement
    customSubDomainName: aiFoundryName
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: publicNetworkAccess
    managedIdentities: {
      systemAssigned: true
    }
    diagnosticSettings: diagnosticSettings
    deployments: deployments
    roleAssignments: roleAssignments
    // Private endpoints deployed separately to avoid race condition (AccountProvisioningStateInvalid)
    privateEndpoints: []
  }
}

// ============================================================================
// AI Foundry Project
// ============================================================================
resource aiFoundryResource 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: aiFoundryName
  dependsOn: [aiFoundryAccount]
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' = {
  parent: aiFoundryResource
  name: projectName
  location: location
  tags: tags
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
  dependsOn: [aiFoundryAccount]
}

// ============================================================================
// Connections
// ============================================================================

// AI Search Connection
resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (enableSearchConnection && !empty(aiSearchName)) {
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
resource storageConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (enableStorageConnection && !empty(storageAccountName)) {
  parent: aiProject
  name: 'storage-connection'
  properties: {
    category: 'AzureBlob'
    target: storageBlobEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ResourceId: storageAccountResourceId
      AccountName: storageAccountName
      ContainerName: 'default'
    }
  }
}

// Application Insights Connection
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (!empty(applicationInsightsResourceId)) {
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

// --- AI Foundry Outputs ---
@description('Resource ID of the AI Foundry account.')
output resourceId string = aiFoundryAccount.outputs.resourceId

@description('Name of the AI Foundry account.')
output name string = aiFoundryAccount.outputs.name

@description('Endpoint of the AI Foundry account.')
output endpoint string = aiFoundryAccount.outputs.endpoint

// --- AI Foundry Project Outputs ---
@description('Resource ID of the AI Foundry project.')
output projectResourceId string = aiProject.id

@description('Name of the AI Foundry project.')
output projectName string = aiProject.name

@description('AI Foundry project endpoint.')
output projectEndpoint string = aiProject.properties.endpoints['AI Foundry API']

@description('System-assigned identity principal ID of the project.')
output projectIdentityPrincipalId string = aiProject.identity.principalId

@description('AI Search connection name.')
output searchConnectionName string = enableSearchConnection ? aiSearchConnectionName : ''

@description('AI Search connection ID.')
output searchConnectionId string = (enableSearchConnection && !empty(aiSearchName)) ? searchConnection.id : ''
