# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
resource "azapi_resource" "main" {
  type      = "Microsoft.Fabric/capacities@2023-11-01"
  name      = var.name
  parent_id = var.resource_group_id
  location  = var.location
  tags      = var.tags

  body = {
    sku = { name = var.sku_name
  tier = "Fabric" }
    properties = {
      administration = { members = var.admin_members }
    }
  }
}
