resource "azurerm_network_security_group" "default" {
  name                = "${local.security_group_prefix}-default"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_virtual_network" "base" {
  name                = local.vnet_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  address_space       = var.vnet_address_space
}

resource "azurerm_subnet" "default" {
    name = "snet-default"
    resource_group_name = azurerm_resource_group.rg.name
    virtual_network_name = azurerm_virtual_network.base.name
    address_prefixes = var.subnet_default_address_space

    private_endpoint_network_policies = "Enabled"
}

resource "azurerm_subnet" "containerapps" {
    name = "snet-containerapps"
    resource_group_name = azurerm_resource_group.rg.name
    virtual_network_name = azurerm_virtual_network.base.name
    address_prefixes = var.subnet_infra_address_space

    private_endpoint_network_policies = "Enabled"
}

resource "azurerm_subnet_network_security_group_association" "default-nsg-association" {
  subnet_id                 = azurerm_subnet.default.id
  network_security_group_id = azurerm_network_security_group.default.id
}


resource "azurerm_subnet_network_security_group_association" "containerapps-nsg-association" {
  subnet_id                 = azurerm_subnet.containerapps.id
  network_security_group_id = azurerm_network_security_group.default.id
}