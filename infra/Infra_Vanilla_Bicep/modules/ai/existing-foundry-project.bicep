@description('Name of the existing Azure AI Services account')
param aiServicesName string

@description('Name of the existing AI Project under the AI Services account')
param aiProjectName string

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: aiServicesName
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-12-01' existing = {
  name: aiProjectName
  parent: aiServices
}


// Outputs: AI Services Account

@description('The Azure region of the AI Services account.')
output location string = aiServices.location

@description('The SKU name of the AI Services account.')
output skuName string = aiServices.sku.name

@description('The kind of the AI Services account.')
output kind string = aiServices.kind

@description('Whether project management is allowed on the AI Services account.')
output allowProjectManagement bool = aiServices.properties.allowProjectManagement

@description('The custom subdomain name of the AI Services account.')
output customSubDomainName string = aiServices.properties.customSubDomainName

@description('The public network access setting of the AI Services account.')
output publicNetworkAccess string = aiServices.properties.publicNetworkAccess

@description('The default network action of the AI Services account.')
output defaultNetworkAction string = aiServices.properties.networkAcls.defaultAction

@description('The IP rules configured for the AI Services account.')
output ipRules array = aiServices.properties.networkAcls.ipRules

@description('The virtual network rules configured for the AI Services account.')
output vnetRules array = aiServices.properties.networkAcls.virtualNetworkRules

// Outputs: AI Project

@description('The Azure region of the AI Project.')
output projectLocation string = aiProject.location

@description('The kind of the AI Project.')
output projectKind string = aiProject.kind

@description('The provisioning state of the AI Project.')
output projectProvisioningState string = aiProject.properties.provisioningState
