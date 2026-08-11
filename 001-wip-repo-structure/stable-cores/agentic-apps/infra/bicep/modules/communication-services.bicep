// GENERATED FROM PROVIDED TERRAFORM. HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
metadata name = 'Azure Communication Services'
metadata description = 'Deploys a vanilla Azure Communication Services resource.'

@description('Globally unique resource name.')
param name string

@description('Data location for the resource.')
param dataLocation string

@description('Tags to apply to the resource.')
param tags object

resource communicationService 'Microsoft.Communication/communicationServices@2023-04-01' = {
  name: name
  location: 'global'
  tags: tags
  properties: {
    dataLocation: dataLocation
  }
}

@description('Resource ID of Azure Communication Services.')
output id string = communicationService.id

@description('Name of Azure Communication Services.')
output name string = communicationService.name
