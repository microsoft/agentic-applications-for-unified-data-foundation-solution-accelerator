// GENERATED FROM PROVIDED TERRAFORM. HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
metadata name = 'CI OIDC Credentials'
metadata description = 'Deploys GitHub OIDC workload identity and least-scope deployment permissions.'

@description('Name of the CI user-assigned managed identity.')
param name string

@description('Azure region for the managed identity.')
param location string

@description('Immutable numeric GitHub repository owner ID.')
param githubRepositoryOwnerId string

@description('Immutable numeric GitHub repository ID.')
param githubRepositoryId string

@description('GitHub Environment included in the OIDC subject.')
param githubEnvironment string

@description('Name of the existing Azure Container Registry.')
param containerRegistryName string

@description('Name of the existing Azure AI Services account.')
param aiServicesName string

@description('Subscription ID containing the Terraform state storage account.')
param stateSubscriptionId string

@description('Resource group containing the Terraform state storage account.')
param stateResourceGroupName string

@description('Name of the Terraform state storage account.')
param stateStorageAccountName string

@description('Tags to apply to the managed identity.')
param tags object

var acrPushRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')
var aiOpenAiUserRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a001fd3d-188f-4b5d-821b-7da978bf7442')
var contributorRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}

resource federatedCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: identity
  name: 'github-actions-${githubEnvironment}'
  properties: {
    audiences: ['api://AzureADTokenExchange']
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repository_owner_id:${githubRepositoryOwnerId}:repository_id:${githubRepositoryId}:environment:${githubEnvironment}'
  }
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
}

resource aiServices 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: aiServicesName
}


resource registryPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, identity.id, acrPushRoleId)
  scope: containerRegistry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPushRoleId
  }
}

resource aiServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiServices.id, identity.id, aiOpenAiUserRoleId)
  scope: aiServices
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: aiOpenAiUserRoleId
  }
}

resource resourceGroupContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, identity.id, contributorRoleId)
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: contributorRoleId
  }
}

module statePermissions './state-storage-permissions.bicep' = {
  scope: resourceGroup(stateSubscriptionId, stateResourceGroupName)
  params: {
    principalId: identity.properties.principalId
    storageAccountName: stateStorageAccountName
  }
}
@description('Client ID of the CI managed identity.')
output clientId string = identity.properties.clientId

@description('Principal ID of the CI managed identity.')
output principalId string = identity.properties.principalId
