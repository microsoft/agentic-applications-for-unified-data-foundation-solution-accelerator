// ========== deploy_fabric_capacity.bicep ========== //
// Deploys a Microsoft Fabric capacity resource.

@description('Name of the Fabric capacity resource.')
param capacityName string

@description('Location for the Fabric capacity resource.')
param solutionLocation string

@description('SKU name for the Fabric capacity (e.g., F2, F4, F8, F16, F32, F64).')
@allowed([
  'F2'
  'F4'
  'F8'
  'F16'
  'F32'
  'F64'
])
param skuName string = 'F8'

@description('Array of admin member UPNs or object IDs for the Fabric capacity.')
param adminMembers array

resource fabricCapacity 'Microsoft.Fabric/capacities@2023-11-01' = {
  name: capacityName
  location: solutionLocation
  sku: {
    name: skuName
    tier: 'Fabric'
  }
  properties: {
    administration: {
      members: adminMembers
    }
  }
}

@description('Resource ID of the deployed Fabric capacity.')
output capacityId string = fabricCapacity.id

@description('Name of the deployed Fabric capacity.')
output capacityName string = fabricCapacity.name
