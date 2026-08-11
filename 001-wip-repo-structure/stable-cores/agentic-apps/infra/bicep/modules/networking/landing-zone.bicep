targetScope = 'resourceGroup'

@description('Solution suffix used for deterministic resource names.')
param solutionName string

@description('Azure region for landing-zone resources.')
param location string

@description('Virtual network address space.')
param addressPrefix string = '10.0.0.0/16'

@description('Log Analytics workspace resource ID for diagnostics.')
param logAnalyticsWorkspaceResourceId string

@description('Tags applied to landing-zone resources.')
param tags object = {}

var networkSecurityGroupDefinitions = [
  {
    name: 'nsg-app-${solutionName}'
    rules: [{
      name: 'deny-rdp-ssh-outbound'
      properties: {
        priority: 200
        direction: 'Outbound'
        access: 'Deny'
        protocol: 'Tcp'
        sourcePortRange: '*'
        destinationPortRanges: ['22', '3389']
        sourceAddressPrefix: 'VirtualNetwork'
        destinationAddressPrefix: '*'
      }
    }]
  }
  {
    name: 'nsg-private-endpoints-${solutionName}'
    rules: []
  }
  {
    name: 'nsg-bastion-${solutionName}'
    rules: [
      {
        name: 'allow-bastion-https-inbound'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: 'Internet'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'allow-bastion-management-inbound'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: 'GatewayManager'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
]

resource networkSecurityGroups 'Microsoft.Network/networkSecurityGroups@2024-05-01' = [for definition in networkSecurityGroupDefinitions: {
  name: definition.name
  location: location
  tags: tags
  properties: { securityRules: definition.rules }
}]

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2024-05-01' = {
  name: 'vnet-${solutionName}'
  location: location
  tags: tags
  properties: {
    addressSpace: { addressPrefixes: [addressPrefix] }
    subnets: [
      {
        name: 'applications'
        properties: {
          addressPrefix: '10.0.1.0/24'
          networkSecurityGroup: { id: networkSecurityGroups[0].id }
          delegations: [{
            name: 'app-service-delegation'
            properties: { serviceName: 'Microsoft.Web/serverFarms' }
          }]
        }
      }
      {
        name: 'private-endpoints'
        properties: {
          addressPrefix: '10.0.2.0/24'
          networkSecurityGroup: { id: networkSecurityGroups[1].id }
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: 'AzureBastionSubnet'
        properties: {
          addressPrefix: '10.0.3.0/26'
          networkSecurityGroup: { id: networkSecurityGroups[2].id }
        }
      }
    ]
  }
}

var privateDnsZoneNames = [
  'privatelink.cognitiveservices.azure.com'
  'privatelink.services.ai.azure.com'
  'privatelink.search.windows.net'
  'privatelink.blob.core.windows.net'
  'privatelink.documents.azure.com'
  'privatelink.azurewebsites.net'
  'privatelink.azurecr.io'
]

resource privateDnsZones 'Microsoft.Network/privateDnsZones@2024-06-01' = [for zoneName in privateDnsZoneNames: {
  name: zoneName
  location: 'global'
  tags: tags
}]

resource privateDnsLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (zoneName, index) in privateDnsZoneNames: {
  parent: privateDnsZones[index]
  name: 'link-${solutionName}-${index}'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: { id: virtualNetwork.id }
  }
}]

resource keyVault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: take('kv-${solutionName}', 24)
  location: location
  tags: tags
  properties: {
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enablePurgeProtection: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    publicNetworkAccess: 'Disabled'
    sku: { family: 'A', name: 'standard' }
  }
}

resource bastionPublicIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: 'pip-bastion-${solutionName}'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: { publicIPAllocationMethod: 'Static' }
}

resource bastionHost 'Microsoft.Network/bastionHosts@2024-05-01' = {
  name: 'bas-${solutionName}'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: {
    disableCopyPaste: true
    enableIpConnect: true
    ipConfigurations: [{
      name: 'default'
      properties: {
        privateIPAllocationMethod: 'Dynamic'
        publicIPAddress: { id: bastionPublicIp.id }
        subnet: { id: resourceId('Microsoft.Network/virtualNetworks/subnets', virtualNetwork.name, 'AzureBastionSubnet') }
      }
    }]
  }
}

resource virtualNetworkDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceResourceId)) {
  scope: virtualNetwork
  name: 'send-to-log-analytics'
  properties: {
    workspaceId: logAnalyticsWorkspaceResourceId
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
}

output virtualNetworkResourceId string = virtualNetwork.id
output privateEndpointSubnetResourceId string = resourceId('Microsoft.Network/virtualNetworks/subnets', virtualNetwork.name, 'private-endpoints')
output keyVaultResourceId string = keyVault.id
