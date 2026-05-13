targetScope = 'resourceGroup'

@description('The name of the solution, used as a base for naming all resources.')
param solutionName string

@description('When true, deploys additional resources for workshop scenarios including AI Search and Storage.')
param isWorkshop bool = false

@description('The resource ID of an existing Azure AI Foundry project. If provided, the existing project will be used instead of creating a new one.')
param azureExistingAIProjectResourceId string = ''

@description('The object ID of the managed identity to assign roles to.')
param managedIdentityObjectId string = ''

@description('The name of the Azure AI Services account.')
param aiServicesName string = ''

@description('The name of the Azure AI Search service.')
param aiSearchName string = ''

@description('The name of the storage account.')
param storageAccountName string = ''

@description('The principal ID of the AI Foundry project managed identity for newly created projects.')
param aiProjectPrincipalId string = ''

@description('The principal ID of the AI Foundry project managed identity for existing projects.')
param existingAiProjectPrincipalId string = ''

@description('The principal ID of the AI Search system-assigned managed identity.')
param searchPrincipalId string = ''

@description('The principal ID of the deploying user.')
param deployingUserPrincipalId string = ''

@description('The principal type of the deploying user. Use ServicePrincipal for CI/CD pipelines with OIDC.')
@allowed(['User', 'ServicePrincipal'])
param deployingUserPrincipalType string = 'User'

@description('The principal ID of the backend app managed identity.')
param backendAppPrincipalId string = ''

var existingAIServicesName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[8] : ''
var existingAIProjectName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[10] : ''
var existingAIServiceSubscription = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[2] : subscription().subscriptionId
var existingAIServiceResourceGroup = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[4] : resourceGroup().name

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = if (!empty(aiServicesName) && empty(azureExistingAIProjectResourceId)) {
  name: aiServicesName
}

resource aiSearch 'Microsoft.Search/searchServices@2025-05-01' existing = if (!empty(aiSearchName)) {
  name: aiSearchName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2025-08-01' existing = if (!empty(storageAccountName)) {
  name: storageAccountName
}

// ╔══════════════════════════════════════════════════════════════╗
// ║  ROLE DEFINITIONS                                           ║
// ╚══════════════════════════════════════════════════════════════╝

resource azureAIUser 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Azure AI User
}

resource cognitiveServicesOpenAIUser 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User
}

resource cognitiveServicesUser 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User
}

resource searchIndexDataReader 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '1407120a-92aa-4202-b7e9-c0e197c71c8f' // Search Index Data Reader
}

resource searchServiceContributor 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '7ca78c08-252a-4471-8644-bb5ff32d4ba0' // Search Service Contributor
}

resource searchIndexDataContributor 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '8ebe5a00-799e-43f5-93ac-243d3dce84a7' // Search Index Data Contributor
}

resource storageBlobDataContributor 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
}

resource storageBlobDataReader 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1' // Storage Blob Data Reader
}

// ╔══════════════════════════════════════════════════════════════╗
// ║  AI SERVICES ROLE ASSIGNMENTS                               ║
// ╚══════════════════════════════════════════════════════════════╝

resource assignFoundryRoleToMI 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && !empty(managedIdentityObjectId) && !empty(aiServicesName)) {
  name: guid(resourceGroup().id, aiServices.id, azureAIUser.id)
  scope: aiServices
  properties: {
    principalId: managedIdentityObjectId
    roleDefinitionId: azureAIUser.id
    principalType: 'ServicePrincipal'
  }
}

resource assignOpenAIRoleToAISearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && isWorkshop && !empty(searchPrincipalId) && !empty(aiServicesName)) {
  name: guid(resourceGroup().id, aiServices.id, cognitiveServicesOpenAIUser.id)
  scope: aiServices
  properties: {
    principalId: searchPrincipalId
    roleDefinitionId: cognitiveServicesOpenAIUser.id
    principalType: 'ServicePrincipal'
  }
}

module existingOpenAiProject './foundry-role-assignment.bicep' = if (!empty(azureExistingAIProjectResourceId) && isWorkshop && !empty(searchPrincipalId) && !empty(aiSearchName)) {
  name: 'assignOpenAIRoleToAISearchExisting'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    roleDefinitionId: cognitiveServicesOpenAIUser.id
    roleAssignmentName: guid(resourceGroup().id, aiSearch.id, cognitiveServicesOpenAIUser.id, 'openai-foundry')
    aiServicesName: existingAIServicesName
    aiProjectName: existingAIProjectName
    principalId: searchPrincipalId
    enableSystemAssignedIdentity: true
  }
}

// ╔══════════════════════════════════════════════════════════════╗
// ║  SEARCH SERVICE ROLE ASSIGNMENTS                            ║
// ╚══════════════════════════════════════════════════════════════╝

resource assignSearchIndexDataReaderToAiProject 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && isWorkshop && !empty(aiProjectPrincipalId) && !empty(aiSearchName)) {
  name: guid(resourceGroup().id, aiProjectPrincipalId, searchIndexDataReader.id)
  scope: aiSearch
  properties: {
    principalId: aiProjectPrincipalId
    roleDefinitionId: searchIndexDataReader.id
    principalType: 'ServicePrincipal'
  }
}

resource assignSearchIndexDataReaderToExistingAiProject 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(azureExistingAIProjectResourceId) && isWorkshop && !empty(existingAiProjectPrincipalId) && !empty(aiSearchName)) {
  name: guid(resourceGroup().id, existingAIProjectName, searchIndexDataReader.id, 'Existing')
  scope: aiSearch
  properties: {
    principalId: existingAiProjectPrincipalId
    roleDefinitionId: searchIndexDataReader.id
    principalType: 'ServicePrincipal'
  }
}

resource assignSearchServiceContributorToAiProject 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && isWorkshop && !empty(aiProjectPrincipalId) && !empty(aiSearchName)) {
  name: guid(resourceGroup().id, aiProjectPrincipalId, searchServiceContributor.id)
  scope: aiSearch
  properties: {
    principalId: aiProjectPrincipalId
    roleDefinitionId: searchServiceContributor.id
    principalType: 'ServicePrincipal'
  }
}

resource assignSearchServiceContributorToExistingAiProject 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(azureExistingAIProjectResourceId) && isWorkshop && !empty(existingAiProjectPrincipalId) && !empty(aiSearchName)) {
  name: guid(resourceGroup().id, existingAIProjectName, searchServiceContributor.id, 'Existing')
  scope: aiSearch
  properties: {
    principalId: existingAiProjectPrincipalId
    roleDefinitionId: searchServiceContributor.id
    principalType: 'ServicePrincipal'
  }
}

resource assignSearchIndexDataContributorToMI 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && isWorkshop && !empty(managedIdentityObjectId) && !empty(aiSearchName)) {
  name: guid(resourceGroup().id, managedIdentityObjectId, searchIndexDataContributor.id)
  scope: aiSearch
  properties: {
    principalId: managedIdentityObjectId
    roleDefinitionId: searchIndexDataContributor.id
    principalType: 'ServicePrincipal'
  }
}

resource assignSearchIndexDataReaderToApi 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isWorkshop && !empty(backendAppPrincipalId) && !empty(aiSearchName)) {
  name: guid(solutionName, aiSearchName, searchIndexDataReader.id, backendAppPrincipalId)
  scope: aiSearch
  properties: {
    principalId: backendAppPrincipalId
    roleDefinitionId: searchIndexDataReader.id
    principalType: 'ServicePrincipal'
  }
}

// ╔══════════════════════════════════════════════════════════════╗
// ║  STORAGE ROLE ASSIGNMENTS                                   ║
// ╚══════════════════════════════════════════════════════════════╝

resource projectStorageBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && isWorkshop && !empty(aiProjectPrincipalId) && !empty(storageAccountName)) {
  scope: storageAccount
  name: guid(storageAccount.id, aiProjectPrincipalId, storageBlobDataContributor.id)
  properties: {
    principalId: aiProjectPrincipalId
    roleDefinitionId: storageBlobDataContributor.id
    principalType: 'ServicePrincipal'
  }
}

resource existingProjectStorageBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(azureExistingAIProjectResourceId) && isWorkshop && !empty(existingAiProjectPrincipalId) && !empty(storageAccountName)) {
  scope: storageAccount
  name: guid(storageAccount.id, existingAIProjectName, storageBlobDataContributor.id)
  properties: {
    principalId: existingAiProjectPrincipalId
    roleDefinitionId: storageBlobDataContributor.id
    principalType: 'ServicePrincipal'
  }
}

resource projectStorageBlobReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && isWorkshop && !empty(aiProjectPrincipalId) && !empty(storageAccountName)) {
  scope: storageAccount
  name: guid(storageAccount.id, aiProjectPrincipalId, storageBlobDataReader.id)
  properties: {
    principalId: aiProjectPrincipalId
    roleDefinitionId: storageBlobDataReader.id
    principalType: 'ServicePrincipal'
  }
}

resource existingProjectStorageBlobReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(azureExistingAIProjectResourceId) && isWorkshop && !empty(existingAiProjectPrincipalId) && !empty(storageAccountName)) {
  scope: storageAccount
  name: guid(storageAccount.id, existingAIProjectName, storageBlobDataReader.id)
  properties: {
    principalId: existingAiProjectPrincipalId
    roleDefinitionId: storageBlobDataReader.id
    principalType: 'ServicePrincipal'
  }
}

resource searchStorageBlobDataReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isWorkshop && !empty(searchPrincipalId) && !empty(storageAccountName)) {
  scope: storageAccount
  name: guid(storageAccount.id, searchPrincipalId, storageBlobDataReader.id)
  properties: {
    principalId: searchPrincipalId
    roleDefinitionId: storageBlobDataReader.id
    principalType: 'ServicePrincipal'
  }
}

// ╔══════════════════════════════════════════════════════════════╗
// ║  USER ACCESS ROLE ASSIGNMENTS                               ║
// ╚══════════════════════════════════════════════════════════════╝

resource userAIServicesAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && !empty(deployingUserPrincipalId) && !empty(aiServicesName)) {
  scope: aiServices
  name: guid(aiServices.id, deployingUserPrincipalId, cognitiveServicesUser.id)
  properties: {
    principalId: deployingUserPrincipalId
    roleDefinitionId: cognitiveServicesUser.id
    principalType: deployingUserPrincipalType
  }
}

resource userAzureAIAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (empty(azureExistingAIProjectResourceId) && !empty(deployingUserPrincipalId) && !empty(aiServicesName)) {
  scope: aiServices
  name: guid(aiServices.id, deployingUserPrincipalId, azureAIUser.id)
  properties: {
    principalId: deployingUserPrincipalId
    roleDefinitionId: azureAIUser.id
    principalType: deployingUserPrincipalType
  }
}

resource userSearchIndexContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isWorkshop && !empty(deployingUserPrincipalId) && !empty(aiSearchName)) {
  scope: aiSearch
  name: guid(aiSearch.id, deployingUserPrincipalId, searchIndexDataContributor.id)
  properties: {
    principalId: deployingUserPrincipalId
    roleDefinitionId: searchIndexDataContributor.id
    principalType: deployingUserPrincipalType
  }
}

resource userSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isWorkshop && !empty(deployingUserPrincipalId) && !empty(aiSearchName)) {
  scope: aiSearch
  name: guid(aiSearch.id, deployingUserPrincipalId, searchServiceContributor.id)
  properties: {
    principalId: deployingUserPrincipalId
    roleDefinitionId: searchServiceContributor.id
    principalType: deployingUserPrincipalType
  }
}

resource userStorageBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isWorkshop && !empty(deployingUserPrincipalId) && !empty(storageAccountName)) {
  scope: storageAccount
  name: guid(storageAccount.id, deployingUserPrincipalId, storageBlobDataContributor.id)
  properties: {
    principalId: deployingUserPrincipalId
    roleDefinitionId: storageBlobDataContributor.id
    principalType: deployingUserPrincipalType
  }
}
