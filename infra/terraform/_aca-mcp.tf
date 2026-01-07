# Key Vault Role Assignment - MCP App (Key Vault Secrets User)
resource "azurerm_role_assignment" "kv_secrets_camcp" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.mcp.principal_id
}

# User Assigned Managed Identity for Backend Container App
resource "azurerm_user_assigned_identity" "mcp" {
  name                = "uami-mcp-${var.iteration}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
}

resource "azurerm_container_app" "mcp" {
  name                         = "ca-mcp-${var.iteration}"
  container_app_environment_id = azurerm_container_app_environment.cae.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.mcp.id]
  }

  ingress {
    target_port      = 8000
    external_enabled = true
    transport        = "http"
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }


  template {
    min_replicas = 1
    max_replicas = 3

    container {
      name   = "mcp"
      image  = var.docker_image_mcp
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "DISABLE_AUTH"
        value = "true"
      }

      env {
        name  = "DB_PATH"
        value = "data/contoso.db"
      }
    }

  }

  lifecycle {
    ignore_changes = []
  }

  depends_on = [
    azurerm_role_assignment.kv_secrets_camcp
  ]
}
