// ============================================================================
// Module: AI Services Deployments (for existing AI Services accounts)
// Description: Deploys model deployments + role assignments to an existing
//              AI Services account. Used when useExistingAIProject = true.
// Pattern: Same as MACAE ai-services-deployments.bicep
// ============================================================================

@description('Required. The name of the existing Cognitive Services account.')
param name string

@description('Optional. SKU of the Cognitive Services account.')
@allowed([
  'C2'
  'C3'
  'C4'
  'F0'
  'F1'
  'S'
  'S0'
  'S1'
  'S10'
  'S2'
  'S3'
  'S4'
  'S5'
  'S6'
  'S7'
  'S8'
  'S9'
])
param sku string = 'S0'

import { deploymentType } from 'br:mcr.microsoft.com/bicep/avm/res/cognitive-services/account:0.13.2'
@description('Optional. Array of deployments about cognitive service accounts to create.')
param deployments deploymentType[]?

import { roleAssignmentType } from 'br/public:avm/utl/types/avm-common-types:0.7.0'
@description('Optional. Array of role assignments to create.')
param roleAssignments roleAssignmentType[]?

// ============================================================================
// Built-in Role Definitions
// ============================================================================
var builtInRoleNames = {
  'Cognitive Services Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68'
  )
  'Cognitive Services OpenAI Contributor': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'a001fd3d-188f-4b5d-821b-7da978bf7442'
  )
  'Cognitive Services OpenAI User': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  )
  'Cognitive Services User': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    'a97b65f3-24c7-4388-baec-2e87135dc908'
  )
  'Azure AI Developer': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '64702f94-c441-49e6-a78b-ef80e0188fee'
  )
  'Azure AI User': subscriptionResourceId(
    'Microsoft.Authorization/roleDefinitions',
    '53ca6127-db72-4b80-b1b0-d745d6d5456d'
  )
  Contributor: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
  Owner: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8e3af657-a8ff-443c-a75c-2fe8c4bcb635')
  Reader: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'acdd72a7-3385-48ef-bd42-f606fba81ae7')
}

var formattedRoleAssignments = [
  for (roleAssignment, index) in (roleAssignments ?? []): union(roleAssignment, {
    roleDefinitionId: builtInRoleNames[?roleAssignment.roleDefinitionIdOrName] ?? (contains(
        roleAssignment.roleDefinitionIdOrName,
        '/providers/Microsoft.Authorization/roleDefinitions/'
      )
      ? roleAssignment.roleDefinitionIdOrName
      : subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAssignment.roleDefinitionIdOrName))
  })
]

// ============================================================================
// Existing Resource Reference
// ============================================================================
resource cognitiveService 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: name
}

// ============================================================================
// Model Deployments
// ============================================================================
@batchSize(1)
resource cognitiveService_deployments 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = [
  for (deployment, index) in (deployments ?? []): {
    parent: cognitiveService
    name: deployment.?name ?? '${name}-deployments'
    properties: {
      model: deployment.model
      raiPolicyName: deployment.?raiPolicyName
      versionUpgradeOption: deployment.?versionUpgradeOption
    }
    sku: deployment.?sku ?? {
      name: sku
      capacity: sku.?capacity
      tier: sku.?tier
      size: sku.?size
      family: sku.?family
    }
  }
]

// ============================================================================
// Role Assignments
// ============================================================================
resource cognitiveService_roleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for (roleAssignment, index) in (formattedRoleAssignments ?? []): {
    name: roleAssignment.?name ?? guid(cognitiveService.id, roleAssignment.principalId, roleAssignment.roleDefinitionId)
    properties: {
      roleDefinitionId: roleAssignment.roleDefinitionId
      principalId: roleAssignment.principalId
      description: roleAssignment.?description
      principalType: roleAssignment.?principalType
      condition: roleAssignment.?condition
      conditionVersion: !empty(roleAssignment.?condition) ? (roleAssignment.?conditionVersion ?? '2.0') : null
      delegatedManagedIdentityResourceId: roleAssignment.?delegatedManagedIdentityResourceId
    }
    scope: cognitiveService
  }
]

// ============================================================================
// Outputs
// ============================================================================
@description('Names of the deployed models.')
output deploymentNames array = [for (deployment, i) in (deployments ?? []): cognitiveService_deployments[i].name]
