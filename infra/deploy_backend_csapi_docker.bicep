@description('The Docker image tag to deploy.')
param imageTag string

@description('The name of the Azure Container Registry.')
param acrName string

@description('The resource ID of the Application Insights instance.')
param applicationInsightsId string

@description('Solution Location')
param solutionLocation string

@description('Application settings for the App Service.')
@secure()
param appSettings object = {}

@description('The resource ID of the App Service Plan.')
param appServicePlanId string

@description('The resource ID of the user-assigned managed identity.')
param userassignedIdentityId string

@description('The name of the Azure AI Services account.')
param aiServicesName string

@description('The resource ID of an existing AI project, if reusing one.')
param azureExistingAIProjectResourceId string = ''
var existingAIServiceSubscription = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[2] : subscription().subscriptionId
var existingAIServiceResourceGroup = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[4] : resourceGroup().name
var existingAIServicesName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[8] : ''
var existingAIProjectName = !empty(azureExistingAIProjectResourceId) ? split(azureExistingAIProjectResourceId, '/')[10] : ''

var imageName = 'DOCKER|${acrName}.azurecr.io/da-api-dotnet:${imageTag}'

@description('The name of the App Service.')
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

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-12-01' existing = {
  name: aiServicesName
  scope: resourceGroup(existingAIServiceSubscription, existingAIServiceResourceGroup)
}

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

@description('The URL of the deployed App Service.')
output appUrl string = appService.outputs.appUrl

@description('The name of the App Service.')
output appName string = name

@description('The React app layout configuration JSON.')
output reactAppLayoutConfig string = reactAppLayoutConfig

@description('The Application Insights instrumentation key.')
output appInsightInstrumentationKey string = reference(applicationInsightsId, '2015-05-01').InstrumentationKey
