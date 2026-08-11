variable "name" {
  description = "Name of the Azure Communication Services resource"
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
}

variable "data_location" {
  description = "Data location for Azure Communication Services"
  type        = string
  default     = "United States"
}

variable "tags" {
  description = "Tags to apply to the resource"
  type        = map(string)
  default     = {}
}
