// ============================================================================
// Module: AI Services
// Description: AVM wrapper for Azure AI Services (Cognitive Services) account
// AVM Module: avm/res/cognitive-services/account
// WAF: https://learn.microsoft.com/azure/well-architected/service-guides/azure-openai
// ============================================================================

@description('Name of the AI Services account.')
param aiServicesName string

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('SKU name for the AI Services account.')
param skuName string = 'S0'

@description('Whether to disable local authentication.')
param disableLocalAuth bool = true

@description('Whether to allow project management (AI Foundry).')
param allowProjectManagement bool = true

@description('Public network access setting.')
param publicNetworkAccess string = 'Enabled'

// --- WAF: Identity ---
@description('User-assigned managed identity resource IDs to attach.')
param userAssignedIdentityResourceIds array = []

// --- WAF: Monitoring ---
@description('Optional. Diagnostic settings for the resource.')
param diagnosticSettings array?

// --- Model Deployments ---
@description('Optional. Array of model deployments to create.')
param deployments array?

// --- Role Assignments ---
@description('Optional. Array of role assignments to create on the AI Services account.')
param roleAssignments array?

// ============================================================================
// AVM Module Deployment
// ============================================================================
module aiServices 'br/public:avm/res/cognitive-services/account:0.13.2' = {
  name: 'deploy-ai-services-${aiServicesName}'
  params: {
    name: aiServicesName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    sku: skuName
    kind: 'AIServices'
    disableLocalAuth: disableLocalAuth
    allowProjectManagement: allowProjectManagement
    customSubDomainName: aiServicesName
    networkAcls: {
      defaultAction: 'Allow'
      virtualNetworkRules: []
      ipRules: []
    }
    publicNetworkAccess: publicNetworkAccess
    managedIdentities: !empty(userAssignedIdentityResourceIds) ? {
      userAssignedResourceIds: userAssignedIdentityResourceIds
    } : null
    diagnosticSettings: diagnosticSettings
    deployments: deployments
    roleAssignments: roleAssignments
    privateEndpoints: []
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the AI Services account.')
output resourceId string = aiServices.outputs.resourceId

@description('Name of the AI Services account.')
output name string = aiServices.outputs.name

@description('Endpoint of the AI Services account.')
output endpoint string = aiServices.outputs.endpoint
