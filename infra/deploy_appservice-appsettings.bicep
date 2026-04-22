metadata description = 'Updates app settings for an Azure App Service.'
@description('The name of the app service resource within the current resource group scope')
param name string

@description('The app settings to be applied to the app service')
@secure()
param appSettings object

resource appService 'Microsoft.Web/sites@2025-05-01' existing = {
  name: name
}

resource settings 'Microsoft.Web/sites/config@2025-05-01' = {
  name: 'appsettings'
  parent: appService
  properties: appSettings
}
