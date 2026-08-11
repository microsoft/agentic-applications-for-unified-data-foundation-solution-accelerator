variable "name" {
  description = "Name of the CI user-assigned managed identity"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "location" {
  description = "Azure region for the managed identity"
  type        = string
}

variable "github_repository_owner_id" {
  description = "Immutable numeric GitHub repository owner ID"
  type        = string
}

variable "github_repository_id" {
  description = "Immutable numeric GitHub repository ID"
  type        = string
}

variable "github_environment" {
  description = "GitHub Environment included in the OIDC subject"
  type        = string
}

variable "container_registry_id" {
  description = "Resource ID of Azure Container Registry"
  type        = string
}

variable "ai_services_id" {
  description = "Resource ID of Azure AI Services"
  type        = string
}

variable "resource_group_id" {
  description = "Resource ID of the workload resource group"
  type        = string
}

variable "state_storage_account_id" {
  description = "Resource ID of the Terraform state storage account"
  type        = string
}

variable "tags" {
  description = "Tags to apply to the managed identity"
  type        = map(string)
  default     = {}
}
