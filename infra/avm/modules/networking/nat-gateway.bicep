// ============================================================================
// Module: NAT Gateway
// Description: AVM wrapper for Azure NAT Gateway with Public IP
// AVM Module: avm/res/network/nat-gateway
// ============================================================================

@description('Solution name suffix used to derive the resource name.')
param solutionName string

var name = 'natgw-${solutionName}'

@description('Azure region for the resource.')
param location string

@description('Tags to apply to the resource.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for module.')
param enableTelemetry bool = true

@description('Idle timeout in minutes for the NAT Gateway.')
param idleTimeoutInMinutes int = 10

@description('Availability zones for the NAT Gateway public IP. Pass empty array to disable zone redundancy.')
param zones array = []

// ============================================================================
// AVM Module Deployment
// ============================================================================
module natGateway 'br/public:avm/res/network/nat-gateway:1.2.1' = {
  name: take('avm.res.network.nat-gateway.${name}', 64)
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    zone: 0
    idleTimeoutInMinutes: idleTimeoutInMinutes
    publicIPAddressObjects: [
      {
        name: 'pip-${name}'
        skuName: 'Standard'
        publicIPAllocationMethod: 'Static'
        zones: zones
        tags: tags
      }
    ]
  }
}

// ============================================================================
// Outputs
// ============================================================================
@description('Resource ID of the NAT Gateway.')
output resourceId string = natGateway.outputs.resourceId

@description('Name of the NAT Gateway.')
output name string = natGateway.outputs.name
