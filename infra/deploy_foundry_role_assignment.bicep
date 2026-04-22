@description('The principal ID to assign the role to.')
param principalId string = ''

@description('The resource ID of the role definition to assign.')
param roleDefinitionId string

@description('A unique name for the role assignment.')
param roleAssignmentName string = ''

@description('The name of the AI Services account.')
param aiServicesName string

@description('The name of the AI project under the AI Services account.')
param aiProjectName string = ''

@description('The Azure region for the AI Services account.')
param aiLocation string=''

@description('The kind of AI Services account (e.g., AIServices).')
param aiKind string=''

@description('The SKU name for the AI Services account.')
param aiSkuName string=''

@description('Whether to enable system-assigned managed identity on the AI Services account.')
param enableSystemAssignedIdentity bool = false

@description('The custom subdomain name for the AI Services account.')
param customSubDomainName string = ''

@description('The public network access setting for the AI Services account.')
param publicNetworkAccess string = ''

@description('The default network action for the AI Services account.')
param defaultNetworkAction string = ''

@description('Virtual network rules for the AI Services account.')
param vnetRules array = []

@description('IP rules for the AI Services account.')
param ipRules array = []

@description('Array of AI model deployments to create.')
param aiModelDeployments array = []

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = if (!enableSystemAssignedIdentity) {
  name: aiServicesName
}

resource aiServicesWithIdentity 'Microsoft.CognitiveServices/accounts@2025-12-01' = if (enableSystemAssignedIdentity) {
  name: aiServicesName
  location: aiLocation
  kind: aiKind
  sku: {
    name: aiSkuName
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: customSubDomainName 
    networkAcls: {
      defaultAction: defaultNetworkAction
      virtualNetworkRules: vnetRules
      ipRules: ipRules
    }
    publicNetworkAccess: publicNetworkAccess

  }
}

@batchSize(1)
resource aiServicesDeployments 'Microsoft.CognitiveServices/accounts/deployments@2025-12-01' = [for aiModeldeployment in aiModelDeployments: if (!empty(aiModelDeployments)) {
  parent: aiServicesWithIdentity
  name: aiModeldeployment.name
  properties: {
    model: {
      format: 'OpenAI'
      name: aiModeldeployment.model
    }
    raiPolicyName: aiModeldeployment.raiPolicyName
  }
  sku:{
    name: aiModeldeployment.sku.name
    capacity: aiModeldeployment.sku.capacity
  }
}]

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' existing = if (!empty(aiProjectName) && !enableSystemAssignedIdentity) {
  name: aiProjectName
  parent: aiServices
}

resource aiProjectWithIdentity 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' = if (!empty(aiProjectName) && enableSystemAssignedIdentity) {
  name: aiProjectName
  parent: aiServicesWithIdentity
  location: aiLocation
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

// Role Assignment to AI Services
resource roleAssignmentToFoundryExisting 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableSystemAssignedIdentity) {
  name: roleAssignmentName
  scope: aiServicesWithIdentity
  properties: {
    roleDefinitionId: roleDefinitionId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

resource roleAssignmentToFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!enableSystemAssignedIdentity) {
  name: roleAssignmentName
  scope: aiServices
  properties: {
    roleDefinitionId: roleDefinitionId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

// ========== Outputs ==========

@description('The principal ID of the AI Services system-assigned managed identity.')
output aiServicesPrincipalId string = enableSystemAssignedIdentity
  ? aiServicesWithIdentity.identity.principalId
  : aiServices.identity.principalId

@description('The principal ID of the AI Project system-assigned managed identity.')
output aiProjectPrincipalId string = !empty(aiProjectName)
  ? (enableSystemAssignedIdentity
      ? aiProjectWithIdentity.identity.principalId
      : aiProject.identity.principalId)
  : ''
