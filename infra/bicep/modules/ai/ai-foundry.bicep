// ========== ai-foundry.bicep ========== //
// Creates Azure AI Services account, AI Foundry project, model deployments,
// and the Application Insights connection to the project.
// Monitoring resources (Log Analytics + App Insights) are deployed separately via modules/monitoring/.

targetScope = 'resourceGroup'

@minLength(3)
@description('The name of the solution, used as a base for naming all resources.')
param solutionName string

@description('The Azure region where resources will be deployed.')
param solutionLocation string

@description('The deployment type for the GPT model (e.g., Standard, GlobalStandard).')
param deploymentType string

@description('The name of the GPT model to deploy (e.g., gpt-4o, gpt-4).')
param gptModelName string

@description('The version of the GPT model to deploy.')
param gptModelVersion string

@description('The capacity (in thousands of tokens per minute) for the GPT model deployment.')
param gptDeploymentCapacity int

@description('The name of the embedding model to deploy.')
param embeddingModel string

@description('The capacity for the embedding model deployment.')
param embeddingDeploymentCapacity int

@description('The object ID of the managed identity to assign roles to.')
param managedIdentityObjectId string = ''

@description('The resource ID of an existing Azure AI Foundry project. If provided, the existing project will be used instead of creating a new one.')
param azureExistingAIProjectResourceId string = ''

@description('The resource ID of the Application Insights instance (from monitoring module).')
param applicationInsightsId string

@description('The instrumentation key of the Application Insights instance (from monitoring module).')
param applicationInsightsInstrumentationKey string

@description('When true, deploys additional resources for workshop scenarios including AI Search and Storage.')
param isWorkshop bool = false

var aiServicesName = 'aisa-${solutionName}'
var applicationInsightsName = 'appi-${solutionName}'
var location = solutionLocation
var aiProjectName = 'aifp-${solutionName}'

var aiModelDeployments = concat([
  {
    name: gptModelName
    model: gptModelName
    sku: {
      name: deploymentType
      capacity: gptDeploymentCapacity
    }
    version: gptModelVersion
    raiPolicyName: 'Microsoft.Default'
  }
], isWorkshop ? [
  {
    name: embeddingModel
    model: embeddingModel
    sku: {
      name: 'GlobalStandard'
      capacity: embeddingDeploymentCapacity
    }
    version: '1'
    raiPolicyName: 'Microsoft.Default'
  }
] : [])

var existingOpenAIEndpoint = !empty(azureExistingAIProjectResourceId) ? format('https://{0}.openai.azure.com/', split(azureExistingAIProjectResourceId, '/')[8]) : ''
var existingProjEndpoint = !empty(azureExistingAIProjectResourceId) ? format('https://{0}.services.ai.azure.com/api/projects/{1}', split(azureExistingAIProjectResourceId, '/')[8], split(azureExistingAIProjectResourceId, '/')[10]) : ''
var existingAIServicesName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[8] : ''
var existingAIProjectName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[10] : ''
var existingAIServiceSubscription = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[2] : subscription().subscriptionId
var existingAIServiceResourceGroup = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[4] : resourceGroup().name

// ========== AI Services ========== //

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' = if (empty(azureExistingAIProjectResourceId)) {
  name: aiServicesName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: aiServicesName
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource existingAiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = if (!empty(azureExistingAIProjectResourceId)) {
  name: existingAIServicesName
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
}

module existing_aiServicesModule 'existing-foundry-project.bicep' = if (!empty(azureExistingAIProjectResourceId)) {
  name: 'existing_foundry_project'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    aiServicesName: existingAIServicesName
    aiProjectName: existingAIProjectName
  }
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' = if (empty(azureExistingAIProjectResourceId)) {
  parent: aiServices
  name: aiProjectName
  location: solutionLocation
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

// This cross-scope module must remain here because it is the only place that can both
// rehydrate an existing AI project with a system-assigned identity and return its principal ID.
module assignFoundryRoleToMIExisting '../identity/foundry-role-assignment.bicep' = if (!empty(azureExistingAIProjectResourceId)) {
  name: 'assignFoundryRoleToMI'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
    roleAssignmentName: guid(resourceGroup().id, managedIdentityObjectId, '53ca6127-db72-4b80-b1b0-d745d6d5456d', 'foundry')
    aiServicesName: existingAIServicesName
    aiProjectName: existingAIProjectName
    principalId: managedIdentityObjectId
    aiLocation: existing_aiServicesModule.outputs.location
    aiKind: existing_aiServicesModule.outputs.kind
    aiSkuName: existing_aiServicesModule.outputs.skuName
    customSubDomainName: existing_aiServicesModule.outputs.customSubDomainName
    publicNetworkAccess: existing_aiServicesModule.outputs.publicNetworkAccess
    enableSystemAssignedIdentity: true
    defaultNetworkAction: existing_aiServicesModule.outputs.defaultNetworkAction
    vnetRules: existing_aiServicesModule.outputs.vnetRules
    ipRules: existing_aiServicesModule.outputs.ipRules
    aiModelDeployments: aiModelDeployments
  }
}

// ========== Application Insights Connection ========== //

resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (empty(azureExistingAIProjectResourceId)) {
  parent: aiProject
  name: applicationInsightsName
  properties: {
    category: 'AppInsights'
    target: applicationInsightsId
    authType: 'ApiKey'
    isSharedToAll: true
    isDefault: true
    credentials: {
      key: applicationInsightsInstrumentationKey
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: applicationInsightsId
    }
  }
}

@batchSize(1)
resource aiServicesDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-12-01' = [for aiModeldeployment in aiModelDeployments: if (empty(azureExistingAIProjectResourceId)) {
  parent: aiServices
  name: aiModeldeployment.name
  properties: {
    model: {
      format: 'OpenAI'
      name: aiModeldeployment.model
      version: !empty(aiModeldeployment.version) ? aiModeldeployment.version : null
    }
    raiPolicyName: aiModeldeployment.raiPolicyName
  }
  sku: {
    name: aiModeldeployment.sku.name
    capacity: aiModeldeployment.sku.capacity
  }
  dependsOn: [
    aiProject
  ]
}]

// ========== Outputs ========== //

@description('The endpoint URL for the Azure OpenAI service.')
output aiServicesTarget string = !empty(existingOpenAIEndpoint) ? existingOpenAIEndpoint : aiServices.properties.endpoints['OpenAI Language Model Instance API']

@description('The name of the AI Services account.')
output aiServicesName string = !empty(existingAIServicesName) ? existingAIServicesName : aiServices.name

@description('The name of the AI Foundry project.')
output aiProjectName string = !empty(existingAIProjectName) ? existingAIProjectName : aiProject.name

@description('The endpoint URL for the AI Foundry project.')
output projectEndpoint string = !empty(existingProjEndpoint) ? existingProjEndpoint : aiProject.properties.endpoints['AI Foundry API']

@description('The resource ID of the AI Foundry account.')
output aiFoundryResourceId string = !empty(azureExistingAIProjectResourceId) ? azureExistingAIProjectResourceId : aiServices.id

@description('The principal ID of the AI Foundry project managed identity.')
output aiProjectPrincipalId string = !empty(existingAIProjectName) ? assignFoundryRoleToMIExisting.outputs.aiProjectPrincipalId : aiProject.identity.principalId

@description('The resource ID of the AI Services account.')
output aiServicesId string = !empty(azureExistingAIProjectResourceId) ? existingAiServices.id : aiServices.id
