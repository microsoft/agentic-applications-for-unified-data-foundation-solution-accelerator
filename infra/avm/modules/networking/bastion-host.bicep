// ============================================================================
// Module: Bastion Host
// Description: AVM wrapper for Azure Bastion Host
// AVM Module: avm/res/network/bastion-host
// ============================================================================

@description('Name of the Bastion Host.')
param name string

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Resource ID of the virtual network.')
param virtualNetworkResourceId string

@description('Optional. Diagnostic settings for the resource.')
param diagnosticSettings array?

@description('SKU name for the Bastion Host.')
param skuName string = 'Standard'

@description('Number of scale units.')
param scaleUnits int = 4

@description('Disable copy/paste functionality.')
param disableCopyPaste bool = true

@description('Enable file copy functionality.')
param enableFileCopy bool = false

@description('Enable IP Connect functionality.')
param enableIpConnect bool = false

@description('Enable shareable link functionality.')
param enableShareableLink bool = false

@description('Optional. Public IP address configuration.')
param publicIPAddressObject object?

// ============================================================================
// AVM Module Deployment
// ============================================================================
module bastionHost 'br/public:avm/res/network/bastion-host:0.8.2' = {
  name: 'deploy-bastion-${name}'
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    skuName: skuName
    virtualNetworkResourceId: virtualNetworkResourceId
    availabilityZones: []
    publicIPAddressObject: publicIPAddressObject
    disableCopyPaste: disableCopyPaste
    enableFileCopy: enableFileCopy
    enableIpConnect: enableIpConnect
    enableShareableLink: enableShareableLink
    scaleUnits: scaleUnits
    diagnosticSettings: diagnosticSettings
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the Bastion Host.')
output resourceId string = bastionHost.outputs.resourceId

@description('Name of the Bastion Host.')
output name string = bastionHost.outputs.name
