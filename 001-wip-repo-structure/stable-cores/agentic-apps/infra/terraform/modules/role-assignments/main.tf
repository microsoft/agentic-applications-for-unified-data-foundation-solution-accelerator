# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
locals {
  workload_assignments = {
    search_openai_user       = { scope = var.foundry_account_id
  principal_id = var.search_principal_id
  role = "Cognitive Services OpenAI User" }
    backend_foundry_user     = { scope = var.foundry_account_id
  principal_id = var.backend_principal_id
  role = "Azure AI User" }
    project_search_reader    = { scope = var.search_id
  principal_id = var.foundry_project_principal_id
  role = "Search Index Data Reader" }
    project_search_service   = { scope = var.search_id
  principal_id = var.foundry_project_principal_id
  role = "Search Service Contributor" }
    backend_search_reader    = { scope = var.search_id
  principal_id = var.backend_principal_id
  role = "Search Index Data Reader" }
    project_storage_writer   = { scope = var.storage_account_id
  principal_id = var.foundry_project_principal_id
  role = "Storage Blob Data Contributor" }
    project_storage_reader   = { scope = var.storage_account_id
  principal_id = var.foundry_project_principal_id
  role = "Storage Blob Data Reader" }
    search_storage_reader    = { scope = var.storage_account_id
  principal_id = var.search_principal_id
  role = "Storage Blob Data Reader" }
    backend_acr_pull         = { scope = var.container_registry_id
  principal_id = var.backend_principal_id
  role = "AcrPull" }
    frontend_acr_pull        = { scope = var.container_registry_id
  principal_id = var.frontend_principal_id
  role = "AcrPull" }
  }
  deployer_assignments = var.deploying_principal_id == null ? {} : {
    deployer_cognitive_user  = { scope = var.foundry_account_id
  principal_id = var.deploying_principal_id
  role = "Cognitive Services User" }
    deployer_foundry_user    = { scope = var.foundry_account_id
  principal_id = var.deploying_principal_id
  role = "Azure AI User" }
    deployer_search_index    = { scope = var.search_id
  principal_id = var.deploying_principal_id
  role = "Search Index Data Contributor" }
    deployer_search_service  = { scope = var.search_id
  principal_id = var.deploying_principal_id
  role = "Search Service Contributor" }
    deployer_storage_writer  = { scope = var.storage_account_id
  principal_id = var.deploying_principal_id
  role = "Storage Blob Data Contributor" }
  }
  role_assignments = merge(local.workload_assignments, local.deployer_assignments)
}

resource "azurerm_role_assignment" "main" {
  for_each             = local.role_assignments
  scope                = each.value.scope
  principal_id         = each.value.principal_id
  role_definition_name = each.value.role
}

resource "azapi_resource" "backend_cosmos_data_contributor" {
  type      = "Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2025-10-15"
  name      = uuidv5("url", "${var.cosmos_account_id}|${var.backend_principal_id}|data-contributor")
  parent_id = var.cosmos_account_id

  body = {
    properties = {
      principalId     = var.backend_principal_id
      roleDefinitionId = "${var.cosmos_account_id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
      scope            = var.cosmos_account_id
    }
  }
}
