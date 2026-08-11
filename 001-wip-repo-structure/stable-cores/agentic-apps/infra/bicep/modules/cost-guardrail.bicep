// GENERATED FROM PROVIDED TERRAFORM. HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
metadata name = 'Cost Guardrail'
metadata description = 'Deploys resource-group budget alerts for actual and forecasted spend.'

@description('Name of the resource-group budget.')
param name string

@description('Monthly budget amount in billing currency.')
param amount int

@description('Email address that receives budget notifications.')
param contactEmail string

@description('Budget start date at the first day of a month in RFC 3339 format.')
param startDate string

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: name
  properties: {
    amount: amount
    category: 'Cost'
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: startDate
    }
    notifications: {
      actual80Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: [contactEmail]
      }
      forecast100Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: [contactEmail]
      }
    }
  }
}

@description('Resource ID of the budget.')
output id string = budget.id
