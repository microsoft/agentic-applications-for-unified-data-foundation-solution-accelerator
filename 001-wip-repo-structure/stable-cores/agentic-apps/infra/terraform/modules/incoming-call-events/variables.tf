variable "name" {
  description = "Name of the Event Grid system topic"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "communication_service_id" {
  description = "Resource ID of Azure Communication Services"
  type        = string
}

variable "webhook_endpoint" {
  description = "HTTPS endpoint for incoming-call notifications"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to Event Grid resources"
  type        = map(string)
  default     = {}
}
