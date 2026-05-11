// ============================================================================
// Module: Role Assignments (cross-service only — service-scoped roles are inline)
// Description: RG-level and cross-service RBAC that can't be handled inline
// ============================================================================

@description('Principal ID of the primary managed identity.')
param primaryIdentityPrincipalId string

@description('Principal ID of the AI project identity.')
param aiProjectPrincipalId string = ''

@description('Principal ID of the AI Search identity.')
param aiSearchPrincipalId string = ''

@description('Resource ID of the AI Search service (empty if not deployed).')
param aiSearchResourceId string = ''

@description('Resource ID of the Storage Account (empty if not deployed).')
param storageAccountResourceId string = ''

@description('Whether workshop mode resources are deployed.')
param isWorkshop bool = false

// ============================================================================
// Role Definitions
// ============================================================================
var roleDefinitions = {
  owner: '8e3af657-a8ff-443c-a75c-2fe8c4bcb635'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  storageBlobDataReader: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
}

// ============================================================================
// Owner Role for Primary Identity (on Resource Group)
// ============================================================================
resource ownerRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: resourceGroup()
  name: roleDefinitions.owner
}

resource primaryIdentityOwnerAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, primaryIdentityPrincipalId, ownerRole.id)
  properties: {
    principalId: primaryIdentityPrincipalId
    roleDefinitionId: ownerRole.id
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// Cross-service: AI Project identity → AI Search (Workshop)
// ============================================================================
resource aiSearchService 'Microsoft.Search/searchServices@2024-06-01-preview' existing = if (!empty(aiSearchResourceId)) {
  name: last(split(aiSearchResourceId, '/'))
}

resource projectSearchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(aiSearchResourceId) && !empty(aiProjectPrincipalId) && isWorkshop) {
  name: guid(resourceGroup().id, aiProjectPrincipalId, roleDefinitions.searchIndexDataReader, 'project-search')
  scope: aiSearchService
  properties: {
    principalId: aiProjectPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.searchIndexDataReader)
    principalType: 'ServicePrincipal'
  }
}

resource projectSearchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(aiSearchResourceId) && !empty(aiProjectPrincipalId) && isWorkshop) {
  name: guid(resourceGroup().id, aiProjectPrincipalId, roleDefinitions.searchServiceContributor, 'project-search')
  scope: aiSearchService
  properties: {
    principalId: aiProjectPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.searchServiceContributor)
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// Cross-service: AI Project + AI Search identities → Storage (Workshop)
// ============================================================================
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = if (!empty(storageAccountResourceId)) {
  name: last(split(storageAccountResourceId, '/'))
}

resource projectStorageContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(storageAccountResourceId) && !empty(aiProjectPrincipalId) && isWorkshop) {
  name: guid(resourceGroup().id, aiProjectPrincipalId, roleDefinitions.storageBlobDataContributor, 'project-storage')
  scope: storageAccount
  properties: {
    principalId: aiProjectPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.storageBlobDataContributor)
    principalType: 'ServicePrincipal'
  }
}

resource projectStorageReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(storageAccountResourceId) && !empty(aiProjectPrincipalId) && isWorkshop) {
  name: guid(resourceGroup().id, aiProjectPrincipalId, roleDefinitions.storageBlobDataReader, 'project-storage')
  scope: storageAccount
  properties: {
    principalId: aiProjectPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.storageBlobDataReader)
    principalType: 'ServicePrincipal'
  }
}

resource searchStorageReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(storageAccountResourceId) && !empty(aiSearchPrincipalId) && isWorkshop) {
  name: guid(resourceGroup().id, aiSearchPrincipalId, roleDefinitions.storageBlobDataReader, 'search-storage')
  scope: storageAccount
  properties: {
    principalId: aiSearchPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.storageBlobDataReader)
    principalType: 'ServicePrincipal'
  }
}
