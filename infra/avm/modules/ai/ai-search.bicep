// ============================================================================
// Module: AI Search
// Description: AVM wrapper for Azure AI Search with WAF alignment
// AVM Module: avm/res/search/search-service:0.9.1
// WAF: https://learn.microsoft.com/azure/well-architected/service-guides/azure-cognitive-search
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

var searchServiceName = 'srch-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('SKU name for the search service.')
@allowed(['free', 'basic', 'standard', 'standard2', 'standard3', 'storage_optimized_l1', 'storage_optimized_l2'])
param skuName string = 'basic'

@description('Number of replicas.')
param replicaCount int = 1

@description('Number of partitions.')
param partitionCount int = 1

@description('Hosting mode.')
@allowed(['default', 'highDensity'])
param hostingMode string = 'default'

@description('Semantic search tier.')
@allowed(['disabled', 'free', 'standard'])
param semanticSearch string = 'free'

@description('Whether to disable local authentication.')
param disableLocalAuth bool = true

@description('Managed identity type for the search service.')
param managedIdentityType string = 'SystemAssigned'

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

// --- WAF: Monitoring ---
@description('Diagnostic settings for monitoring.')
param diagnosticSettings array = []

// --- WAF: Private Networking ---
@description('Public network access setting.')
param publicNetworkAccess string = 'Enabled'

@description('Private endpoint configurations.')
param privateEndpoints array = []

// --- Role Assignments ---
@description('Optional. Array of role assignments to create on the AI Search service.')
param roleAssignments array = []

// ============================================================================
// AVM Module Deployment
// ============================================================================
module searchService 'br/public:avm/res/search/search-service:0.9.1' = {
  name: take('avm.res.search.search-service.${searchServiceName}', 64)
  params: {
    name: searchServiceName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    sku: skuName
    replicaCount: replicaCount
    partitionCount: partitionCount
    hostingMode: hostingMode
    semanticSearch: semanticSearch
    disableLocalAuth: disableLocalAuth
    publicNetworkAccess: publicNetworkAccess
    managedIdentities: {
      systemAssigned: managedIdentityType == 'SystemAssigned'
    }
    diagnosticSettings: !empty(diagnosticSettings) ? diagnosticSettings : []
    privateEndpoints: privateEndpoints
    roleAssignments: !empty(roleAssignments) ? roleAssignments : []
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the AI Search service.')
output resourceId string = searchService.outputs.resourceId

@description('Name of the AI Search service.')
output name string = searchService.outputs.name

@description('Endpoint URL of the AI Search service.')
output endpoint string = 'https://${searchServiceName}.search.windows.net'

@description('System-assigned identity principal ID.')
output identityPrincipalId string = searchService.outputs.?systemAssignedMIPrincipalId ?? ''
