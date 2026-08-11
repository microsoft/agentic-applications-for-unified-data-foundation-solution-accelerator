// GENERATED FROM PROVIDED TERRAFORM. HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
metadata name = 'ACS Incoming Call Events'
metadata description = 'Deploys a local Event Grid system topic and incoming-call webhook subscription.'

@description('Name of the Event Grid system topic.')
param name string

@description('Name of Azure Communication Services.')
param communicationServiceName string

@description('Optional HTTPS webhook endpoint for incoming-call notifications.')
@secure()
param webhookEndpoint string?

@description('Tags to apply to Event Grid resources.')
param tags object

resource communicationService 'Microsoft.Communication/communicationServices@2023-04-01' existing = {
  name: communicationServiceName
}

resource systemTopic 'Microsoft.EventGrid/systemTopics@2022-06-15' = {
  name: name
  location: 'global'
  tags: tags
  properties: {
    source: communicationService.id
    topicType: 'Microsoft.Communication.CommunicationServices'
  }
}

resource incomingCallSubscription 'Microsoft.EventGrid/eventSubscriptions@2023-12-15-preview' = if (webhookEndpoint != null) {
  name: '${name}-incoming-call'
  scope: communicationService
  properties: {
    destination: {
      endpointType: 'WebHook'
      properties: {
        endpointUrl: webhookEndpoint!
        maxEventsPerBatch: 1
        preferredBatchSizeInKilobytes: 64
      }
    }
    eventDeliverySchema: 'EventGridSchema'
    filter: {
      includedEventTypes: [
        'Microsoft.Communication.IncomingCall'
      ]
    }
    retryPolicy: {
      eventTimeToLiveInMinutes: 1440
      maxDeliveryAttempts: 30
    }
  }
  dependsOn: [systemTopic]
}

@description('Resource ID of the Event Grid system topic.')
output systemTopicId string = systemTopic.id
