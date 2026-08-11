# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
locals {
  suffix                     = substr(lower(replace(var.solution_name, "-", "")), 0, 18)
  log_analytics_workspace_id = var.existing_log_analytics_workspace_id != null ? var.existing_log_analytics_workspace_id : azurerm_log_analytics_workspace.main[0].id
  backend_app_name           = var.backend_runtime_stack == "python" ? "api-${local.suffix}" : "api-cs-${local.suffix}"
}

resource "azurerm_log_analytics_workspace" "main" {
  count               = var.existing_log_analytics_workspace_id == null ? 1 : 0
  name                = "log-${local.suffix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_application_insights" "main" {
  name                = "appi-${local.suffix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  workspace_id        = local.log_analytics_workspace_id
  application_type    = "web"
  tags                = var.tags
}

resource "azurerm_search_service" "main" {
  name                          = "srch-${local.suffix}"
  resource_group_name           = var.resource_group_name
  location                      = var.location
  sku                           = "basic"
  public_network_access_enabled = true
  local_authentication_enabled  = false
  identity { type = "SystemAssigned" }
  tags = var.tags
}

resource "azurerm_storage_account" "main" {
  name                            = substr("st${local.suffix}", 0, 24)
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "ZRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  tags                            = var.tags
}

resource "azurerm_storage_container" "documents" {
  name                  = "default"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

resource "azurerm_cosmosdb_account" "history" {
  name                          = "cosmos-${local.suffix}"
  location                      = var.location
  resource_group_name           = var.resource_group_name
  offer_type                    = "Standard"
  kind                          = "GlobalDocumentDB"
  local_authentication_disabled = true
  consistency_policy { consistency_level = "Session" }
  geo_location { location = var.location
  failover_priority = 0 }
  identity { type = "SystemAssigned" }
  tags = var.tags
}

resource "azurerm_cosmosdb_sql_database" "history" {
  name                = "db_conversation_history"
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.history.name
}

resource "azurerm_cosmosdb_sql_container" "conversations" {
  name                  = "conversations"
  resource_group_name   = var.resource_group_name
  account_name          = azurerm_cosmosdb_account.history.name
  database_name         = azurerm_cosmosdb_sql_database.history.name
  partition_key_paths   = ["/userId"]
  partition_key_version = 2
}

resource "azurerm_container_registry" "main" {
  name                = coalesce(var.container_registry_name, substr("cr${local.suffix}", 0, 50))
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "Standard"
  admin_enabled       = false
  tags                = var.tags
}

resource "azurerm_service_plan" "main" {
  name                = "asp-${local.suffix}"
  resource_group_name = var.resource_group_name
  location            = var.location
  os_type             = "Linux"
  sku_name            = var.app_service_plan_sku
  tags                = var.tags
}

resource "azurerm_linux_web_app" "api" {
  name                = local.backend_app_name
  resource_group_name = var.resource_group_name
  location            = var.location
  service_plan_id     = azurerm_service_plan.main.id
  https_only          = true
  identity { type = "SystemAssigned" }
  site_config {
    minimum_tls_version = "1.2"
    application_stack { docker_image_name = "mcr.microsoft.com/azuredocs/aci-helloworld:latest" }
  }
  app_settings = {
    APPLICATIONINSIGHTS_CONNECTION_STRING     = azurerm_application_insights.main.connection_string
    AZURE_ENV_GPT_MODEL_NAME                  = var.gpt_model_name
    AZURE_ENV_EMBEDDING_DEPLOYMENT_NAME       = var.embedding_model_name
    AZURE_OPENAI_ENDPOINT                     = var.foundry_account_endpoint
    AZURE_ENV_OPENAI_API_VERSION              = var.azure_openai_api_version
    AZURE_OPENAI_RESOURCE                     = var.foundry_account_name
    AZURE_AI_AGENT_ENDPOINT                   = var.foundry_project_endpoint
    AZURE_AI_AGENT_API_VERSION                = var.azure_ai_agent_api_version
    AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME      = var.gpt_model_name
    USE_CHAT_HISTORY_ENABLED                  = title(tostring(var.use_chat_history_enabled))
    USE_USER_ACCESS_TOKEN                     = title(tostring(var.use_user_access_token))
    AZURE_COSMOSDB_ACCOUNT                    = azurerm_cosmosdb_account.history.name
    AZURE_COSMOSDB_CONVERSATIONS_CONTAINER    = azurerm_cosmosdb_sql_container.conversations.name
    AZURE_COSMOSDB_DATABASE                   = azurerm_cosmosdb_sql_database.history.name
    AZURE_AI_SEARCH_ENDPOINT                  = "https://${azurerm_search_service.main.name}.search.windows.net"
    AZURE_AI_SEARCH_INDEX                     = "knowledge_index"
    AZURE_AI_SEARCH_CONNECTION_NAME           = "cognitivesearch-connection-${var.solution_name}"
    USE_AI_PROJECT_CLIENT                     = "True"
    APP_ENV                                   = "Prod"
  }
  tags = var.tags
}

resource "azurerm_linux_web_app" "web" {
  name                = "app-${local.suffix}"
  resource_group_name = var.resource_group_name
  location            = var.location
  service_plan_id     = azurerm_service_plan.main.id
  https_only          = true
  identity { type = "SystemAssigned" }
  site_config {
    minimum_tls_version = "1.2"
    application_stack { docker_image_name = "mcr.microsoft.com/azuredocs/aci-helloworld:latest" }
  }
  app_settings = {
    APP_API_BASE_URL    = "https://${azurerm_linux_web_app.api.default_hostname}"
    APP_TITLE_PRIMARY   = var.app_title_primary
    APP_TITLE_SECONDARY = var.app_title_secondary
  }
  tags = var.tags
}
