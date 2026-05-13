targetScope = 'resourceGroup'

@description('The name of the AI Services account that owns the AI project.')
param aiServicesName string

@description('The name of the AI Foundry project.')
param aiProjectName string

@description('The name of the AI Search connection.')
param aiSearchConnectionName string

@description('The endpoint URL of the AI Search service.')
param aiSearchTarget string

@description('The resource ID of the AI Search service.')
param aiSearchId string

@description('The blob endpoint URL of the storage account.')
param storageBlobTarget string

@description('The resource ID of the storage account.')
param storageAccountId string

@description('The name of the storage account.')
param storageAccountName string

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: aiServicesName
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' existing = {
  parent: aiServices
  name: aiProjectName
}

resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = {
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

resource storageConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = {
  parent: aiProject
  name: 'storage-connection'
  properties: {
    category: 'AzureBlob'
    target: storageBlobTarget
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ResourceId: storageAccountId
      AccountName: storageAccountName
      ContainerName: 'default'
    }
  }
}

@description('The resource ID of the AI Search connection.')
output aiSearchConnectionId string = searchConnection.id
