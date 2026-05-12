// ========== monitoring.bicep ========== //
// Creates Log Analytics Workspace (or references an existing one) and Application Insights.
// These are the core observability resources for the solution.

targetScope = 'resourceGroup'

@description('The name of the solution, used for naming monitoring resources.')
param solutionName string

@description('The Azure region where monitoring resources will be deployed.')
param solutionLocation string

@description('The resource ID of an existing Log Analytics workspace. If empty, a new one will be created.')
param existingLogAnalyticsWorkspaceId string = ''

var workspaceName = 'log-${solutionName}'
var applicationInsightsName = 'appi-${solutionName}'
var useExisting = !empty(existingLogAnalyticsWorkspaceId)
var existingLawSubscription = useExisting ? split(existingLogAnalyticsWorkspaceId, '/')[2] : ''
var existingLawResourceGroup = useExisting ? split(existingLogAnalyticsWorkspaceId, '/')[4] : ''
var existingLawName = useExisting ? split(existingLogAnalyticsWorkspaceId, '/')[8] : ''

// ========== Log Analytics Workspace ========== //

resource existingLogAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2025-07-01' existing = if (useExisting) {
  name: existingLawName
  scope: resourceGroup(existingLawSubscription, existingLawResourceGroup)
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-07-01' = if (!useExisting) {
  name: workspaceName
  location: solutionLocation
  tags: {}
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
  }
}

// ========== Application Insights ========== //

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: solutionLocation
  kind: 'web'
  properties: {
    Application_Type: 'web'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    WorkspaceResourceId: useExisting ? existingLogAnalyticsWorkspace.id : logAnalytics.id
  }
}

// ========== Outputs ========== //

@description('The resource ID of the Application Insights instance.')
output applicationInsightsId string = applicationInsights.id

@description('The connection string for Application Insights.')
output applicationInsightsConnectionString string = applicationInsights.properties.ConnectionString

@description('The instrumentation key for Application Insights.')
output applicationInsightsInstrumentationKey string = applicationInsights.properties.InstrumentationKey

@description('The name of the Log Analytics workspace.')
output logAnalyticsWorkspaceResourceName string = useExisting ? existingLogAnalyticsWorkspace.name : logAnalytics.name

@description('The resource group of the Log Analytics workspace.')
output logAnalyticsWorkspaceResourceGroup string = useExisting ? existingLawResourceGroup : resourceGroup().name

@description('The subscription ID of the Log Analytics workspace.')
output logAnalyticsWorkspaceSubscription string = useExisting ? existingLawSubscription : subscription().subscriptionId
