# User Assigned Managed Identity for Backend Container App
resource "azurerm_user_assigned_identity" "backend" {
  name                = "uami-be-${var.iteration}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
}

# Key Vault Role Assignment - Backend App (Key Vault Secrets User)
resource "azurerm_role_assignment" "kv_secrets_cabe" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.backend.principal_id
}

resource "azurerm_container_app" "backend" {
  name                         = "ca-be-${var.iteration}"
  container_app_environment_id = azurerm_container_app_environment.cae.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.backend.id]
  }

  ingress {
    target_port      = "7000"
    external_enabled = true
    transport        = "http"
    traffic_weight {
      percentage      = "100"
      latest_revision = true
    }

    cors {
      allow_credentials_enabled = true
      allowed_origins           = ["*"]
      allowed_headers           = ["*"]
      allowed_methods           = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    }
  }

  secret {
    name                = "aoai-key"
    identity            = azurerm_user_assigned_identity.backend.id
    key_vault_secret_id = azurerm_key_vault_secret.aoai_api_key.id
  }

  template {
    min_replicas = 1
    max_replicas = 3

    container {
      name   = "backend"
      image  = var.docker_image_backend
      cpu    = 1
      memory = "2Gi"

      readiness_probe {
        port      = 7000
        transport = "HTTP"
        path      = "/docs"

        initial_delay           = 10
        interval_seconds        = 30
        failure_count_threshold = 3
      }

      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = local.openai_endpoint
      }

      env {
        name        = "AZURE_OPENAI_API_KEY"
        secret_name = "aoai-key"
      }

      env {
        name  = "AZURE_OPENAI_API_VERSION"
        value = "2025-01-01-preview" # azurerm_cognitive_deployment.gpt.model[0].version
      }

      env {
        name  = "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
        value = "text-embedding-ada-002"
      }

      env {
        name  = "DB_PATH"
        value = "data/contoso.db"
      }

      env {
        name  = "AAD_TENANT_ID"
        value = ""
      }

      env {
        name  = "MCP_API_AUDIENCE"
        value = ""
      }

      env {
        name  = "MCP_SERVER_URI"
        value = "https://${azurerm_container_app.mcp.ingress[0].fqdn}/mcp"
      }

      env {
        name  = "DISABLE_AUTH"
        value = "true"
      }

      env {
        name  = "AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"
        value = var.openai_deployment_name
      }

      env {
        name  = "AZURE_OPENAI_CHAT_DEPLOYMENT"
        value = var.openai_deployment_name
      }

      env {
        name  = "OPENAI_MODEL_NAME"
        value = "gpt-4.1-2025-04-14" # var.openai_deployment_name
      }

      env {
        name  = "AGENT_MODULE"
        value = "agents.agent_framework.single_agent"
      }

      env {
        name  = "MAGENTIC_LOG_WORKFLOW_EVENTS"
        value = "true"
      }
      env {
        name  = "MAGENTIC_ENABLE_PLAN_REVIEW"
        value = "true"
      }
      env {
        name  = "MAGENTIC_MAX_ROUNDS"
        value = "10"
      }
      env {
        name  = "HANDOFF_CONTEXT_TRANSFER_TURNS"
        value = "-1"
      }

    }
  }
  lifecycle {
    # ignore_changes = []
  }

  depends_on = [
    azurerm_role_assignment.kv_secrets_cabe
  ]
}
