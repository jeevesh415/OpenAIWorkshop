locals {
  env         = var.environment
  name_prefix = lower("${var.project_name}-${local.env}")

  rg_name               = "rg-${local.name_prefix}-${var.iteration}"
  asp_name              = "asp-${var.project_name}-${local.env}"
  app_name              = "app-${var.project_name}-${local.env}"
  ai_hub_name           = lower("aih-${var.project_name}-${local.env}-${var.iteration}")
  vnet_name             = "vnet-${local.name_prefix}"
  security_group_prefix = "sg-${local.name_prefix}"
  model_endpoint        = "https://${local.ai_hub_name}.openai.azure.com/openai/v1/chat/completions"
  openai_endpoint       = "https://${local.ai_hub_name}.openai.azure.com"
  key_vault_name        = "kv-${substr(local.name_prefix, 0, 14)}-${substr(var.iteration, -2, -1)}"
  web_app_name_prefix   = "${local.name_prefix}-${var.iteration}"

  common_tags = { env = local.env, project = var.project_name }
}
