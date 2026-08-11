# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = { source = "hashicorp/azurerm"
  version = "~> 4.0" }
    azapi   = { source = "Azure/azapi"
  version = "~> 2.0" }
  }
}

provider "azurerm" { features {} }
provider "azapi" {}

data "azurerm_client_config" "current" {}
data "azurerm_resource_group" "main" { name = var.resource_group_name }

locals {
  solution_suffix    = substr(lower(replace(var.solution_name, "-", "")), 0, 18)
  ai_location        = coalesce(var.azure_ai_service_location, var.location)
  fabric_name        = coalesce(var.azure_fabric_capacity_name, "fc${local.solution_suffix}")
  should_create_fabric_capacity = var.create_fabric_workspace && var.azure_fabric_capacity_name == null
  deploying_principal_id = coalesce(var.deploying_principal_id, data.azurerm_client_config.current.object_id)
}

module "ai_foundry" {
  source                               = "./modules/ai-foundry"
  resource_group_id                    = data.azurerm_resource_group.main.id
  location                             = local.ai_location
  solution_name                        = local.solution_suffix
  existing_foundry_project_resource_id = var.existing_foundry_project_resource_id
  deployment_type                      = var.deployment_type
  gpt_model_name                       = var.gpt_model_name
  gpt_model_version                    = var.gpt_model_version
  gpt_deployment_capacity              = var.gpt_deployment_capacity
  embedding_model_name                 = var.embedding_model_name
  embedding_deployment_capacity        = var.embedding_deployment_capacity
  tags                                 = var.tags
}

module "platform" {
  source                                  = "./modules/platform"
  resource_group_name                     = var.resource_group_name
  location                                = var.location
  solution_name                           = local.solution_suffix
  tenant_id                               = data.azurerm_client_config.current.tenant_id
  existing_log_analytics_workspace_id     = var.existing_log_analytics_workspace_id
  container_registry_name                 = var.container_registry_name
  backend_runtime_stack                   = var.backend_runtime_stack
  app_service_plan_sku                    = var.app_service_plan_sku
  foundry_account_name                    = module.ai_foundry.account_name
  foundry_account_endpoint                = module.ai_foundry.account_endpoint
  foundry_project_endpoint                = module.ai_foundry.project_endpoint
  gpt_model_name                          = var.gpt_model_name
  embedding_model_name                    = var.embedding_model_name
  azure_openai_api_version                = var.azure_openai_api_version
  azure_ai_agent_api_version              = var.azure_ai_agent_api_version
  use_chat_history_enabled                = var.use_chat_history_enabled
  use_user_access_token                   = var.use_user_access_token
  app_title_primary                       = var.app_title_primary
  app_title_secondary                     = var.app_title_secondary
  tags                                    = var.tags
}

module "foundry_connections" {
  source                                  = "./modules/foundry-connections"
  foundry_project_id                      = module.ai_foundry.project_id
  solution_name                           = local.solution_suffix
  search_endpoint                         = module.platform.search_endpoint
  search_id                               = module.platform.search_id
  storage_blob_endpoint                   = module.platform.storage_blob_endpoint
  storage_account_id                      = module.platform.storage_account_id
  storage_account_name                    = module.platform.storage_account_name
  should_create_application_insights_connection = var.existing_foundry_project_resource_id == null
  application_insights_id                 = module.platform.application_insights_id
  application_insights_instrumentation_key = module.platform.application_insights_instrumentation_key
}

module "fabric_capacity" {
  count             = local.should_create_fabric_capacity ? 1 : 0
  source            = "./modules/fabric-capacity"
  resource_group_id = data.azurerm_resource_group.main.id
  location          = var.location
  name              = local.fabric_name
  sku_name          = var.fabric_capacity_sku
  admin_members     = distinct(concat([local.deploying_principal_id], var.fabric_admin_members))
  tags              = var.tags
}

module "role_assignments" {
  source                       = "./modules/role-assignments"
  foundry_account_id           = module.ai_foundry.account_id
  search_id                    = module.platform.search_id
  storage_account_id           = module.platform.storage_account_id
  cosmos_account_id            = module.platform.cosmos_account_id
  container_registry_id        = module.platform.container_registry_id
  foundry_project_principal_id = module.ai_foundry.project_principal_id
  search_principal_id          = module.platform.search_principal_id
  backend_principal_id         = module.platform.backend_principal_id
  frontend_principal_id        = module.platform.frontend_principal_id
  deploying_principal_id       = local.deploying_principal_id
}

module "landing_zone" {
  count                      = var.enable_private_networking ? 1 : 0
  source                     = "./modules/landing-zone"
  resource_group_name        = var.resource_group_name
  location                   = var.location
  solution_name              = local.solution_suffix
  log_analytics_workspace_id = module.platform.log_analytics_workspace_id
  virtual_network_cidr       = var.virtual_network_cidr
  private_link_resources = {
    foundry = { resource_id = module.ai_foundry.account_id
  subresource_name = "account"
  dns_zone_name = "privatelink.cognitiveservices.azure.com" }
    search = { resource_id = module.platform.search_id
  subresource_name = "searchService"
  dns_zone_name = "privatelink.search.windows.net" }
    storage = { resource_id = module.platform.storage_account_id
  subresource_name = "blob"
  dns_zone_name = "privatelink.blob.core.windows.net" }
    cosmos = { resource_id = module.platform.cosmos_account_id
  subresource_name = "Sql"
  dns_zone_name = "privatelink.documents.azure.com" }
    backend = { resource_id = module.platform.backend_app_id
  subresource_name = "sites"
  dns_zone_name = "privatelink.azurewebsites.net" }
    frontend = { resource_id = module.platform.frontend_app_id
  subresource_name = "sites"
  dns_zone_name = "privatelink.azurewebsites.net" }
    registry = { resource_id = module.platform.container_registry_id
  subresource_name = "registry"
  dns_zone_name = "privatelink.azurecr.io" }
  }
  tags = var.tags
}
module "communication_services" {
  source = "./modules/communication-services"

  name                = var.communication_service_name
  resource_group_name = var.resource_group_name
  data_location       = var.communication_service_data_location
  tags                = var.tags
}

module "incoming_call_events" {
  source = "./modules/incoming-call-events"

  name                     = var.event_grid_name
  resource_group_name      = var.resource_group_name
  communication_service_id = module.communication_services.id
  webhook_endpoint         = var.incoming_call_webhook_endpoint
  tags                     = var.tags
}

resource "terraform_data" "ci_inputs" {
  count = var.should_enable_ci_oidc ? 1 : 0

  lifecycle {
    precondition {
      condition     = var.github_repository_owner_id != null && var.github_repository_id != null
      error_message = "CI OIDC requires immutable GitHub repository owner and repository IDs."
    }
    precondition {
      condition     = var.state_storage_account_id != null
      error_message = "CI OIDC requires a Terraform state storage account resource ID."
    }
    precondition {
      condition     = var.budget_contact_email != null
      error_message = "CI OIDC requires a budget notification email."
    }
  }
}

module "ci_credentials" {
  source = "./modules/ci-credentials"
  count  = var.should_enable_ci_oidc ? 1 : 0

  name                       = var.ci_identity_name
  resource_group_name        = var.resource_group_name
  location                   = var.location
  github_repository_owner_id = var.github_repository_owner_id
  github_repository_id       = var.github_repository_id
  github_environment         = var.github_environment
  container_registry_id      = module.platform.container_registry_id
  ai_services_id             = module.ai_foundry.account_id
  resource_group_id          = data.azurerm_resource_group.main.id
  state_storage_account_id   = var.state_storage_account_id
  tags                       = var.tags

  depends_on = [terraform_data.ci_inputs]
}

module "cost_guardrail" {
  source = "./modules/cost-guardrail"
  count  = var.should_enable_ci_oidc ? 1 : 0

  name              = var.budget_name
  resource_group_id = data.azurerm_resource_group.main.id
  amount             = var.monthly_budget_amount
  contact_email      = var.budget_contact_email
  start_date         = var.budget_start_date

  depends_on = [terraform_data.ci_inputs]
}
