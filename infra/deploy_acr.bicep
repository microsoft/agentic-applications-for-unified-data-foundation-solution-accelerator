// ========== Dedicated Azure Container Registry (identity-based pull) ========== //
targetScope = 'resourceGroup'

@description('The name of the Azure Container Registry to create. Must be globally unique, 5-50 alphanumeric characters.')
@minLength(5)
@maxLength(50)
param acrName string

@description('The Azure region where the container registry will be deployed.')
param solutionLocation string = resourceGroup().location

@description('Solution name used for tagging.')
param solutionName string = ''

@description('Principal (object) IDs of the managed identities that require AcrPull access to this registry.')
param acrPullPrincipalIds array = []

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2025-11-01' = {
  name: acrName
  location: solutionLocation
  tags: empty(solutionName) ? {} : {
    app: solutionName
    location: solutionLocation
  }
  sku: {
    name: 'Standard'
  }
  properties: {
    // Identity-based authentication only. Anonymous pull and admin user are disabled.
    adminUserEnabled: false
    anonymousPullEnabled: false
    dataEndpointEnabled: false
    networkRuleBypassOptions: 'AzureServices'
    policies: {
      quarantinePolicy: {
        status: 'disabled'
      }
      trustPolicy: {
        status: 'disabled'
        type: 'Notary'
      }
    }
    publicNetworkAccess: 'Enabled'
    zoneRedundancy: 'Disabled'
  }
}

@description('Built-in AcrPull role. See https://learn.microsoft.com/azure/role-based-access-control/built-in-roles#acrpull')
resource acrPullRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
}

resource acrPullRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for principalId in acrPullPrincipalIds: {
    name: guid(containerRegistry.id, principalId, acrPullRoleDefinition.id)
    scope: containerRegistry
    properties: {
      principalId: principalId
      roleDefinitionId: acrPullRoleDefinition.id
      principalType: 'ServicePrincipal'
    }
  }
]

@description('The name of the created container registry.')
output acrName string = containerRegistry.name

@description('The login server of the created container registry (e.g., myacr.azurecr.io).')
output loginServer string = containerRegistry.properties.loginServer

@description('The resource ID of the container registry.')
output acrId string = containerRegistry.id
