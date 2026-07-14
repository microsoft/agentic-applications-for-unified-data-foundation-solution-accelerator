// ============================================================================
// STANDALONE TEST TEMPLATE — Container Registry + Role Assignments (AVM variant)
// ----------------------------------------------------------------------------
// Purpose: quickly validate the new/existing container registry logic and the
// AcrPull role assignments in isolation, without deploying the full solution.
//
// It reuses the exact same modules that infra_new/avm/main.bicep uses:
//   - modules/compute/container-registry.bicep      (new registry when none provided)
//   - modules/compute/app-service-plan.bicep         (+ app-service.bicep)     [optional]
//   - modules/compute/container-app-environment.bicep(+ container-app.bicep)   [optional]
//   - modules/identity/role-assignments.bicep        (AcrPull — new + cross-scope existing)
//
// Deploy (example):
//   az group create -n rg-cr-test -l eastus2
//   # New registry + app service:
//   az deployment group create -g rg-cr-test -f infra_new/test/test-container-registry-avm.bicep
//   # Reuse an existing registry:
//   az deployment group create -g rg-cr-test -f infra_new/test/test-container-registry-avm.bicep \
//     -p existingContainerRegistryResourceId=/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.ContainerRegistry/registries/<name>
// ============================================================================

targetScope = 'resourceGroup'

// ----------------------------------------------------------------------------
// Parameters
// ----------------------------------------------------------------------------
@description('Solution name used for resource naming and unique role-assignment GUIDs. 3-16 chars.')
@minLength(3)
@maxLength(16)
param solutionName string = 'crtest'

@maxLength(5)
@description('Unique text appended to resource names to keep global names unique.')
param solutionUniqueText string = take(uniqueString(subscription().id, resourceGroup().id, solutionName), 5)

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Tags applied to all resources.')
param tags object = {}

@description('Optional. Resource ID of an existing Azure Container Registry to reuse. If empty, a new registry is created.')
param existingContainerRegistryResourceId string = ''

@description('Deploy an App Service (placeholder image) to validate AcrPull on its managed identity.')
param deployAppService bool = true

@description('Deploy a Container App (placeholder image) to validate AcrPull on its managed identity.')
param deployContainerApp bool = false

@description('Treat the newly created registry as private-networking (Premium SKU + public access disabled). No VNet/private endpoint is created here — this only flips SKU/public access for validation.')
param enablePrivateNetworking bool = false

@description('Principal type of the deployer (User for interactive az/azd, ServicePrincipal for CI).')
@allowed(['User', 'ServicePrincipal', 'Group'])
param deployingUserPrincipalType string = 'User'

@description('Enable AVM telemetry.')
param enableTelemetry bool = false

// ----------------------------------------------------------------------------
// Derived variables
// ----------------------------------------------------------------------------
var solutionSuffix = toLower(trim(replace(
  replace(replace(replace(replace(replace('${solutionName}${solutionUniqueText}', '-', ''), '_', ''), '.', ''), '/', ''), ' ', ''),
  '*',
  ''
)))

var deployerInfo = deployer()
var deployingUserPrincipalId = deployerInfo.objectId

var useExistingContainerRegistry = !empty(existingContainerRegistryResourceId)
var existingContainerRegistryName = useExistingContainerRegistry ? last(split(existingContainerRegistryResourceId, '/')) : ''

// Public placeholder images (no registry auth needed at provision time).
var placeholderAppServiceImage = 'DOCKER|mcr.microsoft.com/appsvc/staticsite:latest'
var placeholderContainerAppImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

// ----------------------------------------------------------------------------
// App Service (optional) — provides a system-assigned identity to grant AcrPull
// ----------------------------------------------------------------------------
module hostingPlan '../avm/modules/compute/app-service-plan.bicep' = if (deployAppService) {
  name: take('test.app-service-plan.${solutionSuffix}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    skuName: 'B1'
  }
}

module appService '../avm/modules/compute/app-service.bicep' = if (deployAppService) {
  name: take('test.app-service.${solutionSuffix}', 64)
  params: {
    solutionName: 'app-${solutionSuffix}'
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    serverFarmResourceId: hostingPlan!.outputs.resourceId
    linuxFxVersion: placeholderAppServiceImage
    publicNetworkAccess: 'Enabled'
  }
}

// ----------------------------------------------------------------------------
// Container App (optional) — provides a system-assigned identity to grant AcrPull
// ----------------------------------------------------------------------------
module containerAppEnvironment '../avm/modules/compute/container-app-environment.bicep' = if (deployContainerApp) {
  name: take('test.container-app-env.${solutionSuffix}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    enableMonitoring: false
    publicNetworkAccess: 'Enabled'
  }
}

module containerApp '../avm/modules/compute/container-app.bicep' = if (deployContainerApp) {
  name: take('test.container-app.${solutionSuffix}', 64)
  params: {
    name: 'ca-${solutionSuffix}'
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    environmentResourceId: containerAppEnvironment!.outputs.resourceId
    ingressTargetPort: 80
    containers: [
      {
        name: 'test'
        image: placeholderContainerAppImage
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
      }
    ]
  }
}

// ----------------------------------------------------------------------------
// Container Registry — created only when no existing registry is provided
// ----------------------------------------------------------------------------
module containerRegistry '../avm/modules/compute/container-registry.bicep' = if (!useExistingContainerRegistry) {
  name: take('test.container-registry.${solutionSuffix}', 64)
  params: {
    solutionName: solutionSuffix
    location: location
    tags: tags
    enableTelemetry: enableTelemetry
    sku: enablePrivateNetworking ? 'Premium' : 'Standard'
    publicNetworkAccess: enablePrivateNetworking ? 'Disabled' : 'Enabled'
    exportPolicyStatus: enablePrivateNetworking ? 'disabled' : 'enabled'
    networkRuleSetDefaultAction: enablePrivateNetworking ? 'Deny' : 'Allow'
  }
}

// Resolved registry identity (new or existing/reused).
var resolvedContainerRegistryName = useExistingContainerRegistry
  ? existingContainerRegistryName
  : containerRegistry!.outputs.name

var containerRegistryResourceId = useExistingContainerRegistry
  ? existingContainerRegistryResourceId
  : containerRegistry!.outputs.resourceId

// Principals that should get AcrPull: the deployer plus any compute identities.
var acrPullPrincipals = concat(
  [
    {
      principalId: deployingUserPrincipalId
      principalType: deployingUserPrincipalType
    }
  ],
  deployAppService
    ? [
        {
          principalId: appService!.outputs.identityPrincipalId
          principalType: 'ServicePrincipal'
        }
      ]
    : [],
  deployContainerApp
    ? [
        {
          principalId: containerApp!.outputs.principalId
          principalType: 'ServicePrincipal'
        }
      ]
    : []
)

// ----------------------------------------------------------------------------
// Role Assignments — same centralized module used by main.bicep (ACR params only)
// ----------------------------------------------------------------------------
module roleAssignments '../avm/modules/identity/role-assignments.bicep' = {
  name: take('test.role-assignments.${solutionSuffix}', 64)
  params: {
    solutionName: solutionSuffix
    useExistingContainerRegistry: useExistingContainerRegistry
    containerRegistryResourceId: containerRegistryResourceId
    acrPullPrincipals: acrPullPrincipals
  }
}

// ----------------------------------------------------------------------------
// Outputs
// ----------------------------------------------------------------------------
@description('Whether an existing registry was reused (true) or a new one created (false).')
output USED_EXISTING_CONTAINER_REGISTRY bool = useExistingContainerRegistry

@description('The resolved container registry name (new or existing/reused).')
output AZURE_CONTAINER_REGISTRY_NAME string = resolvedContainerRegistryName

@description('The resolved container registry resource ID.')
output AZURE_CONTAINER_REGISTRY_RESOURCE_ID string = containerRegistryResourceId

@description('App Service name (empty when not deployed).')
output APP_SERVICE_NAME string = deployAppService ? appService!.outputs.name : ''

@description('App Service managed identity principal ID granted AcrPull (empty when not deployed).')
output APP_SERVICE_PRINCIPAL_ID string = deployAppService ? appService!.outputs.identityPrincipalId : ''

@description('Container App name (empty when not deployed).')
output CONTAINER_APP_NAME string = deployContainerApp ? containerApp!.outputs.name : ''

@description('Container App managed identity principal ID granted AcrPull (empty when not deployed).')
output CONTAINER_APP_PRINCIPAL_ID string = deployContainerApp ? containerApp!.outputs.principalId : ''
