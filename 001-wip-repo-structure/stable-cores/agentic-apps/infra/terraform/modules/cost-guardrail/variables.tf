variable "name" {
  description = "Name of the resource-group budget"
  type        = string
}

variable "resource_group_id" {
  description = "Resource ID of the resource group guarded by the budget"
  type        = string
}

variable "amount" {
  description = "Monthly budget amount in billing currency"
  type        = number
}

variable "contact_email" {
  description = "Email address that receives budget notifications"
  type        = string
}

variable "start_date" {
  description = "Budget start date at the first day of a month in RFC 3339 format"
  type        = string
}
