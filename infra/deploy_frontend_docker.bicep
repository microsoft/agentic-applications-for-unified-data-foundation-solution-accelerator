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

var imageName = 'DOCKER|${acrName}.azurecr.io/da-app:${imageTag}'

@description('The name of the App Service.')
param name string
module appService 'deploy_app_service.bicep' = {
  name: '${name}-app-module'
  params: {
    solutionLocation:solutionLocation
    solutionName: name
    appServicePlanId: appServicePlanId
    appImageName: imageName
    appSettings: union(
      appSettings,
      {
        APPINSIGHTS_INSTRUMENTATIONKEY: reference(applicationInsightsId, '2015-05-01').InstrumentationKey
      }
    )
  }
}

@description('The URL of the deployed App Service.')
output appUrl string = appService.outputs.appUrl
