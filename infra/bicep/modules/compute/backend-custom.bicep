// ========== deploy_backend_custom.bicep ========== //
// Deploys the Python backend API App Service using Oryx source-code build (azd deploy compatible).
// Mirrors deploy_backend_docker.bicep but targets code deployment instead of a pre-built Docker image.

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

@description('Optional. Resource ID of the Log Analytics Workspace for diagnostic settings.')
param logAnalyticsWorkspaceId string = ''

@description('The name of the App Service.')
param name string

var reactAppLayoutConfig = '''{
  "appConfig": {
      "CHAT_CHATHISTORY": {
        "CHAT": 70,
        "CHATHISTORY": 30
      }
    }
  }
}'''

module appService 'app-service-custom.bicep' = {
  name: '${name}-app-module'
  params: {
    solutionName: name
    solutionLocation: solutionLocation
    appServicePlanId: appServicePlanId
    linuxFxVersion: 'PYTHON|3.11'
    appCommandLine: 'uvicorn app:app --host 0.0.0.0 --port 8000'
    userassignedIdentityId: userassignedIdentityId
    enableSystemAssignedIdentity: true
    azdServiceName: 'api'
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    appSettings: union(
      appSettings,
      {
        APPINSIGHTS_INSTRUMENTATIONKEY: reference(applicationInsightsId, '2015-05-01').InstrumentationKey
        REACT_APP_LAYOUT_CONFIG: reactAppLayoutConfig
        PYTHONUNBUFFERED: '1'
        SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
        ENABLE_ORYX_BUILD: 'true'
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
