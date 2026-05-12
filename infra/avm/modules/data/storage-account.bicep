// ============================================================================
// Module: Storage Account
// Description: AVM wrapper for Azure Storage Account with WAF alignment
// AVM Module: avm/res/storage/storage-account:0.19.0
// WAF: https://learn.microsoft.com/azure/well-architected/service-guides/storage-accounts
// ============================================================================

@description('Name of the Storage Account.')
param storageAccountName string

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Storage account SKU.')
param skuName string = 'Standard_LRS'

@description('Storage account kind.')
param kind string = 'StorageV2'

@description('Access tier.')
@allowed(['Hot', 'Cool'])
param accessTier string = 'Hot'

@description('Allow blob public access.')
param allowBlobPublicAccess bool = false

@description('Allow shared key access.')
param allowSharedKeyAccess bool = true

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Blob containers to create.')
param containers array = [
  {
    name: 'default'
    publicAccess: 'None'
  }
]

// --- WAF: Monitoring ---
@description('Diagnostic settings for monitoring.')
param diagnosticSettings array = []

// --- WAF: Private Networking ---
@description('Public network access setting.')
param publicNetworkAccess string = 'Enabled'

@description('Network ACLs for the storage account.')
param networkAcls object = {
  defaultAction: 'Allow'
  bypass: 'AzureServices'
}

@description('Private endpoint configurations.')
param privateEndpoints array = []

// --- Role Assignments ---
@description('Optional. Array of role assignments to create on the Storage Account.')
param roleAssignments array = []

// ============================================================================
// AVM Module Deployment
// ============================================================================
module storage 'br/public:avm/res/storage/storage-account:0.19.0' = {
  name: 'deploy-storage-${storageAccountName}'
  params: {
    name: storageAccountName
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    skuName: skuName
    kind: kind
    accessTier: accessTier
    allowBlobPublicAccess: allowBlobPublicAccess
    allowSharedKeyAccess: allowSharedKeyAccess
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: publicNetworkAccess
    networkAcls: networkAcls
    blobServices: {
      containers: [for container in containers: {
        name: container.name
        publicAccess: container.publicAccess
      }]
      diagnosticSettings: !empty(diagnosticSettings) ? diagnosticSettings : []
    }
    diagnosticSettings: !empty(diagnosticSettings) ? diagnosticSettings : []
    privateEndpoints: privateEndpoints
    roleAssignments: !empty(roleAssignments) ? roleAssignments : []
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the Storage Account.')
output resourceId string = storage.outputs.resourceId

@description('Name of the Storage Account.')
output name string = storage.outputs.name

@description('Primary blob endpoint.')
output blobEndpoint string = storage.outputs.primaryBlobEndpoint

@description('Service endpoints.')
output serviceEndpoints object = storage.outputs.serviceEndpoints
