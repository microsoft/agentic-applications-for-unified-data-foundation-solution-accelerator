targetScope = 'resourceGroup'

@description('The name of the existing AI Search service.')
param searchServiceName string

@description('The Azure region of the search service.')
param searchServiceLocation string

resource aiSearchIdentity 'Microsoft.Search/searchServices@2025-05-01' = {
  name: searchServiceName
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

@description('The principal ID of the AI Search system-assigned managed identity.')
output searchPrincipalId string = aiSearchIdentity.identity.principalId
