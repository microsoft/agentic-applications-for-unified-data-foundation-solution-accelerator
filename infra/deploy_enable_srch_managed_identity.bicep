@description('The name of the AI Search service to enable managed identity on.')
param searchServiceName string

@description('The Azure region where the search service is deployed.')
param location string

resource aiSearchWithManagedIdentity 'Microsoft.Search/searchServices@2025-05-01' = {
  name: searchServiceName
  location: location
  sku: {
    name: 'basic'
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

@description('The principal ID of the search service system-assigned managed identity.')
output principalId string = aiSearchWithManagedIdentity.identity.principalId
