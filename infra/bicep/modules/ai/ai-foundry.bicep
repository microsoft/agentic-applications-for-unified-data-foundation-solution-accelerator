// ========== ai-foundry.bicep ========== //
// Creates NEW Azure AI Services account, AI Foundry project, model deployments,
// and project connections (AppInsights, Search, Storage).

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

@description('The resource ID of the Application Insights instance (from monitoring module).')
param applicationInsightsId string

@description('The instrumentation key of the Application Insights instance (from monitoring module).')
param applicationInsightsInstrumentationKey string

@description('When true, deploys additional resources for workshop scenarios including AI Search and Storage.')
param isWorkshop bool = false

@description('The endpoint URL of the AI Search service (workshop only).')
param aiSearchTarget string = ''

@description('The resource ID of the AI Search service (workshop only).')
param aiSearchId string = ''

@description('The connection name for the AI Search service (workshop only).')
param aiSearchConnectionName string = ''

@description('The primary blob endpoint of the storage account (workshop only).')
param storageBlobEndpoint string = ''

@description('The resource ID of the storage account (workshop only).')
param storageAccountId string = ''

@description('The name of the storage account (workshop only).')
param storageAccountName string = ''

var aiFoundryName = 'aif-${solutionName}'
var applicationInsightsName = 'appi-${solutionName}'
var location = solutionLocation
var aiProjectName = 'proj-${solutionName}'

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

// ========== AI Foundry Account ========== //

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' = {
  name: aiFoundryName
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
    customSubDomainName: aiFoundryName
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

// ========== AI Project ========== //

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' = {
  parent: aiServices
  name: aiProjectName
  location: solutionLocation
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

// ========== Application Insights Connection ========== //

resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = {
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

// ========== AI Search Connection (workshop only) ========== //

resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (isWorkshop) {
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

// ========== Storage Connection (workshop only) ========== //

resource storageConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01' = if (isWorkshop) {
  parent: aiProject
  name: 'storage-connection'
  properties: {
    category: 'AzureBlob'
    target: storageBlobEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ResourceId: storageAccountId
      AccountName: storageAccountName
      ContainerName: 'default'
    }
  }
}

// ========== Model Deployments ========== //

@batchSize(1)
resource aiServicesDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-12-01' = [for aiModeldeployment in aiModelDeployments: {
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
output aiFoundryEndpoint string = aiServices.properties.endpoints['OpenAI Language Model Instance API']

@description('The name of the AI Foundry account.')
output aiFoundryName string = aiServices.name

@description('The name of the AI Foundry project.')
output aiProjectName string = aiProject.name

@description('The endpoint URL for the AI Foundry project.')
output projectEndpoint string = aiProject.properties.endpoints['AI Foundry API']

@description('The resource ID of the AI Foundry account.')
output aiFoundryResourceId string = aiServices.id

@description('The principal ID of the AI Foundry project managed identity.')
output aiProjectPrincipalId string = aiProject.identity.principalId

@description('The resource ID of the AI Search connection (workshop only).')
output aiSearchConnectionId string = isWorkshop ? searchConnection.id : ''
