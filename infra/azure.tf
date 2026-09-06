provider "azurerm" {
  features {}
}

resource "azurerm_storage_account" "export" {
  name                            = "ordersexport${var.name_prefix}"
  resource_group_name             = "rg-orders-prod"
  location                        = "switzerlandnorth"
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  allow_nested_items_to_be_public = true
  https_traffic_only_enabled      = false
  min_tls_version                 = "TLS1_0"
  tags                            = local.common_tags
}

resource "azurerm_storage_container" "export" {
  name                  = "daily-export"
  storage_account_id    = azurerm_storage_account.export.id
  container_access_type = "blob"
}

resource "azurerm_network_security_rule" "ops_rdp" {
  name                        = "ops-rdp"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "3389"
  source_address_prefix       = "*"
  destination_address_prefix  = "*"
  resource_group_name         = "rg-orders-prod"
  network_security_group_name = "nsg-orders"
}
