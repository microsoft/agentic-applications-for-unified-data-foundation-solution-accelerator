# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
output "solution_name" { value = local.solution_suffix }
output "resource_group_name" { value = var.resource_group_name }
output "ai_services_name" { value = module.ai_foundry.account_name }
output "ai_services_endpoint" { value = module.ai_foundry.account_endpoint }
output "ai_foundry_resource_id" { value = module.ai_foundry.account_id }
output "ai_project_name" { value = module.ai_foundry.project_name }
output "ai_project_endpoint" { value = module.ai_foundry.project_endpoint }
output "foundry_project_principal_id" { value = module.ai_foundry.project_principal_id }
output "gpt_model_name" { value = var.gpt_model_name }
output "embedding_model_name" { value = var.embedding_model_name }
output "search_endpoint" { value = module.platform.search_endpoint }
output "search_name" { value = module.platform.search_name }
output "search_connection_name" { value = module.foundry_connections.search_connection_name }
output "search_connection_id" { value = module.foundry_connections.search_connection_id }
output "storage_account_name" { value = module.platform.storage_account_name }
output "container_registry_name" { value = split(".", module.platform.container_registry_login_server)[0] }
output "container_registry_login_server" { value = module.platform.container_registry_login_server }
output "backend_app_name" { value = module.platform.backend_app_name }
output "backend_principal_id" { value = module.platform.backend_principal_id }
output "web_app_name" { value = module.platform.frontend_app_name }
output "web_app_url" { value = module.platform.web_app_url }
output "fabric_capacity_name" { value = var.create_fabric_workspace ? local.fabric_name : null }
output "fabric_capacity_id" { value = var.create_fabric_workspace ? (local.should_create_fabric_capacity ? module.fabric_capacity[0].id : "${data.azurerm_resource_group.main.id}/providers/Microsoft.Fabric/capacities/${local.fabric_name}") : null }
output "virtual_network_id" { value = var.enable_private_networking ? module.landing_zone[0].virtual_network_id : null }
output "image_tag" { value = var.image_tag }
output "backend_runtime_stack" { value = var.backend_runtime_stack }
output "communication_service_id" {
  description = "Resource ID of Azure Communication Services"
  value       = module.communication_services.id
}

output "communication_service_name" {
  description = "Name of Azure Communication Services"
  value       = module.communication_services.name
}

output "ci_identity_client_id" {
  description = "Client ID of the CI managed identity"
  value       = var.should_enable_ci_oidc ? module.ci_credentials[0].client_id : null
}
