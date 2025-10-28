param imageTag string
param acrName string
param applicationInsightsId string

@description('Solution Location')
param solutionLocation string

@secure()
param appSettings object = {}
param appServicePlanId string
param userassignedIdentityId string
// param keyVaultName string
param aiServicesName string
param azureExistingAIProjectResourceId string = ''
// param aiSearchName string
var existingAIServiceSubscription = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[2] : subscription().subscriptionId
var existingAIServiceResourceGroup = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[4] : resourceGroup().name
var existingAIServicesName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[8] : ''
var existingAIProjectName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[10] : ''

var imageName = 'DOCKER|${acrName}.azurecr.io/da-api:${imageTag}'
param name string 
var reactAppLayoutConfig ='''{
  "appConfig": {
      "CHAT_CHATHISTORY": {
        "CHAT": 70,
        "CHATHISTORY": 30
      }
    }
  }
}'''

module appService 'deploy_app_service.bicep' = {
  name: '${name}-app-module'
  params: {
    solutionName: name
    solutionLocation:solutionLocation
    appServicePlanId: appServicePlanId
    appImageName: imageName
    userassignedIdentityId:userassignedIdentityId
    appSettings: union(
      appSettings,
      {
        APPINSIGHTS_INSTRUMENTATIONKEY: reference(applicationInsightsId, '2015-05-01').InstrumentationKey
        REACT_APP_LAYOUT_CONFIG: reactAppLayoutConfig
      }
    )
  }
}

// resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2022-08-15' existing = {
//   name: appSettings.AZURE_COSMOSDB_ACCOUNT
// }

// resource contributorRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-05-15' existing = {
//   parent: cosmos
//   name: '00000000-0000-0000-0000-000000000002'
// }

// resource role 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2022-05-15' = {
//   parent: cosmos
//   name: guid(contributorRoleDefinition.id, cosmos.id)
//   properties: {
//     principalId: appService.outputs.identityPrincipalId
//     roleDefinitionId: contributorRoleDefinition.id
//     scope: cosmos.id
//   }
// }

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiServicesName
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
}

// resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
//   name: keyVaultName
// }

// resource keyVaultSecretsUser 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
//   name: '4633458b-17de-408a-b874-0445c86b69e6'
// }

// resource keyVaultSecretsUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
//   name: guid(appService.name, keyVault.name, keyVaultSecretsUser.id)
//   scope: keyVault
//   properties: {
//     roleDefinitionId: keyVaultSecretsUser.id
//     principalId: appService.outputs.identityPrincipalId
//     principalType: 'ServicePrincipal'
//   }
// }

// resource aiSearch 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
//   name: aiSearchName
// }

// resource searchIndexDataReader 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
//   name: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
// }

// resource searchIndexDataReaderAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
//   name: guid(appService.name, aiSearch.name, searchIndexDataReader.id)
//   scope: aiSearch
//   properties: {
//     roleDefinitionId: searchIndexDataReader.id
//     principalId: appService.outputs.identityPrincipalId
//     principalType: 'ServicePrincipal'
//   }
// }

resource aiUser 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
}

module existing_aiServicesModule 'existing_foundry_project.bicep' = if (!empty(azureExistingAIProjectResourceId)) {
  name: 'existing_foundry_project'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    aiServicesName: existingAIServicesName
    aiProjectName: existingAIProjectName
  }
}

module assignAiUserRoleToAiProject 'deploy_foundry_role_assignment.bicep' = {
  name: 'assignAiUserRoleToAiProject'
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
  params: {
    principalId: appService.outputs.identityPrincipalId
    roleDefinitionId: aiUser.id
    roleAssignmentName: guid(appService.name, aiServices.id, aiUser.id)
    aiServicesName: !empty(azureExistingAIProjectResourceId) ? existingAIServicesName : aiServicesName
    aiProjectName: !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[10] : ''
    enableSystemAssignedIdentity: false
  }
}

output appUrl string = appService.outputs.appUrl
output appName string = name
output reactAppLayoutConfig string = reactAppLayoutConfig
output appInsightInstrumentationKey string = reference(applicationInsightsId, '2015-05-01').InstrumentationKey
