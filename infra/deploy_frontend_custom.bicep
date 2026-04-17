// ========== deploy_frontend_custom.bicep ========== //
// Deploys the React frontend App Service using Oryx source-code build (azd deploy compatible).
// Mirrors deploy_frontend_docker.bicep but targets code deployment instead of a pre-built Docker image.
// No managed identity is assigned to the frontend in this configuration.

@description('The resource ID of the Application Insights instance.')
param applicationInsightsId string

@description('Solution Location')
param solutionLocation string

@description('Application settings for the App Service.')
@secure()
param appSettings object = {}

@description('The resource ID of the App Service Plan.')
param appServicePlanId string

@description('Optional. Resource ID of the Log Analytics Workspace for diagnostic settings.')
param logAnalyticsWorkspaceId string = ''

@description('The name of the App Service.')
param name string

module appService 'deploy_app_service_custom.bicep' = {
  name: '${name}-app-module'
  params: {
    solutionLocation: solutionLocation
    solutionName: name
    appServicePlanId: appServicePlanId
    linuxFxVersion: 'NODE|20-lts'
    appCommandLine: 'npx serve -s build -l 8080'
    enableSystemAssignedIdentity: false
    azdServiceName: 'webapp'
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    appSettings: union(
      appSettings,
      {
        APPINSIGHTS_INSTRUMENTATIONKEY: reference(applicationInsightsId, '2015-05-01').InstrumentationKey
        REACT_APP_API_BASE_URL: appSettings.APP_API_BASE_URL
        WEBSITE_NODE_DEFAULT_VERSION: '~20'
        SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
        ENABLE_ORYX_BUILD: 'true'
      }
    )
  }
}

@description('The URL of the deployed App Service.')
output appUrl string = appService.outputs.appUrl
