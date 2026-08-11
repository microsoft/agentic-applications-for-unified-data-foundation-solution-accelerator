# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
variable "resource_group_name" { type = string }
variable "location" { type = string }
variable "azure_ai_service_location" { type = string
  default = null }
variable "solution_name" { type = string
  default = "agenticappudf" }
variable "deployment_type" { type = string
  default = "GlobalStandard" }
variable "gpt_model_name" { type = string
  default = "gpt-5.4-mini" }
variable "gpt_model_version" { type = string
  default = "2026-03-17" }
variable "gpt_deployment_capacity" { type = number
  default = 150 }
variable "embedding_model_name" { type = string
  default = "text-embedding-3-small" }
variable "embedding_deployment_capacity" { type = number
  default = 80 }
variable "azure_openai_api_version" { type = string
  default = "2025-01-01-preview" }
variable "azure_ai_agent_api_version" { type = string
  default = "2025-05-01" }
variable "image_tag" { type = string
  default = "latest_v2" }
variable "container_registry_name" { type = string
  default = null }
variable "backend_runtime_stack" { type = string
  default = "python" }
variable "app_service_plan_sku" { type = string
  default = "B2" }
variable "use_chat_history_enabled" { type = bool
  default = true }
variable "use_user_access_token" { type = bool
  default = true }
variable "enable_private_networking" { type = bool
  default = false }
variable "virtual_network_cidr" { type = string
  default = "10.0.0.0/16" }
variable "create_fabric_workspace" { type = bool
  default = false }
variable "azure_fabric_capacity_name" { type = string
  default = null }
variable "fabric_capacity_sku" { type = string
  default = "F2" }
variable "fabric_admin_members" { type = list(string)
  default = [] }
variable "existing_log_analytics_workspace_id" { type = string
  default = null }
variable "existing_foundry_project_resource_id" { type = string
  default = null }
variable "deploying_principal_id" { type = string
  default = null }
variable "deploying_principal_type" { type = string
  default = "User" }
variable "app_title_primary" { type = string
  default = "Agentic Apps" }
variable "app_title_secondary" { type = string
  default = "| Unified Data Analysis Agents" }
variable "tags" { type = map(string)
  default = {} }
variable "communication_service_name" {
  description = "Globally unique Azure Communication Services name"
  type        = string
}

variable "communication_service_data_location" {
  description = "Data location for Azure Communication Services"
  type        = string
  default     = "United States"
}

variable "event_grid_name" {
  description = "Name prefix for incoming-call Event Grid resources"
  type        = string
}

variable "incoming_call_webhook_endpoint" {
  description = "HTTPS endpoint that receives incoming-call events"
  type        = string
  default     = null
}

variable "should_enable_ci_oidc" {
  description = "Whether to deploy CI workload identity and cost guardrails"
  type        = bool
  default     = false
}

variable "ci_identity_name" {
  description = "Name of the CI user-assigned managed identity"
  type        = string
  default     = "agentic-apps-ci"
}

variable "github_repository_owner_id" {
  description = "Immutable numeric GitHub repository owner ID"
  type        = string
  default     = null
}

variable "github_repository_id" {
  description = "Immutable numeric GitHub repository ID"
  type        = string
  default     = null
}

variable "github_environment" {
  description = "GitHub Environment used in the OIDC subject"
  type        = string
  default     = "production"
}

variable "state_storage_account_id" {
  description = "Resource ID of the Terraform state storage account"
  type        = string
  default     = null
}

variable "budget_name" {
  description = "Name of the resource-group budget"
  type        = string
  default     = "agentic-apps-ci-budget"
}

variable "monthly_budget_amount" {
  description = "Monthly budget amount in billing currency"
  type        = number
  default     = 50
}

variable "budget_contact_email" {
  description = "Email address that receives budget notifications"
  type        = string
  default     = null
}

variable "budget_start_date" {
  description = "Budget start date at the first day of a month in RFC 3339 format"
  type        = string
  default     = "2026-08-01T00:00:00Z"
}
