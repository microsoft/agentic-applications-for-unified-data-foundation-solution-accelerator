// ========== ai-foundry.bicep ========== //
// Creates NEW Azure AI Services account, AI Foundry project, model deployments,
// and the Application Insights connection.
// For existing projects: only computes endpoint/name outputs (setup is handled by existing-project-setup.bicep).

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

// Derived vars for existing project outputs
var existingOpenAIEndpoint = !empty(azureExistingAIProjectResourceId) ? format('https://{0}.openai.azure.com/', split(azureExistingAIProjectResourceId, '/')[8]) : ''
var existingProjEndpoint = !empty(azureExistingAIProjectResourceId) ? format('https://{0}.services.ai.azure.com/api/projects/{1}', split(azureExistingAIProjectResourceId, '/')[8], split(azureExistingAIProjectResourceId, '/')[10]) : ''
var existingAIServicesName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[8] : ''
var existingAIProjectName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[10] : ''
var existingAIServiceSubscription = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[2] : subscription().subscriptionId
var existingAIServiceResourceGroup = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[4] : resourceGroup().name

// ========== AI Services (NEW only) ========== //

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

// ========== AI Project (NEW only) ========== //

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

// ========== Application Insights Connection (NEW only) ========== //

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

// ========== Model Deployments (NEW only) ========== //

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

@description('The principal ID of the AI Foundry project managed identity (for NEW projects only; existing projects get this from existing-project-setup).')
output aiProjectPrincipalId string = empty(azureExistingAIProjectResourceId) ? aiProject.identity.principalId : ''

@description('The resource ID of the AI Services account.')
output aiServicesId string = !empty(azureExistingAIProjectResourceId) ? resourceId(existingAIServiceSubscription, existingAIServiceResourceGroup, 'Microsoft.CognitiveServices/accounts', existingAIServicesName) : aiServices.id

@description('The AI model deployments array (for passing to existing-project-setup).')
output aiModelDeployments array = aiModelDeployments
