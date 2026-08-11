resource "azurerm_user_assigned_identity" "main" {
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "github" {
  name      = "github-actions-${var.github_environment}"
  audience  = ["api://AzureADTokenExchange"]
  issuer    = "https://token.actions.githubusercontent.com"
  parent_id = azurerm_user_assigned_identity.main.id
  subject   = "repository_owner_id:${var.github_repository_owner_id}:repository_id:${var.github_repository_id}:environment:${var.github_environment}"
}

resource "azurerm_role_assignment" "registry_push" {
  scope                = var.container_registry_id
  role_definition_name = "AcrPush"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

resource "azurerm_role_assignment" "ai_services" {
  scope                = var.ai_services_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

resource "azurerm_role_assignment" "resource_group" {
  scope                = var.resource_group_id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

resource "azurerm_role_assignment" "state_data" {
  scope                = var.state_storage_account_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}

resource "azurerm_role_assignment" "state_reader" {
  scope                = var.state_storage_account_id
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.main.principal_id
}
