targetScope = 'resourceGroup'

@minLength(3)
@description('The name of the solution, used as a base for naming all resources.')
param solutionName string

@description('The Azure region where the search service will be deployed.')
param searchServiceLocation string = resourceGroup().location

var aiSearchName = 'srch-${solutionName}'
var aiSearchConnectionName = 'search-connection-${solutionName}'

// ========== AI Search Service ========== //

resource aiSearch 'Microsoft.Search/searchServices@2025-05-01' = {
  name: aiSearchName
  location: searchServiceLocation
  sku: {
    name: 'standard'
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

module aiSearchIdentity 'ai-search-identity.bicep' = {
  name: 'aiSearchIdentityDeployment'
  params: {
    searchServiceName: aiSearch.name
    searchServiceLocation: searchServiceLocation
  }
}

// ========== Outputs ========== //

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
output searchPrincipalId string = aiSearchIdentity.outputs.searchPrincipalId
