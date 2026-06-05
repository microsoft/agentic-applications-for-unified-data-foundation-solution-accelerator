// ============================================================================
// Test: Virtual Machine with Entra ID Authentication
// Deploys VNet + NAT Gateway + Bastion + VM to validate Entra ID login via Bastion
// ============================================================================

targetScope = 'resourceGroup'

@description('Solution name for resource naming.')
param solutionName string

@description('Azure region.')
param location string = resourceGroup().location

// ============================================================================
// Variables
// ============================================================================
var tags = { Purpose: 'VM-Entra-ID-Test' }
var deployerInfo = deployer()
var deployingUserPrincipalId = deployerInfo.objectId
var deployingUserPrincipalType = 'User'
var logAnalyticsWorkspaceId = '/subscriptions/41e8dded-503c-48ed-ab78-0ad67715bdd9/resourcegroups/rg-law-test/providers/microsoft.operationalinsights/workspaces/law-cross-sub-test'

// ============================================================================
// NAT Gateway — provides outbound internet for jumpbox VM (required for AAD Join)
// ============================================================================
module natGateway './modules/networking/nat-gateway.bicep' = {
  name: 'test-nat-gateway'
  params: {
    solutionName: solutionName
    location: location
    tags: tags
  }
}

// ============================================================================
// Virtual Network
// ============================================================================
module vnet './modules/networking/virtual-network.bicep' = {
  name: 'test-vnet'
  params: {
    solutionName: solutionName
    location: location
    tags: tags
    addressPrefixes: ['10.0.0.0/16']
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    resourceSuffix: solutionName
    subnets: [
      {
        name: 'administration'
        addressPrefixes: ['10.0.0.0/27']
        natGatewayResourceId: natGateway.outputs.resourceId
        networkSecurityGroup: {
          name: 'nsg-administration'
          securityRules: []
        }
      }
      {
        name: 'AzureBastionSubnet'
        addressPrefixes: ['10.0.0.64/26']
        networkSecurityGroup: {
          name: 'nsg-bastion'
          securityRules: [
            {
              name: 'AllowGatewayManager'
              properties: {
                access: 'Allow'
                direction: 'Inbound'
                priority: 2702
                protocol: '*'
                sourcePortRange: '*'
                destinationPortRange: '443'
                sourceAddressPrefix: 'GatewayManager'
                destinationAddressPrefix: '*'
              }
            }
            {
              name: 'AllowHttpsInBound'
              properties: {
                access: 'Allow'
                direction: 'Inbound'
                priority: 2703
                protocol: '*'
                sourcePortRange: '*'
                destinationPortRange: '443'
                sourceAddressPrefix: 'Internet'
                destinationAddressPrefix: '*'
              }
            }
            {
              name: 'AllowBastionHostCommunicationInbound'
              properties: {
                access: 'Allow'
                direction: 'Inbound'
                priority: 2704
                protocol: '*'
                sourcePortRange: '*'
                destinationPortRanges: ['8080', '5701']
                sourceAddressPrefix: 'VirtualNetwork'
                destinationAddressPrefix: 'VirtualNetwork'
              }
            }
            {
              name: 'AllowSshRdpOutbound'
              properties: {
                access: 'Allow'
                direction: 'Outbound'
                priority: 100
                protocol: '*'
                sourcePortRange: '*'
                destinationPortRanges: ['22', '3389']
                sourceAddressPrefix: '*'
                destinationAddressPrefix: 'VirtualNetwork'
              }
            }
            {
              name: 'AllowAzureCloudOutbound'
              properties: {
                access: 'Allow'
                direction: 'Outbound'
                priority: 110
                protocol: 'Tcp'
                sourcePortRange: '*'
                destinationPortRange: '443'
                sourceAddressPrefix: '*'
                destinationAddressPrefix: 'AzureCloud'
              }
            }
            {
              name: 'AllowBastionHostCommunicationOutbound'
              properties: {
                access: 'Allow'
                direction: 'Outbound'
                priority: 120
                protocol: '*'
                sourcePortRange: '*'
                destinationPortRanges: ['8080', '5701']
                sourceAddressPrefix: 'VirtualNetwork'
                destinationAddressPrefix: 'VirtualNetwork'
              }
            }
            {
              name: 'AllowGetSessionInformation'
              properties: {
                access: 'Allow'
                direction: 'Outbound'
                priority: 130
                protocol: '*'
                sourcePortRange: '*'
                destinationPortRange: '80'
                sourceAddressPrefix: '*'
                destinationAddressPrefix: 'Internet'
              }
            }
          ]
        }
      }
    ]
  }
}

// ============================================================================
// Bastion Host
// ============================================================================
module bastion './modules/networking/bastion-host.bicep' = {
  name: 'test-bastion'
  params: {
    solutionName: solutionName
    location: location
    tags: tags
    virtualNetworkResourceId: vnet.outputs.resourceId
  }
}

// ============================================================================
// Virtual Machine (Jumpbox) — Entra ID Authentication
// ============================================================================
module vm './modules/compute/virtual-machine.bicep' = {
  name: 'test-virtual-machine'
  params: {
    solutionName: solutionName
    location: location
    tags: tags
    adminUsername: 'testvmuser'
    adminPassword: 'Vm!${uniqueString(subscription().subscriptionId, solutionName)}${guid(subscription().subscriptionId, solutionName, 'vm-admin-password')}'
    subnetResourceId: vnet.outputs.administrationSubnetResourceId
    deployingUserPrincipalId: deployingUserPrincipalId
    deployingUserPrincipalType: deployingUserPrincipalType
    roleAssignments: [
      {
        roleDefinitionIdOrName: '1c0163c0-47e6-4577-8991-ea5c82e286e4' // Virtual Machine Administrator Login
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
    ]
  }
}

// ============================================================================
// Outputs
// ============================================================================
output vmName string = vm.outputs.name
output vmResourceId string = vm.outputs.resourceId
output bastionName string = bastion.outputs.name
output natGatewayName string = natGateway.outputs.name
