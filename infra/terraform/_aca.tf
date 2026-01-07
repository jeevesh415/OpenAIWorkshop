resource "azurerm_log_analytics_workspace" "laws" {
  name                = "log-${local.web_app_name_prefix}"
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name

  tags = local.common_tags
}

resource "azurerm_container_app_environment" "cae" {
  name                       = "cae-${local.web_app_name_prefix}"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.rg.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.laws.id
  infrastructure_subnet_id   = azurerm_subnet.containerapps.id

  tags = local.common_tags
}