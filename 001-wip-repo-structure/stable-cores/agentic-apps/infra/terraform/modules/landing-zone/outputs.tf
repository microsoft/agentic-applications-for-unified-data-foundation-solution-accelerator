# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
output "virtual_network_id" { value = azurerm_virtual_network.main.id }
output "private_endpoint_subnet_id" { value = azurerm_subnet.private_endpoints.id }
output "key_vault_id" { value = azurerm_key_vault.main.id }
output "private_endpoint_ids" { value = { for key, endpoint in azurerm_private_endpoint.main : key => endpoint.id } }
