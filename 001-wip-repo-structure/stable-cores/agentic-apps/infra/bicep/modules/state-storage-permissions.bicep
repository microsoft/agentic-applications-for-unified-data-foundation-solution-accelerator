// GENERATED FROM PROVIDED TERRAFORM. HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
metadata name = 'State Storage Permissions'
metadata description = 'Grants CI data-plane and management-plane access to Terraform state storage.'

@description('Name of the Terraform state storage account.')
param storageAccountName string

@description('Principal ID of the CI managed identity.')
param principalId string

var stateDataContributorRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var readerRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'acdd72a7-3385-48ef-bd42-f606fba81ae7')

resource stateStorage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource stateDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(stateStorage.id, principalId, stateDataContributorRoleId)
  scope: stateStorage
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: stateDataContributorRoleId
  }
}

resource stateReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(stateStorage.id, principalId, readerRoleId)
  scope: stateStorage
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: readerRoleId
  }
}
