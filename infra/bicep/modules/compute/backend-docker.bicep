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

var imageName = 'DOCKER|${acrName}.azurecr.io/da-api:${imageTag}'

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

module appService 'app-service.bicep' = {
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

@description('The URL of the deployed App Service.')
output appUrl string = appService.outputs.appUrl

@description('The name of the App Service.')
output appName string = name

@description('The React app layout configuration JSON.')
output reactAppLayoutConfig string = reactAppLayoutConfig

@description('The Application Insights instrumentation key.')
output appInsightInstrumentationKey string = reference(applicationInsightsId, '2015-05-01').InstrumentationKey

@description('The principal ID of the App Service managed identity.')
output identityPrincipalId string = appService.outputs.identityPrincipalId
