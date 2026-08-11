output "client_id" {
  description = "Client ID of the CI managed identity"
  value       = azurerm_user_assigned_identity.main.client_id
}

output "principal_id" {
  description = "Principal ID of the CI managed identity"
  value       = azurerm_user_assigned_identity.main.principal_id
}
