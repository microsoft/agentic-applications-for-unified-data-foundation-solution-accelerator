// ============================================================================
// Module: Existing Foundry Project (AI Services model deployments + connections)
// Description: Deploys model deployments and project connections to an existing
//              AI Services account. Used when useExistingAIProject = true.
// ============================================================================

@description('Required. The name of the existing Cognitive Services account.')
param name string

@description('Required. The name of the existing AI project.')
param projectName string

@description('Optional. SKU of the Cognitive Services account.')
@allowed([
  'C2'
  'C3'
  'C4'
  'F0'
  'F1'
  'S'
  'S0'
  'S1'
  'S10'
  'S2'
  'S3'
  'S4'
  'S5'
  'S6'
  'S7'
  'S8'
  'S9'
])
param sku string = 'S0'

import { deploymentType } from 'br:mcr.microsoft.com/bicep/avm/res/cognitive-services/account:0.13.2'
@description('Optional. Array of deployments about cognitive service accounts to create.')
param deployments deploymentType[]?

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
resource cognitiveService 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: name
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: cognitiveService
  name: projectName
}

// ============================================================================
// Model Deployments
// ============================================================================
@batchSize(1)
resource cognitiveService_deployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [
  for (deployment, index) in (deployments ?? []): {
    parent: cognitiveService
    name: deployment.?name ?? '${name}-deployments'
    properties: {
      model: deployment.model
      raiPolicyName: deployment.?raiPolicyName
      versionUpgradeOption: deployment.?versionUpgradeOption
    }
    sku: deployment.?sku ?? {
      name: sku
      capacity: sku.?capacity
      tier: sku.?tier
      size: sku.?size
      family: sku.?family
    }
  }
]

// ============================================================================
// Connections
// ============================================================================

// Application Insights connection
resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = if (!empty(applicationInsightsId)) {
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
resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = if (!empty(aiSearchTarget)) {
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
resource storageConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-06-01' = if (!empty(storageBlobEndpoint)) {
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
@description('Names of the deployed models.')
output deploymentNames array = [for (deployment, i) in (deployments ?? []): cognitiveService_deployments[i].name]

@description('The principal ID of the AI Foundry system-assigned managed identity.')
output aiFoundryPrincipalId string = cognitiveService.identity.principalId

@description('The principal ID of the AI Project system-assigned managed identity.')
output aiProjectPrincipalId string = aiProject.identity.principalId

@description('The name of the AI Search connection (pass-through).')
output searchConnectionName string = !empty(aiSearchTarget) ? aiSearchConnectionName : ''

