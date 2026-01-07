resource "azurerm_resource_group" "rg" {
  name     = local.rg_name
  location = var.location
  tags     = { env = local.env, project = var.project_name }
}


resource "azurerm_ai_services" "ai_hub" {
  custom_subdomain_name              = local.ai_hub_name
  fqdns                              = []
  local_authentication_enabled       = true
  location                           = "East US 2"
  name                               = local.ai_hub_name
  outbound_network_access_restricted = false
  public_network_access              = "Enabled"
  resource_group_name                = azurerm_resource_group.rg.name
  sku_name                           = "S0"
  tags                               = local.common_tags

  identity {
    identity_ids = []
    type         = "SystemAssigned"
  }

  network_acls {
    default_action = "Allow"
    ip_rules       = []
  }

  lifecycle {
    ignore_changes = [tags]
  }
}

resource "azurerm_key_vault" "main" {
  name                       = local.key_vault_name
  location                   = var.location
  resource_group_name        = azurerm_resource_group.rg.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = false

  # Enable RBAC authorization (recommended over access policies)
  rbac_authorization_enabled = true

  # Network settings
  public_network_access_enabled = true

  network_acls {
    bypass         = "AzureServices"
    default_action = "Allow"
  }

  tags = local.common_tags

  lifecycle {
    ignore_changes = [tags]
  }
}

# Key Vault Role Assignment - Current User (Key Vault Administrator)
resource "azurerm_role_assignment" "kv_admin_current_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_key_vault_secret" "aoai_api_key" {
  name         = "AZURE-OPENAI-API-KEY"
  value        = azurerm_ai_services.ai_hub.primary_access_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_role_assignment.kv_admin_current_user]
}
