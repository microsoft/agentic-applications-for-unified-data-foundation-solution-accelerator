// ============================================================================
// Module: AI Search
// Description: Deploys Azure AI Search with a two-step pattern:
//   Step 1: Plain Bicep resource for fast initial creation (name, location, SKU)
//   Step 2: Separate deployment to enable managed identity & full configuration
// This reduces deployment time by making the resource available immediately
// while identity enablement proceeds separately.
// ============================================================================

targetScope = 'resourceGroup'

@minLength(3)
@description('The name of the solution, used as a base for naming all resources.')
param solutionName string

@description('The Azure region where the search service will be deployed.')
param searchServiceLocation string = resourceGroup().location

var aiSearchName = 'srch-${solutionName}'
var aiSearchConnectionName = 'search-connection-${solutionName}'

// ============================================================================
// Step 1: Initial resource creation (fast — no identity)
// ============================================================================
resource aiSearch 'Microsoft.Search/searchServices@2025-05-01' = {
  name: aiSearchName
  location: searchServiceLocation
  sku: {
    name: 'standard'
  }
}

// ============================================================================
// Step 2: Update — enables identity & full configuration
// ============================================================================
resource aiSearchUpdate 'Microsoft.Search/searchServices@2025-05-01' = {
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
  dependsOn: [
    aiSearch
  ]
}

// ============================================================================
// Outputs
// ============================================================================

@description('The name of the AI Search service.')
output aiSearchName string = aiSearchName

@description('The resource ID of the AI Search service.')
output aiSearchId string = aiSearch.id

@description('The endpoint URL of the AI Search service.')
output aiSearchTarget string = 'https://${aiSearch.name}.search.windows.net'

@description('The name of the AI Search service resource.')
output aiSearchService string = aiSearch.name

@description('The name of the AI Search connection.')
output aiSearchConnectionName string = aiSearchConnectionName

@description('The principal ID of the AI Search system-assigned managed identity.')
output searchPrincipalId string = aiSearchUpdate.identity.principalId
