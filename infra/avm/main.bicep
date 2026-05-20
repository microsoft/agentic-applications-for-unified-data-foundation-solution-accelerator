// ============================================================================
// main.bicep — Orchestrator
// Description: Pure orchestrator for Agentic Applications for UDF
//              All resource names are derived from params — no hardcoded names.
//              This file only calls modules; no inline resource definitions.
//              Supports WAF-aligned deployment via feature flags.
// ============================================================================
targetScope = 'resourceGroup'

// ============================================================================
// Parameters — Core
// ============================================================================

@minLength(3)
@maxLength(20)
@description('Optional. A unique application/solution name used as base for all resource naming.')
param solutionName string = 'agenticappudf'

@maxLength(5)
@description('Optional. A unique text suffix appended to resource names for uniqueness.')
param solutionUniqueText string = substring(uniqueString(subscription().id, resourceGroup().name, solutionName), 0, 5)

@description('Optional. Primary Azure region for resource deployment.')
param location string = resourceGroup().location

@description('Optional. Secondary location for database resources.')
param secondaryLocation string = 'eastus2'

@description('Optional. Tags to apply to all resources.')
param tags object = {}

@description('Optional. Enable/Disable usage telemetry for AVM modules.')
param enableTelemetry bool = true

// ============================================================================
// Parameters — WAF Feature Flags
// ============================================================================

@description('Optional. Enable monitoring for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enableMonitoring bool = false

@description('Optional. Enable private networking for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enablePrivateNetworking bool = false

@description('Optional. Enable scalability for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enableScalability bool = false

@description('Optional. Enable redundancy for applicable resources, aligned with the Well Architected Framework recommendations. Defaults to false.')
param enableRedundancy bool = false

// ============================================================================
// Parameters — VM (applicable when enablePrivateNetworking = true)
// ============================================================================

@secure()
@description('Optional. The user name for the administrator account of the virtual machine. Allows to customize credentials if `enablePrivateNetworking` is set to true.')
param vmAdminUsername string?

@secure()
@description('Optional. The password for the administrator account of the virtual machine. Allows to customize credentials if `enablePrivateNetworking` is set to true.')
param vmAdminPassword string?

@description('Optional. The size of the virtual machine. Defaults to Standard_D2s_v5.')
param vmSize string = 'Standard_D2s_v5'

// ============================================================================
// Parameters — AI Configuration
// ============================================================================

@allowed([
  'australiaeast'
  'eastus'
  'eastus2'
  'francecentral'
  'japaneast'
  'swedencentral'
  'uksouth'
  'westus'
  'westus3'
])
@metadata({
  azd: {
    type: 'location'
    usageName: [
      'OpenAI.GlobalStandard.gpt4.1-mini,100'
      'OpenAI.GlobalStandard.text-embedding-3-small,80'
    ]
  }
})
@description('Required. Location for AI Services and model deployments.')
param azureAiServiceLocation string

@description('Optional. Location for AI Search service deployment.')
param searchServiceLocation string = location

@allowed(['Standard', 'GlobalStandard'])
@description('Optional. GPT model deployment type.')
param deploymentType string = 'GlobalStandard'

@description('Optional. Name of the GPT model to deploy.')
param gptModelName string = 'gpt-4.1-mini'

@description('Optional. Version of the GPT model to deploy.')
param gptModelVersion string = '2025-04-14'

@minValue(10)
@description('Optional. Capacity of the GPT deployment (TPM in thousands).')
param gptDeploymentCapacity int = 150

@description('Optional. Name of the embedding model to deploy.')
@allowed(['text-embedding-3-small'])
param embeddingModel string = 'text-embedding-3-small'

@minValue(10)
@description('Optional. Capacity of the embedding model deployment.')
param embeddingDeploymentCapacity int = 80

@description('Optional. Azure OpenAI API version.')
param azureOpenaiAPIVersion string = '2025-01-01-preview'

@description('Optional. Azure AI Agent API version.')
param azureAiAgentApiVersion string = '2025-05-01'

// ============================================================================
// Parameters — Compute
// ============================================================================

@description('Optional. Docker image tag for app deployments.')
param imageTag string = 'latest_v2'

@description('Optional. Name of the Azure Container Registry.')
param containerRegistryName string = 'dataagentscontainerreg'

@allowed(['python', 'dotnet'])
@description('Optional. Backend runtime stack.')
param backendRuntimeStack string = 'python'

@allowed(['F1', 'D1', 'B1', 'B2', 'B3', 'S1', 'S2', 'S3', 'P1', 'P2', 'P3', 'P1v3', 'P1v4'])
@description('Optional. App Service Plan SKU.')
param appServicePlanSku string = 'B2'

// ============================================================================
// Parameters — Feature Flags
// ============================================================================

@description('Optional. Deploy application components (API, Frontend, Cosmos DB).')
param deployApp bool = true

@description('Optional. Workshop deployment mode with sample data.')
param isWorkshop bool = true

@description('Optional. Azure-only mode (deploy Azure SQL instead of Fabric SQL).')
param azureEnvOnly bool = false

@description('Optional. Enable chat history storage.')
param useChatHistoryEnabled bool = true

@description('Optional. Enable user access token forwarding.')
param useUserAccessToken bool = false

// ============================================================================
// Parameters — Fabric Capacity
// ============================================================================

@description('Optional. Set to true to auto-create a Fabric workspace during post-provision. When false, capacity creation is skipped.')
param createFabricWorkspace bool = false

@description('Optional. Name of an existing Fabric capacity to reuse. If empty, a new capacity is auto-created when conditions are met.')
param azureFabricCapacityName string = ''

@allowed([
  'F2'
  'F4'
  'F8'
  'F16'
  'F32'
  'F64'
  'F128'
  'F256'
  'F512'
  'F1024'
  'F2048'
])
@description('Optional. SKU tier of the Fabric capacity resource.')
param fabricCapacitySku string = 'F2'

@description('Optional. Additional user/service principal object IDs to assign as Fabric Capacity admins.')
param fabricAdminMembers array = []

// ============================================================================
// Parameters — Existing Resources
// ============================================================================

@description('Optional. Resource ID of an existing Log Analytics workspace (empty = create new).')
param existingLogAnalyticsWorkspaceId string = ''

@description('Optional. Resource ID of an existing AI Foundry project (empty = create new).')
param existingFoundryProjectResourceId string = ''

// ============================================================================
// Parameters — Identity
// ============================================================================

@allowed(['User', 'ServicePrincipal'])
@description('Optional. Principal type of the deploying user.')
param deployingUserPrincipalType string = 'User'

// ============================================================================
// Parameters — App Configuration
// ============================================================================

@allowed(['Retail-sales-analysis', 'Insurance-improve-customer-meetings'])
@description('Optional. Industry use case for deployment.')
param usecase string = 'Retail-sales-analysis'

@description('Optional. Primary title in the web app header.')
param appTitlePrimary string = 'Contoso'

@description('Optional. Secondary title in the web app header.')
param appTitleSecondary string = '| Unified Data Analysis Agents'

// ============================================================================
// Variables
// ============================================================================

var solutionSuffix = toLower(trim(replace(replace(replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''), ' ', ''), '*', '')))
var deployerInfo = deployer()
var deployingUserPrincipalId = deployerInfo.objectId
var createdBy = contains(deployerInfo, 'userPrincipalName') ? split(deployerInfo.userPrincipalName, '@')[0] : deployerInfo.objectId
var shouldDeployApp = !isWorkshop || deployApp
var useExistingAIProject = !empty(existingFoundryProjectResourceId)
var useChatHistoryEnabledSetting = useChatHistoryEnabled ? 'True' : 'False'
var useUserAccessTokenSetting = useUserAccessToken ? 'True' : 'False'
var landingText = usecase == 'Retail-sales-analysis' ? 'You can ask questions around sales, products and orders.' : 'You can ask questions around customer policies, claims and communications.'

// Fabric Capacity: create when createFabricWorkspace=true and no existing capacity provided
// Skipped only when isWorkshop=true AND azureEnvOnly=true (no Fabric needed in azure-only workshop mode)
var useExistingFabricCapacity = !empty(azureFabricCapacityName)
var shouldCreateFabricCapacity = !azureEnvOnly && createFabricWorkspace && !useExistingFabricCapacity
var fabricCapacityResourceName = useExistingFabricCapacity ? azureFabricCapacityName : 'fc${solutionSuffix}'
var fabricCapacityDefaultAdmins = contains(deployerInfo, 'userPrincipalName')
  ? [deployerInfo.userPrincipalName]
  : [deployerInfo.objectId]
var fabricTotalAdminMembers = union(fabricCapacityDefaultAdmins, fabricAdminMembers)

// Tags: merge caller-supplied tags with standard metadata (matching old infra)
var existingTags = resourceGroup().tags ?? {}
var resourceTags = union(existingTags, tags, {
  TemplateName: 'Unified Data Analysis Agents'
  CreatedBy: createdBy
  DeploymentName: deployment().name
  Type: enablePrivateNetworking ? 'WAF' : 'Non-WAF'
})

// WAF: Region pairs for redundancy (Log Analytics replication)
var replicaRegionPairs = {
  australiaeast: 'australiasoutheast'
  eastus: 'centralus'
  eastus2: 'centralus'
  francecentral: 'westeurope'
  japaneast: 'eastasia'
  swedencentral: 'northeurope'
  uksouth: 'westeurope'
  westus: 'centralus'
  westus3: 'centralus'
}
var replicaLocation = replicaRegionPairs[location]

// WAF: Region pairs for Cosmos DB zone-redundant HA
var cosmosDbHaRegionPairs = {
  australiaeast: 'uksouth'
  eastus: 'centralus'
  eastus2: 'centralus'
  francecentral: 'westeurope'
  japaneast: 'australiaeast'
  swedencentral: 'northeurope'
  uksouth: 'westeurope'
  westus: 'centralus'
  westus3: 'centralus'
}
var cosmosDbHaLocation = cosmosDbHaRegionPairs[location]

// WAF: Diagnostic settings helper — reused across modules
var monitoringDiagnosticSettings = enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : []

// WAF: Private DNS zones for private endpoints
var privateDnsZones = [
  'privatelink.cognitiveservices.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.services.ai.azure.com'
  'privatelink.documents.azure.com'
  'privatelink.blob.core.windows.net'
  'privatelink.search.windows.net'
  'privatelink.database.windows.net'
]
var dnsZoneIndex = {
  cognitiveServices: 0
  openAI: 1
  aiFoundry: 2
  cosmosDb: 3
  blob: 4
  search: 5
  sqlServer: 6
}

// Resource naming (parameterized — no abbreviations.json dependency)
// Resource names for generic modules are now derived inside each module from solutionName/solutionSuffix.

// Model deployments configuration
var aiModelDeployments = concat([
  {
    name: gptModelName
    model: gptModelName
    sku: { name: deploymentType, capacity: gptDeploymentCapacity }
    version: gptModelVersion
    raiPolicyName: 'Microsoft.Default'
  }
], isWorkshop ? [
  {
    name: embeddingModel
    model: embeddingModel
    sku: { name: 'GlobalStandard', capacity: embeddingDeploymentCapacity }
    version: '1'
    raiPolicyName: 'Microsoft.Default'
  }
] : [])

// ============================================================================
// Resource Group Tags (matching old infra)
// ============================================================================

resource resourceGroupTags 'Microsoft.Resources/tags@2024-11-01' = {
  name: 'default'
  properties: {
    tags: resourceTags
  }
}

// ============================================================================
// Module: Fabric Capacity
// ============================================================================

module fabricCapacity './modules/data/fabric-capacity.bicep' = if (shouldCreateFabricCapacity) {
  name: take('module.fabric-capacity.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    skuName: fabricCapacitySku
    adminMembers: fabricTotalAdminMembers
    tags: resourceTags
    enableTelemetry: enableTelemetry
  }
}

// ============================================================================
// Module: Monitoring
// ============================================================================

var useExistingLogAnalytics = !empty(existingLogAnalyticsWorkspaceId)

// Existing workspace reference (for cross-subscription support)
resource existingLogAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2025-07-01' existing = if (useExistingLogAnalytics) {
  name: split(existingLogAnalyticsWorkspaceId, '/')[8]
  scope: resourceGroup(split(existingLogAnalyticsWorkspaceId, '/')[2], split(existingLogAnalyticsWorkspaceId, '/')[4])
}

module log_analytics './modules/monitoring/log-analytics.bicep' = if (enableMonitoring && !useExistingLogAnalytics) {
  name: take('module.log-analytics.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    retentionInDays: 365
    publicNetworkAccessForIngestion: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    publicNetworkAccessForQuery: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    enableReplication: enableRedundancy
    replicationLocation: enableRedundancy ? replicaLocation : ''
    dailyQuotaGb: enableRedundancy ? '150' : ''
    dataSources: enablePrivateNetworking ? [
      {
        tags: tags
        eventLogName: 'Application'
        eventTypes: [{ eventType: 'Error' }, { eventType: 'Warning' }, { eventType: 'Information' }]
        kind: 'WindowsEvent'
        name: 'applicationEvent'
      }
      {
        counterName: '% Processor Time'
        instanceName: '*'
        intervalSeconds: 60
        kind: 'WindowsPerformanceCounter'
        name: 'windowsPerfCounter1'
        objectName: 'Processor'
      }
    ] : []
  }
}

// Resolve workspace resource ID — existing or new
var logAnalyticsWorkspaceResourceId = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspace.id
  : (enableMonitoring ? log_analytics!.outputs.resourceId : '')

module app_insights './modules/monitoring/app-insights.bicep' = if (enableMonitoring) {
  name: take('module.app-insights.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: azureAiServiceLocation
    tags: tags
    enableTelemetry: enableTelemetry
    workspaceResourceId: logAnalyticsWorkspaceResourceId
    retentionInDays: 365
    disableIpMasking: false
  }
}

// ============================================================================
// Module: Networking (WAF — conditional on enablePrivateNetworking)
// ============================================================================

module virtualNetwork './modules/networking/virtual-network.bicep' = if (enablePrivateNetworking) {
  name: take('module.virtual-network.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    addressPrefixes: ['10.0.0.0/8']
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceResourceId
    resourceSuffix: solutionSuffix
  }
}

// Bastion Host — secure access to jumpbox VM
module bastionHost './modules/networking/bastion-host.bicep' = if (enablePrivateNetworking) {
  name: take('module.bastion-host.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    virtualNetworkResourceId: virtualNetwork!.outputs.resourceId
    publicIPDiagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
  }
}

// WAF: Maintenance Configuration for VM patching
module maintenanceConfiguration './modules/compute/maintenance-configuration.bicep' = if (enablePrivateNetworking) {
  name: take('module.maintenance-configuration.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
  }
}

// WAF: Data Collection Rules for VM monitoring
var dataCollectionRulesLocation = useExistingLogAnalytics
  ? existingLogAnalyticsWorkspace!.location
  : (enableMonitoring ? log_analytics!.outputs.location : location)
module windowsVmDataCollectionRules './modules/monitoring/data-collection-rule.bicep' = if (enablePrivateNetworking && enableMonitoring) {
  name: take('module.data-collection-rule.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: dataCollectionRulesLocation
    tags: tags
    enableTelemetry: enableTelemetry
    logAnalyticsWorkspaceResourceId: logAnalyticsWorkspaceResourceId
  }
}

// WAF: Proximity Placement Group for VM
var virtualMachineAvailabilityZone = 1
module proximityPlacementGroup './modules/compute/proximity-placement-group.bicep' = if (enablePrivateNetworking) {
  name: take('module.proximity-placement-group.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    availabilityZone: virtualMachineAvailabilityZone
    vmSizes: [vmSize]
  }
}

// Jumpbox VM — administration access when private networking is enabled
module virtualMachine './modules/compute/virtual-machine.bicep' = if (enablePrivateNetworking) {
  name: take('module.virtual-machine.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    vmSize: vmSize
    availabilityZone: virtualMachineAvailabilityZone
    adminUsername: vmAdminUsername ?? 'JumpboxAdmin'
    adminPassword: vmAdminPassword ?? 'JumpboxAdminP@ssw0rd1234!'
    subnetResourceId: virtualNetwork!.outputs.administrationSubnetResourceId
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    maintenanceConfigurationResourceId: maintenanceConfiguration!.outputs.resourceId
    proximityPlacementGroupResourceId: proximityPlacementGroup!.outputs.resourceId
    extensionMonitoringAgentConfig: enableMonitoring ? {
      dataCollectionRuleAssociations: [
        {
          dataCollectionRuleResourceId: windowsVmDataCollectionRules!.outputs.resourceId
          name: 'send-${log_analytics!.outputs.name}'
        }
      ]
      enabled: true
      tags: tags
    } : null
  }
}

// Private DNS Zones — one per service, linked to VNet
@batchSize(5)
module privateDnsZoneDeployments './modules/networking/private-dns-zone.bicep' = [
  for (zone, i) in privateDnsZones: if (enablePrivateNetworking) {
    name: take('module.private-dns-zone.${split(zone, '.')[1]}.${solutionName}', 64)
    params: {
      name: zone
      tags: tags
      enableTelemetry: enableTelemetry
      virtualNetworkLinks: [
        {
          name: take('vnetlink-${virtualNetwork!.outputs.name}-${split(zone, '.')[1]}', 80)
          virtualNetworkResourceId: virtualNetwork!.outputs.resourceId
        }
      ]
    }
  }
]

// ============================================================================
// Module: AI Services (conditional — skip if using existing project)
// ============================================================================

// Existing AI Foundry reference (for cross-subscription support when using existing project)
var aiFoundryResourceGroupName = useExistingAIProject
  ? split(existingFoundryProjectResourceId, '/')[4]
  : resourceGroup().name
var aiFoundrySubscriptionId = useExistingAIProject
  ? split(existingFoundryProjectResourceId, '/')[2]
  : subscription().subscriptionId
var aiFoundryResourceName = useExistingAIProject
  ? split(existingFoundryProjectResourceId, '/')[8]
  : aifoundry!.outputs.name

// Construct endpoints from existing resource ID (matching bicep/modules/ai/ai-foundry.bicep)
// Expected format: /subscriptions/.../providers/Microsoft.CognitiveServices/accounts/{account}/projects/{project}
var existingHasProjectSegment = useExistingAIProject && length(split(existingFoundryProjectResourceId, '/')) > 10
var existingOpenAIEndpoint = useExistingAIProject
  ? format('https://{0}.openai.azure.com/', split(existingFoundryProjectResourceId, '/')[8])
  : ''
var existingProjectEndpoint = existingHasProjectSegment
  ? format('https://{0}.services.ai.azure.com/api/projects/{1}', split(existingFoundryProjectResourceId, '/')[8], split(existingFoundryProjectResourceId, '/')[10])
  : ''

resource existingAiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = if (useExistingAIProject) {
  name: aiFoundryResourceName
  scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
}

// Deploy model deployments + connections to existing AI Foundry (when using existing project)
module existing_project_setup './modules/ai/existing-foundry-project.bicep' = if (useExistingAIProject) {
  name: take('module.existing-foundry-project.${solutionName}', 64)
  scope: resourceGroup(aiFoundrySubscriptionId, aiFoundryResourceGroupName)
  params: {
    name: existingAiFoundry.name
    projectName: existingHasProjectSegment ? split(existingFoundryProjectResourceId, '/')[10] : ''
    deployments: [
      for deployment in aiModelDeployments: {
        name: deployment.name
        model: {
          format: 'OpenAI'
          name: deployment.model
          version: deployment.version
        }
        raiPolicyName: deployment.raiPolicyName
        sku: {
          name: deployment.sku.name
          capacity: deployment.sku.capacity
        }
      }
    ]
    // Connections (workshop-only)
    applicationInsightsId: enableMonitoring ? app_insights!.outputs.resourceId : ''
    applicationInsightsInstrumentationKey: enableMonitoring ? app_insights!.outputs.instrumentationKey : ''
    aiSearchTarget: isWorkshop ? ai_search!.outputs.endpoint : ''
    aiSearchId: isWorkshop ? ai_search!.outputs.resourceId : ''
    aiSearchConnectionName: isWorkshop ? 'search-connection-${solutionSuffix}' : ''
    storageBlobEndpoint: isWorkshop ? storage_account!.outputs.blobEndpoint : ''
    storageAccountId: isWorkshop ? storage_account!.outputs.resourceId : ''
    storageAccountName: isWorkshop ? storage_account!.outputs.name : ''
  }
}

// Deploy new AI Services account with deployments + role assignments via AVM
module aifoundry './modules/ai/ai-foundry.bicep' = if (!useExistingAIProject) {
  name: take('module.ai-foundry.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: azureAiServiceLocation
    tags: tags
    enableTelemetry: enableTelemetry
    // Temporarily public — AI Search Knowledge Base needs to call the AI Services model endpoint for answer synthesis.
    publicNetworkAccess: 'Enabled'
    diagnosticSettings: enableMonitoring ? [{ workspaceResourceId: logAnalyticsWorkspaceResourceId }] : null
    deployments: [
      for deployment in aiModelDeployments: {
        name: deployment.name
        model: {
          format: 'OpenAI'
          name: deployment.model
          version: deployment.version
        }
        raiPolicyName: deployment.raiPolicyName
        sku: {
          name: deployment.sku.name
          capacity: deployment.sku.capacity
        }
      }
    ]
    roleAssignments: [
      {
        roleDefinitionIdOrName: 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
      {
        roleDefinitionIdOrName: '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Azure AI User
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
    ]
    // Project connections
    enableSearchConnection: isWorkshop
    aiSearchName: isWorkshop ? ai_search!.outputs.name : ''
    aiSearchConnectionName: isWorkshop ? 'search-connection-${solutionSuffix}' : ''
    enableStorageConnection: isWorkshop
    storageAccountName: isWorkshop ? storage_account!.outputs.name : ''
    storageBlobEndpoint: isWorkshop ? storage_account!.outputs.blobEndpoint : ''
    storageAccountResourceId: isWorkshop ? storage_account!.outputs.resourceId : ''
    applicationInsightsName: app_insights!.outputs.name
    applicationInsightsResourceId: enableMonitoring ? app_insights!.outputs.resourceId : ''
    applicationInsightsInstrumentationKey: enableMonitoring ? app_insights!.outputs.instrumentationKey : ''
    // Private networking
    enablePrivateNetworking: enablePrivateNetworking
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.cognitiveServices]!.outputs.resourceId
      privateDnsZoneDeployments[dnsZoneIndex.openAI]!.outputs.resourceId
      privateDnsZoneDeployments[dnsZoneIndex.aiFoundry]!.outputs.resourceId
    ] : []
  }
  dependsOn: isWorkshop ? [ai_search] : []
}

module ai_search './modules/ai/ai-search.bicep' = if (isWorkshop) {
  name: take('module.ai-search.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: searchServiceLocation
    tags: tags
    enableTelemetry: enableTelemetry
    // Temporarily public — Foundry Agent runtime runs outside the VNET and cannot resolve private DNS for AI Search.
    publicNetworkAccess: 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    roleAssignments: [
      {
        roleDefinitionIdOrName: '8ebe5a00-799e-43f5-93ac-243d3dce84a7' // Search Index Data Contributor
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
      {
        roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0' // Search Service Contributor
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
    ]
    // Temporarily no private endpoint — Foundry Agent cannot resolve private DNS for AI Search.
    privateEndpoints: []
  }
}

// ============================================================================
// Module: Data 
// ============================================================================

module storage_account './modules/data/storage-account.bicep' = if (isWorkshop) {
  name: take('module.storage-account.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: azureAiServiceLocation
    tags: tags
    enableTelemetry: enableTelemetry
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    roleAssignments: [
      {
        roleDefinitionIdOrName: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' // Storage Blob Data Contributor
        principalId: deployingUserPrincipalId
        principalType: deployingUserPrincipalType
      }
    ]
    enablePrivateNetworking: enablePrivateNetworking
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.blob]!.outputs.resourceId
    ] : []
  }
}

module cosmosDBModule './modules/data/cosmos-db.bicep' = if (isWorkshop && shouldDeployApp) {
  name: take('module.cosmos-db.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    zoneRedundant: enableRedundancy
    enableAutomaticFailover: enableRedundancy
    haLocation: cosmosDbHaLocation
    enablePrivateNetworking: enablePrivateNetworking
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.cosmosDb]!.outputs.resourceId
    ] : []
  }
}

module sqlDBModule './modules/data/sql-database.bicep' = if (isWorkshop && azureEnvOnly) {
  name: take('module.sql-database.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: secondaryLocation
    tags: tags
    enableTelemetry: enableTelemetry
    deployerPrincipalId: deployingUserPrincipalId
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    enablePrivateNetworking: enablePrivateNetworking
    privateEndpointSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.backendSubnetResourceId : ''
    privateDnsZoneResourceIds: enablePrivateNetworking ? [
      privateDnsZoneDeployments[dnsZoneIndex.sqlServer]!.outputs.resourceId
    ] : []
  }
}

// ============================================================================
// Module: Compute
// ============================================================================

module hostingplan './modules/compute/app-service-plan.bicep' = if (shouldDeployApp) {
  name: take('module.app-service-plan.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    skuName: (enableScalability || enableRedundancy) ? 'P1v3' : appServicePlanSku
    skuCapacity: enableScalability ? 3 : 1
    zoneRedundant: enableRedundancy
    diagnosticSettings: monitoringDiagnosticSettings
  }
}

// Backend API (Python)
module backend_docker './modules/compute/app-service.bicep' = if (shouldDeployApp && backendRuntimeStack == 'python') {
  name: take('module.app-service-pybackend.${solutionName}', 64)
  params: {
    solutionName: 'api-${solutionSuffix}'
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    serverFarmResourceId: hostingplan!.outputs.resourceId
    linuxFxVersion: 'DOCKER|${containerRegistryName}.azurecr.io/da-api:${imageTag}'
    virtualNetworkSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.webserverfarmSubnetResourceId : ''
    publicNetworkAccess: 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    appSettings: {
      AZURE_ENV_GPT_MODEL_NAME: gptModelName
      AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME: embeddingModel
      AZURE_OPENAI_ENDPOINT: useExistingAIProject ? existingOpenAIEndpoint : aifoundry!.outputs.endpoint
      AZURE_ENV_OPENAI_API_VERSION: azureOpenaiAPIVersion
      AZURE_OPENAI_RESOURCE: useExistingAIProject ? aiFoundryResourceName : aifoundry!.outputs.name
      AZURE_AI_AGENT_ENDPOINT: useExistingAIProject ? existingProjectEndpoint : aifoundry!.outputs.projectEndpoint
      AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
      AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
      USE_CHAT_HISTORY_ENABLED: useChatHistoryEnabledSetting
      AZURE_COSMOSDB_ACCOUNT: (isWorkshop && shouldDeployApp) ? cosmosDBModule!.outputs.name : ''
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: isWorkshop ? 'conversations' : ''
      AZURE_COSMOSDB_DATABASE: isWorkshop ? 'db_conversation_history' : ''
      AZURE_COSMOSDB_ENABLE_FEEDBACK: isWorkshop ? 'True' : ''
      AZURE_SQLDB_DATABASE: (isWorkshop && azureEnvOnly) ? sqlDBModule!.outputs.databaseName : ''
      AZURE_SQLDB_SERVER: (isWorkshop && azureEnvOnly) ? sqlDBModule!.outputs.serverFqdn : ''
      AZURE_SQLDB_USER_MID: ''
      API_UID: ''
      AZURE_AI_SEARCH_ENDPOINT: isWorkshop ? ai_search!.outputs.endpoint : ''
      AZURE_AI_SEARCH_INDEX: isWorkshop ? 'knowledge_index' : ''
      AZURE_AI_SEARCH_CONNECTION_NAME: isWorkshop ? (useExistingAIProject ? existing_project_setup!.outputs.searchConnectionName : aifoundry!.outputs.searchConnectionName) : ''
      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: enableMonitoring ? app_insights!.outputs.connectionString : ''
      SOLUTION_NAME: solutionSuffix
      IS_WORKSHOP: isWorkshop ? 'True' : 'False'
      AZURE_ENV_ONLY: azureEnvOnly ? 'True' : 'False'
      USE_USER_ACCESS_TOKEN: useUserAccessTokenSetting
      APP_ENV: 'Prod'
      AZURE_BASIC_LOGGING_LEVEL: 'INFO'
      AZURE_PACKAGE_LOGGING_LEVEL: 'WARNING'
      AZURE_LOGGING_PACKAGES: ''
      AGENT_NAME_CHAT: ''
      AGENT_NAME_TITLE: ''
      FABRIC_SQL_DATABASE: ''
      FABRIC_SQL_SERVER: ''
      FABRIC_SQL_CONNECTION_STRING: ''
    }
  }
}

// Backend API (C#)
module backend_csapi_docker './modules/compute/app-service.bicep' = if (shouldDeployApp && backendRuntimeStack == 'dotnet') {
  name: take('module.app-service.csbackend.${solutionName}', 64)
  params: {
    solutionName: 'api-cs-${solutionSuffix}'
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    serverFarmResourceId: hostingplan!.outputs.resourceId
    linuxFxVersion: 'DOCKER|${containerRegistryName}.azurecr.io/da-api-dotnet:${imageTag}'
    virtualNetworkSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.webserverfarmSubnetResourceId : ''
    publicNetworkAccess: 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    appSettings: {
      AZURE_ENV_GPT_MODEL_NAME: gptModelName
      AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME: embeddingModel
      AZURE_OPENAI_ENDPOINT: useExistingAIProject ? existingOpenAIEndpoint : aifoundry!.outputs.endpoint
      AZURE_ENV_OPENAI_API_VERSION: azureOpenaiAPIVersion
      AZURE_OPENAI_RESOURCE: useExistingAIProject ? aiFoundryResourceName : aifoundry!.outputs.name
      AZURE_AI_AGENT_ENDPOINT: useExistingAIProject ? existingProjectEndpoint : aifoundry!.outputs.projectEndpoint
      AZURE_AI_AGENT_API_VERSION: azureAiAgentApiVersion
      AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME: gptModelName
      USE_CHAT_HISTORY_ENABLED: useChatHistoryEnabledSetting
      AZURE_COSMOSDB_ACCOUNT: (isWorkshop && shouldDeployApp) ? cosmosDBModule!.outputs.name : ''
      AZURE_COSMOSDB_CONVERSATIONS_CONTAINER: isWorkshop ? 'conversations' : ''
      AZURE_COSMOSDB_DATABASE: isWorkshop ? 'db_conversation_history' : ''
      AZURE_COSMOSDB_ENABLE_FEEDBACK: isWorkshop ? 'True' : ''
      API_UID: ''
      AZURE_AI_SEARCH_ENDPOINT: isWorkshop ? ai_search!.outputs.endpoint : ''
      AZURE_AI_SEARCH_INDEX: isWorkshop ? 'call_transcripts_index' : ''
      AZURE_AI_SEARCH_CONNECTION_NAME: isWorkshop ? (useExistingAIProject ? existing_project_setup!.outputs.searchConnectionName : aifoundry!.outputs.searchConnectionName) : ''
      USE_AI_PROJECT_CLIENT: 'True'
      DISPLAY_CHART_DEFAULT: 'False'
      APPLICATIONINSIGHTS_CONNECTION_STRING: enableMonitoring ? app_insights!.outputs.connectionString : ''
      SOLUTION_NAME: solutionSuffix
      APP_ENV: 'Prod'
      AGENT_NAME_CHAT: ''
      AGENT_NAME_TITLE: ''
      FABRIC_SQL_DATABASE: ''
      FABRIC_SQL_SERVER: ''
      FABRIC_SQL_CONNECTION_STRING: ''
    }
  }
}

// Frontend
module frontend_docker './modules/compute/app-service.bicep' = if (shouldDeployApp) {
  name: take('module.app-service-frontend.${solutionName}', 64)
  params: {
    solutionName: 'app-${solutionSuffix}'
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    serverFarmResourceId: hostingplan!.outputs.resourceId
    linuxFxVersion: 'DOCKER|${containerRegistryName}.azurecr.io/da-app:${imageTag}'
    virtualNetworkSubnetId: enablePrivateNetworking ? virtualNetwork!.outputs.webserverfarmSubnetResourceId : ''
    publicNetworkAccess: 'Enabled'
    diagnosticSettings: monitoringDiagnosticSettings
    appSettings: {
      APP_API_BASE_URL: shouldDeployApp ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.appUrl : backend_csapi_docker!.outputs.appUrl) : ''
      CHAT_LANDING_TEXT: landingText
      IS_WORKSHOP: isWorkshop ? 'True' : 'False'
      APP_TITLE_PRIMARY: appTitlePrimary
      APP_TITLE_SECONDARY: appTitleSecondary
      PROXY_API_REQUESTS: enablePrivateNetworking ? 'true' : 'false'
    }
  }
}

// ============================================================================
// Module: Role Assignments (centralized)
// ============================================================================

module role_assignments './modules/identity/role-assignments.bicep' = {
  name: take('module.role-assignments.${solutionName}', 64)
  params: {
    solutionName: solutionSuffix
    aiProjectPrincipalId: (!useExistingAIProject) ? aifoundry!.outputs.projectIdentityPrincipalId : ''
    aiSearchPrincipalId: isWorkshop ? ai_search!.outputs.identityPrincipalId : ''
    aiSearchResourceId: isWorkshop ? ai_search!.outputs.resourceId : ''
    storageAccountResourceId: isWorkshop ? storage_account!.outputs.resourceId : ''
    isWorkshop: isWorkshop
    cosmosDbAccountName: (isWorkshop && shouldDeployApp) ? cosmosDBModule!.outputs.name : ''
    backendAppServicePrincipalId: shouldDeployApp
      ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.identityPrincipalId : backend_csapi_docker!.outputs.identityPrincipalId)
      : ''
    aiFoundryResourceId: !useExistingAIProject ? aifoundry!.outputs.resourceId : ''
    useExistingAIProject: useExistingAIProject
    existingFoundryProjectResourceId: existingFoundryProjectResourceId
    existingAiProjectPrincipalId: useExistingAIProject ? existing_project_setup!.outputs.aiProjectPrincipalId : ''
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Solution suffix used for naming resources.')
output SOLUTION_NAME string = solutionSuffix

@description('Name of the deployed resource group.')
output RESOURCE_GROUP_NAME string = resourceGroup().name

@description('WAF deployment type.')
output DEPLOYMENT_TYPE string = enablePrivateNetworking ? 'WAF' : 'Non-WAF'

@description('Cosmos DB account name.')
output AZURE_COSMOSDB_ACCOUNT string = (shouldDeployApp && isWorkshop) ? cosmosDBModule!.outputs.name : ''

@description('Cosmos DB container name.')
output AZURE_COSMOSDB_CONVERSATIONS_CONTAINER string = isWorkshop ? 'conversations' : ''

@description('Cosmos DB database name.')
output AZURE_COSMOSDB_DATABASE string = isWorkshop ? 'db_conversation_history' : ''

@description('GPT model deployment name.')
output AZURE_ENV_GPT_MODEL_NAME string = gptModelName

@description('Azure OpenAI service endpoint URL.')
output AZURE_OPENAI_ENDPOINT string = !useExistingAIProject ? aifoundry!.outputs.endpoint : existingOpenAIEndpoint

@description('Embedding model deployment name.')
output AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME string = embeddingModel

@description('Azure SQL database name (Azure-only mode).')
output AZURE_SQLDB_DATABASE string = (isWorkshop && azureEnvOnly) ? sqlDBModule!.outputs.databaseName : ''

@description('Azure SQL server FQDN (Azure-only mode).')
output AZURE_SQLDB_SERVER string = (isWorkshop && azureEnvOnly) ? sqlDBModule!.outputs.serverFqdn : ''

@description('Managed identity client ID for SQL auth.')
output AZURE_SQLDB_USER_MID string = ''

@description('Backend API managed identity client ID.')
output API_UID string = ''

@description('Azure AI Agent endpoint.')
output AZURE_AI_AGENT_ENDPOINT string = !useExistingAIProject ? aifoundry!.outputs.projectEndpoint : existingProjectEndpoint

@description('Model deployment name for AI Agent.')
output AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME string = gptModelName

@description('Backend API App Service name.')
output API_APP_NAME string = shouldDeployApp ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.name : backend_csapi_docker!.outputs.name) : ''

@description('Backend API managed identity principal ID.')
output API_PID string = shouldDeployApp
  ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.identityPrincipalId : backend_csapi_docker!.outputs.identityPrincipalId)
  : ''

@description('Backend API managed identity display name.')
output MID_DISPLAY_NAME string = shouldDeployApp
  ? (backendRuntimeStack == 'python' ? backend_docker!.outputs.name : backend_csapi_docker!.outputs.name)
  : ''

@description('Frontend web application URL.')
output WEB_APP_URL string = shouldDeployApp ? frontend_docker!.outputs.appUrl : ''

@description('Deployed use case identifier.')
output USE_CASE string = usecase

@description('Azure AI Search endpoint.')
output AZURE_AI_SEARCH_ENDPOINT string = isWorkshop ? ai_search!.outputs.endpoint : ''

@description('Azure AI Search index name.')
output AZURE_AI_SEARCH_INDEX string = isWorkshop ? 'knowledge_index' : ''

@description('Azure AI Search service name.')
output AZURE_AI_SEARCH_NAME string = isWorkshop ? ai_search!.outputs.name : ''

@description('Search data folder path.')
output SEARCH_DATA_FOLDER string = isWorkshop ? 'data/default/documents' : ''

@description('AI Search connection name.')
output AZURE_AI_SEARCH_CONNECTION_NAME string = isWorkshop ? (useExistingAIProject ? existing_project_setup!.outputs.searchConnectionName : aifoundry!.outputs.searchConnectionName) : ''

@description('AI Search connection ID.')
output AZURE_AI_SEARCH_CONNECTION_ID string = (isWorkshop && !useExistingAIProject) ? aifoundry!.outputs.searchConnectionId : ''

@description('AI Foundry project endpoint.')
output AZURE_AI_PROJECT_ENDPOINT string = !useExistingAIProject ? aifoundry!.outputs.projectEndpoint : existingProjectEndpoint

@description('AI Foundry resource ID.')
output AI_FOUNDRY_RESOURCE_ID string = !useExistingAIProject ? aifoundry!.outputs.resourceId : existingFoundryProjectResourceId

@description('AI Foundry project name.')
output AZURE_AI_PROJECT_NAME string = !useExistingAIProject ? aifoundry!.outputs.projectName : (existingHasProjectSegment ? split(existingFoundryProjectResourceId, '/')[10] : '')

@description('AI Services resource name.')
output AI_SERVICE_NAME string = !useExistingAIProject ? aifoundry!.outputs.name : aiFoundryResourceName

@description('AI Project identity principal ID.')
output FOUNDRY_PROJECT_PID string = !useExistingAIProject ? aifoundry!.outputs.projectIdentityPrincipalId : ''

@description('Chat history enabled flag.')
output USE_CHAT_HISTORY_ENABLED string = useChatHistoryEnabledSetting

@description('Backend runtime stack.')
output BACKEND_RUNTIME_STACK string = backendRuntimeStack

@description('Workshop mode flag.')
output IS_WORKSHOP bool = isWorkshop

@description('Deploy app flag.')
output AZURE_ENV_DEPLOY_APP bool = deployApp

@description('Azure-only mode flag.')
output AZURE_ENV_ONLY bool = azureEnvOnly

@description('User access token forwarding flag.')
output USE_USER_ACCESS_TOKEN string = useUserAccessTokenSetting

@description('The name of the Fabric capacity resource.')
output AZURE_FABRIC_CAPACITY_NAME string = createFabricWorkspace ? fabricCapacityResourceName : ''

@description('The identities assigned as Fabric Capacity Admin members.')
output FABRIC_ADMIN_MEMBERS array = shouldCreateFabricCapacity ? fabricTotalAdminMembers : []

@description('The unique solution suffix of the deployed resources.')
output SOLUTION_SUFFIX string = solutionSuffix
