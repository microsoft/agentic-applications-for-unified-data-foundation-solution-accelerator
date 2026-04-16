@description('The Azure region where the Cosmos DB account will be deployed.')
param solutionLocation string

@description('The name of the Cosmos DB account.')
param accountName string
var databaseName = 'db_conversation_history'
var collectionName = 'conversations'

var containers = [
  {
    name: collectionName
    id: collectionName
    partitionKey: '/userId'
  }
]

@description('The type of Cosmos DB account to create.')
@allowed([ 'GlobalDocumentDB', 'MongoDB', 'Parse' ])
param kind string = 'GlobalDocumentDB'

@description('Tags to apply to the Cosmos DB resources.')
param tags object = {}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: accountName
  kind: kind
  location: solutionLocation
  tags: tags
  properties: {
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [
      {
        locationName: solutionLocation
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    databaseAccountOfferType: 'Standard'
    capacityMode: 'Serverless'
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    disableLocalAuth: true
    apiProperties: (kind == 'MongoDB') ? { serverVersion: '4.0' } : {}
  }
}


resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2022-05-15' = {
  name: '${accountName}/${databaseName}'
  properties: {
    resource: { id: databaseName }
  }

  resource list 'containers' = [for container in containers: {
    name: container.name
    properties: {
      resource: {
        id: container.id
        partitionKey: { paths: [ container.partitionKey ] }
      }
      options: {}
    }
  }]

  dependsOn: [
    cosmos
  ]
}

@description('The name of the created Cosmos DB account.')
output cosmosAccountName string = cosmos.name

@description('The name of the Cosmos DB database.')
output cosmosDatabaseName string = databaseName

@description('The name of the Cosmos DB container.')
output cosmosContainerName string = collectionName
