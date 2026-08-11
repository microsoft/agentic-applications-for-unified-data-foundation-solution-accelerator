# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
locals {
  should_create_foundry = var.existing_foundry_project_resource_id == null
  existing_id_parts     = local.should_create_foundry ? [] : split("/", var.existing_foundry_project_resource_id)
  existing_account_id   = local.should_create_foundry ? null : join("/", slice(local.existing_id_parts, 0, 9))
  existing_account_name = local.should_create_foundry ? null : local.existing_id_parts[8]
  existing_project_name = local.should_create_foundry ? null : local.existing_id_parts[10]

  model_deployments = {
    gpt = {
      name       = var.gpt_model_name
      model_name = var.gpt_model_name
      version    = var.gpt_model_version
      sku_name   = var.deployment_type
      capacity   = var.gpt_deployment_capacity
    }
    embedding = {
      name       = var.embedding_model_name
      model_name = var.embedding_model_name
      version    = "1"
      sku_name   = "GlobalStandard"
      capacity   = var.embedding_deployment_capacity
    }
  }
}

data "azapi_resource" "existing_account" {
  count                  = local.should_create_foundry ? 0 : 1
  type                   = "Microsoft.CognitiveServices/accounts@2025-12-01"
  resource_id            = local.existing_account_id
  response_export_values = ["properties.endpoint", "properties.endpoints", "identity.principalId"]
}

data "azapi_resource" "existing_project" {
  count                  = local.should_create_foundry ? 0 : 1
  type                   = "Microsoft.CognitiveServices/accounts/projects@2025-12-01"
  resource_id            = var.existing_foundry_project_resource_id
  response_export_values = ["properties.endpoints", "identity.principalId"]
}

resource "azapi_resource" "account" {
  count     = local.should_create_foundry ? 1 : 0
  type      = "Microsoft.CognitiveServices/accounts@2025-12-01"
  name      = "aif-${var.solution_name}"
  parent_id = var.resource_group_id
  location  = var.location
  tags      = var.tags

  identity { type = "SystemAssigned" }

  body = {
    kind = "AIServices"
    sku  = { name = "S0" }
    properties = {
      allowProjectManagement = true
      customSubDomainName     = "aif-${var.solution_name}"
      disableLocalAuth        = true
      publicNetworkAccess     = "Enabled"
      networkAcls = {
        defaultAction       = "Allow"
        virtualNetworkRules = []
        ipRules             = []
      }
    }
  }

  response_export_values = ["properties.endpoint", "properties.endpoints", "identity.principalId"]
}

resource "azapi_resource" "project" {
  count     = local.should_create_foundry ? 1 : 0
  type      = "Microsoft.CognitiveServices/accounts/projects@2025-12-01"
  name      = "proj-${var.solution_name}"
  parent_id = azapi_resource.account[0].id
  location  = var.location

  identity { type = "SystemAssigned" }

  body = {
    kind       = "AIServices"
    properties = {}
  }

  response_export_values = ["properties.endpoints", "identity.principalId"]
}

resource "azapi_resource" "model_deployment" {
  for_each  = local.model_deployments
  type      = "Microsoft.CognitiveServices/accounts/deployments@2025-12-01"
  name      = each.value.name
  parent_id = local.should_create_foundry ? azapi_resource.account[0].id : local.existing_account_id

  body = {
    sku = { name = each.value.sku_name
  capacity = each.value.capacity }
    properties = {
      model         = { format = "OpenAI"
  name = each.value.model_name
  version = each.value.version }
      raiPolicyName = "Microsoft.Default"
    }
  }
}
