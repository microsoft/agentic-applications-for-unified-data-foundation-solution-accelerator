# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
variable "resource_group_id" { type = string }
variable "location" { type = string }
variable "name" { type = string }
variable "sku_name" { type = string
  default = "F2" }
variable "admin_members" { type = list(string) }
variable "tags" { type = map(string)
  default = {} }
