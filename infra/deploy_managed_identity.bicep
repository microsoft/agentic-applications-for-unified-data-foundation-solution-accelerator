// ========== Managed Identity ========== //
targetScope = 'resourceGroup'

@minLength(3)
@maxLength(25)
@description('Solution Name')
param solutionName string

@description('Solution Location')
param solutionLocation string

@description('Name')
param miName string

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: miName
  location: solutionLocation
  tags: {
    app: solutionName
    location: solutionLocation
  }
}

@description('This is the built-in owner role. See https://docs.microsoft.com/azure/role-based-access-control/built-in-roles#owner')
resource ownerRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: resourceGroup()
  name: '8e3af657-a8ff-443c-a75c-2fe8c4bcb635'
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, managedIdentity.id, ownerRoleDefinition.id)
  properties: {
    principalId: managedIdentity.properties.principalId
    roleDefinitionId:  ownerRoleDefinition.id
    principalType: 'ServicePrincipal' 
  }
}

resource managedIdentityBackendApp 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: 'id-backend-app-mi-${solutionName}'
  location: solutionLocation
  tags: {
    app: solutionName
    location: solutionLocation
  }
}

@description('The managed identity details including id, objectId, clientId, and name.')
output managedIdentityOutput object = {
  id: managedIdentity.id
  objectId: managedIdentity.properties.principalId
  clientId: managedIdentity.properties.clientId
  name: miName
}

@description('The backend app managed identity details including id, objectId, clientId, and name.')
output managedIdentityBackendAppOutput object = {
  id: managedIdentityBackendApp.id
  objectId: managedIdentityBackendApp.properties.principalId
  clientId: managedIdentityBackendApp.properties.clientId
  name: managedIdentityBackendApp.name
}
