# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
variable "resource_group_name" { type = string }
variable "location" { type = string }
variable "solution_name" { type = string }
variable "log_analytics_workspace_id" { type = string }
variable "virtual_network_cidr" { type = string }
variable "private_link_resources" {
  type = map(object({ resource_id = string
  subresource_name = string
  dns_zone_name = string }))
}
variable "tags" { type = map(string)
  default = {} }
