# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
locals {
  connections = {
    search = {
      name       = "cognitivesearch-connection-${var.solution_name}"
      category   = "CognitiveSearch"
      target     = var.search_endpoint
      auth_type  = "AAD"
      is_default = false
      metadata   = { ApiType = "Azure"
  ResourceId = var.search_id }
      credentials = null
    }
    storage = {
      name       = "azureblob-connection-${var.solution_name}"
      category   = "AzureBlob"
      target     = var.storage_blob_endpoint
      auth_type  = "AAD"
      is_default = false
      metadata   = { ResourceId = var.storage_account_id
  AccountName = var.storage_account_name
  ContainerName = "default" }
      credentials = null
    }
    app_insights = {
      name       = "appinsights-connection-${var.solution_name}"
      category   = "AppInsights"
      target     = var.application_insights_id
      auth_type  = "ApiKey"
      is_default = true
      metadata   = { ApiType = "Azure"
  ResourceId = var.application_insights_id }
      credentials = { key = var.application_insights_instrumentation_key }
    }
  }
}

resource "azapi_resource" "connection" {
  for_each  = var.should_create_application_insights_connection ? local.connections : { for key, value in local.connections : key => value if key != "app_insights" }
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2025-12-01"
  name      = each.value.name
  parent_id = var.foundry_project_id

  body = {
    properties = merge({
      category                    = each.value.category
      target                      = each.value.target
      authType                    = each.value.auth_type
      isSharedToAll               = true
      metadata                    = each.value.metadata
      useWorkspaceManagedIdentity = false
    }, each.value.is_default ? { isDefault = true } : {}, each.value.credentials != null ? { credentials = each.value.credentials } : {})
  }
}
