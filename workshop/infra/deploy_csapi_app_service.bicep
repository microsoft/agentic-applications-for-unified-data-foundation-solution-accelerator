param location string = resourceGroup().location

@minLength(1)
@description('Name for the Web App (unique within resource group)')
param siteName string

@minLength(1)
@description('Key Vault name to store/open secrets')
param keyVaultName string

@description('Secret name for OpenAI key in Key Vault')
param openAiSecretName string = 'AZURE_OPENAI_KEY'

@description('Secret name for SQL connection string in Key Vault')
param sqlSecretName string = 'FABRIC_SQL_CONNECTION_STRING'

// Optional secure params (do not commit values). Leave empty to reference pre-existing secrets.
@secure()
@description('Optional: OpenAI key value to create in Key Vault')
param openAiSecretValue string = ''

@secure()
@description('Optional: SQL connection string value to create in Key Vault')
param sqlSecretValue string = ''

@minLength(1)
param skuName string = 'P1v2'

@description('Optional app setting: Azure OpenAI endpoint')
param azureOpenAiEndpoint string = ''

resource appInsights 'microsoft.insights/components@2020-02-02' = {
  name: '${siteName}-ai'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
  }
}

resource plan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: '${siteName}-plan'
  location: location
  sku: {
    name: skuName
    capacity: 1
  }
  properties: {
    reserved: true
  }
}

resource webApp 'Microsoft.Web/sites@2022-03-01' = {
  name: siteName
  location: location
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      linuxFxVersion: 'DOTNETCORE|8.0'
      appSettings: [
        {
          name: 'ASPNETCORE_ENVIRONMENT'
          value: 'Production'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: azureOpenAiEndpoint
        }
      ]
    }
  }
}

resource kv 'Microsoft.KeyVault/vaults@2022-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      name: 'standard'
      family: 'A'
    }
    tenantId: subscription().tenantId
    enableSoftDelete: true
    accessPolicies: []
  }
}


resource openAiSecret 'Microsoft.KeyVault/vaults/secrets@2019-09-01' = if (openAiSecretValue != '') {
  parent: kv
  name: openAiSecretName
  properties: {
    value: openAiSecretValue
  }
}

resource sqlSecret 'Microsoft.KeyVault/vaults/secrets@2019-09-01' = if (sqlSecretValue != '') {
  parent: kv
  name: sqlSecretName
  properties: {
    value: sqlSecretValue
  }
}


var openAiSecretUri = 'https://${keyVaultName}.vault.azure.net/secrets/${openAiSecretName}'
var sqlSecretUri = 'https://${keyVaultName}.vault.azure.net/secrets/${sqlSecretName}'

// Key Vault Secrets User role definition id
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

// Use a stable GUID value for the roleAssignment name (calculable at start)
resource kvRoleAssignment 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(kv.id, webApp.name, keyVaultSecretsUserRoleId)
  scope: kv
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    kv
    webApp
  ]
}

// Configure App Settings referencing Key Vault secrets (App Service Key Vault reference format)
resource webConfig 'Microsoft.Web/sites/config@2022-03-01' = {
  name: '${webApp.name}/appsettings'
  properties: {
    ASPNETCORE_ENVIRONMENT: 'Production'
    APPLICATIONINSIGHTS_CONNECTION_STRING: appInsights.properties.ConnectionString
    WEBSITE_RUN_FROM_PACKAGE: '1'
    AZURE_OPENAI_ENDPOINT: azureOpenAiEndpoint
    AZURE_OPENAI_KEY: '@Microsoft.KeyVault(SecretUri=${openAiSecretUri})'
    FABRIC_SQL_CONNECTION_STRING: '@Microsoft.KeyVault(SecretUri=${sqlSecretUri})'
  }
  dependsOn: [
    kvRoleAssignment
  ]
}

output webAppName string = webApp.name
output defaultHostName string = webApp.properties.defaultHostName
output appInsightsConnectionString string = appInsights.properties.ConnectionString
