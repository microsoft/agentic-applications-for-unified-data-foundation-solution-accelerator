@description('The public placeholder container image used at provisioning time. The real image is applied by the post-deployment ACR build script.')
param placeholderImage string

@description('The resource ID of the user-assigned managed identity used for ACR pull.')
param userassignedIdentityId string = ''

@description('Client ID of the user-assigned managed identity used for ACR pull.')
param acrUserManagedIdentityClientId string = ''

@description('The resource ID of the Application Insights instance.')
param applicationInsightsId string

@description('Solution Location')
param solutionLocation string

@description('Application settings for the App Service.')
@secure()
param appSettings object = {}

@description('The resource ID of the App Service Plan.')
param appServicePlanId string

var imageName = 'DOCKER|${placeholderImage}'

@description('The name of the App Service.')
param name string
module appService 'deploy_app_service.bicep' = {
  name: '${name}-app-module'
  params: {
    solutionLocation:solutionLocation
    solutionName: name
    appServicePlanId: appServicePlanId
    appImageName: imageName
    userassignedIdentityId: userassignedIdentityId
    acrUseManagedIdentityCreds: true
    acrUserManagedIdentityClientId: acrUserManagedIdentityClientId
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
