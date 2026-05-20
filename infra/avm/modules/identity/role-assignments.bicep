// ============================================================================
// Module: Role Assignments (centralized — all cross-service + data plane RBAC)
// Description: RG-level, cross-service, and data-plane role assignments
// ============================================================================

@description('Solution name suffix for generating unique role assignment GUIDs.')
param solutionName string = ''

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

// --- Backend App Service system-assigned identity roles ---
@description('Name of the Cosmos DB account (empty if not deployed).')
param cosmosDbAccountName string = ''

@description('Principal ID of the backend App Service system-assigned identity (empty if not deployed).')
param backendAppServicePrincipalId string = ''

@description('Resource ID of the AI Services account (empty if not deployed — new project path).')
param aiServicesResourceId string = ''

@description('Whether to use an existing AI project (true) or create new (false).')
param useExistingAIProject bool = false

@description('Resource ID of the existing AI project (for deriving AI Services name/sub/RG).')
param existingAIProjectResourceId string = ''

@description('Principal ID of the existing AI project identity (for cross-service roles).')
param existingAiProjectPrincipalId string = ''

// ============================================================================
// Derived Variables
// ============================================================================
var existingAIServicesName = useExistingAIProject ? split(existingAIProjectResourceId, '/')[8] : ''
var existingAIServiceSubscription = useExistingAIProject ? split(existingAIProjectResourceId, '/')[2] : subscription().subscriptionId
var existingAIServiceResourceGroup = useExistingAIProject ? split(existingAIProjectResourceId, '/')[4] : resourceGroup().name

// ============================================================================
// Role Definitions
// ============================================================================
var roleDefinitions = {
  azureAiUser: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
  cognitiveServicesOpenAIUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  searchIndexDataReader: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
  searchServiceContributor: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
  storageBlobDataContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  storageBlobDataReader: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
}

// ============================================================================
// Cross-service: AI Search → Cognitive Services OpenAI User on AI Services
// ============================================================================
resource aiServicesAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = if (!empty(aiServicesResourceId)) {
  name: last(split(aiServicesResourceId, '/'))
}

// AI Search → OpenAI User on AI Services (new project, same RG)
resource assignOpenAIRoleToAISearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingAIProject && isWorkshop && !empty(aiSearchPrincipalId) && !empty(aiServicesResourceId)) {
  name: guid(resourceGroup().id, aiServicesAccount.id, roleDefinitions.cognitiveServicesOpenAIUser, 'search-openai')
  scope: aiServicesAccount
  properties: {
    principalId: aiSearchPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.cognitiveServicesOpenAIUser)
    principalType: 'ServicePrincipal'
  }
}

// AI Search → OpenAI User on existing AI Services (cross-scope)
module assignOpenAIToSearchExisting './cross-scope-role-assignment.bicep' = if (useExistingAIProject && isWorkshop && !empty(aiSearchPrincipalId)) {
  name: 'assignOpenAIRoleToAISearchExisting'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    principalId: aiSearchPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.cognitiveServicesOpenAIUser)
    roleAssignmentName: guid(solutionName, 'search-openai', existingAIServicesName, roleDefinitions.cognitiveServicesOpenAIUser)
    aiServicesName: existingAIServicesName
  }
}

// ============================================================================
// Cross-service: Backend App Service → Azure AI User on AI Services
// ============================================================================

// Backend → AI User on AI Services (new project, same RG)
resource backendAppAiUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!useExistingAIProject && !empty(aiServicesResourceId) && !empty(backendAppServicePrincipalId)) {
  name: guid(resourceGroup().id, backendAppServicePrincipalId, roleDefinitions.azureAiUser, 'backend-ai-services')
  scope: aiServicesAccount
  properties: {
    principalId: backendAppServicePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.azureAiUser)
    principalType: 'ServicePrincipal'
  }
}

// Backend → AI User on existing AI Services (cross-scope)
module backendAppAiUserExisting './cross-scope-role-assignment.bicep' = if (useExistingAIProject && !empty(backendAppServicePrincipalId)) {
  name: 'assignAiUserRoleToBackendExisting'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    principalId: backendAppServicePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.azureAiUser)
    roleAssignmentName: guid(solutionName, 'backend-aiuser', existingAIServicesName, roleDefinitions.azureAiUser)
    aiServicesName: existingAIServicesName
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

// Existing AI Project → Search Index Data Reader on AI Search
resource existingProjectSearchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingAIProject && !empty(aiSearchResourceId) && !empty(existingAiProjectPrincipalId) && isWorkshop) {
  name: guid(resourceGroup().id, existingAiProjectPrincipalId, roleDefinitions.searchIndexDataReader, 'existing-project-search')
  scope: aiSearchService
  properties: {
    principalId: existingAiProjectPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.searchIndexDataReader)
    principalType: 'ServicePrincipal'
  }
}

// Existing AI Project → Search Service Contributor on AI Search
resource existingProjectSearchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingAIProject && !empty(aiSearchResourceId) && !empty(existingAiProjectPrincipalId) && isWorkshop) {
  name: guid(resourceGroup().id, existingAiProjectPrincipalId, roleDefinitions.searchServiceContributor, 'existing-project-search')
  scope: aiSearchService
  properties: {
    principalId: existingAiProjectPrincipalId
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

// Existing AI Project → Storage Blob Data Contributor
resource existingProjectStorageContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingAIProject && !empty(storageAccountResourceId) && !empty(existingAiProjectPrincipalId) && isWorkshop) {
  name: guid(resourceGroup().id, existingAiProjectPrincipalId, roleDefinitions.storageBlobDataContributor, 'existing-project-storage')
  scope: storageAccount
  properties: {
    principalId: existingAiProjectPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.storageBlobDataContributor)
    principalType: 'ServicePrincipal'
  }
}

// Existing AI Project → Storage Blob Data Reader
resource existingProjectStorageReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useExistingAIProject && !empty(storageAccountResourceId) && !empty(existingAiProjectPrincipalId) && isWorkshop) {
  name: guid(resourceGroup().id, existingAiProjectPrincipalId, roleDefinitions.storageBlobDataReader, 'existing-project-storage')
  scope: storageAccount
  properties: {
    principalId: existingAiProjectPrincipalId
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

// ============================================================================
// Data Plane: Backend App Service → Cosmos DB (Built-in Data Contributor)
// Uses Microsoft.DocumentDB sqlRoleAssignments (NOT ARM roleAssignments)
// ============================================================================
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = if (!empty(cosmosDbAccountName)) {
  name: cosmosDbAccountName
}

resource cosmosContributorRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-11-15' existing = if (!empty(cosmosDbAccountName)) {
  parent: cosmosAccount
  name: '00000000-0000-0000-0000-000000000002'
}

resource backendAppCosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-11-15' = if (!empty(cosmosDbAccountName) && !empty(backendAppServicePrincipalId)) {
  parent: cosmosAccount
  name: guid(cosmosContributorRoleDefinition.id, cosmosAccount.id, backendAppServicePrincipalId)
  properties: {
    principalId: backendAppServicePrincipalId
    roleDefinitionId: cosmosContributorRoleDefinition.id
    scope: cosmosAccount.id
  }
}

// ============================================================================
// Cross-service: Backend App Service → AI Search
// ============================================================================
resource backendAppSearchReaderAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(aiSearchResourceId) && !empty(backendAppServicePrincipalId) && isWorkshop) {
  name: guid(resourceGroup().id, backendAppServicePrincipalId, roleDefinitions.searchIndexDataReader, 'backend-search')
  scope: aiSearchService
  properties: {
    principalId: backendAppServicePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitions.searchIndexDataReader)
    principalType: 'ServicePrincipal'
  }
}
