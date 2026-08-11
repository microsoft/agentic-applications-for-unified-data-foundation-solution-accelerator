# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
locals {
  account_id       = local.should_create_foundry ? azapi_resource.account[0].id : local.existing_account_id
  account_name     = local.should_create_foundry ? azapi_resource.account[0].name : local.existing_account_name
  project_id       = local.should_create_foundry ? azapi_resource.project[0].id : var.existing_foundry_project_resource_id
  project_name     = local.should_create_foundry ? azapi_resource.project[0].name : local.existing_project_name
  account_output   = local.should_create_foundry ? azapi_resource.account[0].output : data.azapi_resource.existing_account[0].output
  project_output   = local.should_create_foundry ? azapi_resource.project[0].output : data.azapi_resource.existing_project[0].output
}

output "account_id" { value = local.account_id }
output "account_name" { value = local.account_name }
output "account_endpoint" { value = local.account_output.properties.endpoints["OpenAI Language Model Instance API"] }
output "account_principal_id" { value = local.account_output.identity.principalId }
output "project_id" { value = local.project_id }
output "project_name" { value = local.project_name }
output "project_endpoint" { value = local.project_output.properties.endpoints["AI Foundry API"] }
output "project_principal_id" { value = local.project_output.identity.principalId }
