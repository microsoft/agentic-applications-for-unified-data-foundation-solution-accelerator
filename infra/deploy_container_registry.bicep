targetScope = 'resourceGroup'

@description('The environment name used to generate unique resource names.')
param environmentName string

@description('The Azure region where the container registry will be deployed.')
param solutionLocation string = resourceGroup().location

var uniqueId = toLower(uniqueString(subscription().id, environmentName, solutionLocation))
var solutionName = 'da${padLeft(take(uniqueId, 12), 12, '0')}'
var abbrs = loadJsonContent('./abbreviations.json')
var containerRegistryName = '${abbrs.containers.containerRegistry}${solutionName}'
var containerRegistryNameCleaned = replace(containerRegistryName, '-', '')
 
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2025-11-01' = {
  name: containerRegistryName
  location: solutionLocation
  sku: {
    name: 'Premium'
  }
  properties: {
    dataEndpointEnabled: false
    networkRuleBypassOptions: 'AzureServices'
    networkRuleSet: {
      defaultAction: 'Allow'
    }
    policies: {
      quarantinePolicy: {
        status: 'disabled'
      }
      retentionPolicy: {
        status: 'enabled'
        days: 7
      }
      trustPolicy: {
        status: 'disabled'
        type: 'Notary'
      }
    }
    publicNetworkAccess: 'Enabled'
    zoneRedundancy: 'Disabled'
  }
}
 
@description('The name of the created container registry (without hyphens).')
output createdAcrName string = containerRegistryNameCleaned

@description('The resource ID of the container registry.')
output createdAcrId string = containerRegistry.id
 