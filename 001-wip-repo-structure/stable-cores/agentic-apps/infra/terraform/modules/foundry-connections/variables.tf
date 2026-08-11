# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
variable "foundry_project_id" { type = string }
variable "solution_name" { type = string }
variable "search_endpoint" { type = string }
variable "search_id" { type = string }
variable "storage_blob_endpoint" { type = string }
variable "storage_account_id" { type = string }
variable "storage_account_name" { type = string }
variable "application_insights_id" { type = string }
variable "should_create_application_insights_connection" { type = bool }
variable "application_insights_instrumentation_key" { type = string
  sensitive = true }
