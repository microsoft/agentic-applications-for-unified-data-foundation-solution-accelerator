# GENERATED FROM THE PROVIDED BICEP - HUMAN-REVIEW/VALIDATE BEFORE DEPLOYMENT.
locals {
  private_dns_zone_names = toset([
    "privatelink.cognitiveservices.azure.com",
    "privatelink.services.ai.azure.com",
    "privatelink.search.windows.net",
    "privatelink.blob.core.windows.net",
    "privatelink.documents.azure.com",
    "privatelink.azurewebsites.net",
    "privatelink.azurecr.io"
  ])
}

resource "azurerm_network_security_group" "applications" {
  name                = "nsg-app-${var.solution_name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
  security_rule {
    name = "deny-rdp-ssh-outbound"
  priority = 200
  direction = "Outbound"
  access = "Deny"
  protocol = "Tcp"
    source_port_range = "*"
  destination_port_ranges = ["22", "3389"]
  source_address_prefix = "VirtualNetwork"
  destination_address_prefix = "*"
  }
}

resource "azurerm_network_security_group" "private_endpoints" {
  name = "nsg-private-endpoints-${var.solution_name}"
  location = var.location
  resource_group_name = var.resource_group_name
  tags = var.tags
}

resource "azurerm_network_security_group" "bastion" {
  name = "nsg-bastion-${var.solution_name}"
  location = var.location
  resource_group_name = var.resource_group_name
  tags = var.tags
  security_rule {
    name = "allow-bastion-https-inbound"
  priority = 100
  direction = "Inbound"
  access = "Allow"
  protocol = "Tcp"
    source_port_range = "*"
  destination_port_range = "443"
  source_address_prefix = "Internet"
  destination_address_prefix = "*"
  }
  security_rule {
    name = "allow-bastion-management-inbound"
  priority = 110
  direction = "Inbound"
  access = "Allow"
  protocol = "Tcp"
    source_port_range = "*"
  destination_port_range = "443"
  source_address_prefix = "GatewayManager"
  destination_address_prefix = "*"
  }
}

resource "azurerm_virtual_network" "main" {
  name = "vnet-${var.solution_name}"
  location = var.location
  resource_group_name = var.resource_group_name
  address_space = [var.virtual_network_cidr]
  tags = var.tags
}

resource "azurerm_subnet" "applications" {
  name = "applications"
  resource_group_name = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes = [cidrsubnet(var.virtual_network_cidr, 8, 1)]
  delegation { name = "app-service-delegation", service_delegation { name = "Microsoft.Web/serverFarms"
  actions = ["Microsoft.Network/virtualNetworks/subnets/action"] } }
}
resource "azurerm_subnet_network_security_group_association" "applications" { subnet_id = azurerm_subnet.applications.id
  network_security_group_id = azurerm_network_security_group.applications.id }

resource "azurerm_subnet" "private_endpoints" {
  name = "private-endpoints"
  resource_group_name = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes = [cidrsubnet(var.virtual_network_cidr, 8, 2)]
  private_endpoint_network_policies = "Disabled"
}
resource "azurerm_subnet_network_security_group_association" "private_endpoints" { subnet_id = azurerm_subnet.private_endpoints.id
  network_security_group_id = azurerm_network_security_group.private_endpoints.id }

resource "azurerm_subnet" "bastion" {
  name = "AzureBastionSubnet"
  resource_group_name = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes = [cidrsubnet(var.virtual_network_cidr, 10, 12)]
}
resource "azurerm_subnet_network_security_group_association" "bastion" { subnet_id = azurerm_subnet.bastion.id
  network_security_group_id = azurerm_network_security_group.bastion.id }

resource "azurerm_private_dns_zone" "main" { for_each = local.private_dns_zone_names
  name = each.value
  resource_group_name = var.resource_group_name
  tags = var.tags }
resource "azurerm_private_dns_zone_virtual_network_link" "main" {
  for_each = local.private_dns_zone_names
  name = "link-${var.solution_name}-${substr(md5(each.value), 0, 6)}"
  resource_group_name = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.main[each.value].name
  virtual_network_id = azurerm_virtual_network.main.id
}

resource "azurerm_private_endpoint" "main" {
  for_each = var.private_link_resources
  name = "pep-${each.key}-${var.solution_name}"
  location = var.location
  resource_group_name = var.resource_group_name
  subnet_id = azurerm_subnet.private_endpoints.id
  tags = var.tags
  private_service_connection { name = "psc-${each.key}"
  private_connection_resource_id = each.value.resource_id
  subresource_names = [each.value.subresource_name]
  is_manual_connection = false }
  private_dns_zone_group { name = "default"
  private_dns_zone_ids = [azurerm_private_dns_zone.main[each.value.dns_zone_name].id] }
}

resource "azurerm_key_vault" "main" {
  name = substr("kv-${replace(var.solution_name, "-", "")}", 0, 24)
  location = var.location
  resource_group_name = var.resource_group_name
  tenant_id = data.azurerm_client_config.current.tenant_id
  sku_name = "standard"
  enable_rbac_authorization = true
  purge_protection_enabled = true
  soft_delete_retention_days = 90
  public_network_access_enabled = false
  tags = var.tags
}
data "azurerm_client_config" "current" {}

resource "azurerm_public_ip" "bastion" { name = "pip-bastion-${var.solution_name}"
  location = var.location
  resource_group_name = var.resource_group_name
  allocation_method = "Static"
  sku = "Standard"
  tags = var.tags }
resource "azurerm_bastion_host" "main" {
  name = "bas-${var.solution_name}"
  location = var.location
  resource_group_name = var.resource_group_name
  sku = "Standard"
  copy_paste_enabled = false
  ip_connect_enabled = true
  tags = var.tags
  ip_configuration { name = "default"
  subnet_id = azurerm_subnet.bastion.id
  public_ip_address_id = azurerm_public_ip.bastion.id }
}
resource "azurerm_monitor_diagnostic_setting" "vnet" {
  name = "send-to-log-analytics"
  target_resource_id = azurerm_virtual_network.main.id
  log_analytics_workspace_id = var.log_analytics_workspace_id
  enabled_metric { category = "AllMetrics" }
}
