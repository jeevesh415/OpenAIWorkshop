variable "project_name" { type = string }
variable "location" {
  type    = string
  default = "canadacentral"
}
variable "tenant_id" { type = string }
variable "subscription_id" { type = string }
variable "acr_name" { type = string }

variable "openai_deployment_name" {
  description = "Name of the OpenAI model deployment"
  type        = string
  default     = "gpt-4.1"
}

variable "openai_model_name" {
  description = "OpenAI model name to deploy"
  type        = string
  default     = "gpt-4.1"
}

variable "openai_model_version" {
  description = "OpenAI model version"
  type        = string
  default     = "2025-04-14"
}

variable "iteration" {
  description = "An iteration counter for things to prevent soft deletion issues."
  type        = string
  default     = "001"
}


variable "docker_image_backend" {
  description = "Docker image name (e.g., 'nginx:latest', 'httpd:alpine'). Leave empty to use runtime stack instead."
  type        = string
  default     = ""
}

variable "docker_image_mcp" {
  description = "Docker image name (e.g., 'nginx:latest', 'httpd:alpine'). Leave empty to use runtime stack instead."
  type        = string
  default     = ""
}

variable "docker_registry_url" {
  description = "Docker registry URL (e.g., 'https://index.docker.io' for Docker Hub). Only needed for private registries."
  type        = string
  default     = ""
}

variable "docker_registry_username" {
  description = "Username for private Docker registry authentication"
  type        = string
  default     = ""
  sensitive   = true
}

variable "docker_registry_password" {
  description = "Password for private Docker registry authentication"
  type        = string
  default     = ""
  sensitive   = true
}

variable "environment" {
  description = "Deployment environment (e.g., dev, integration, prod)"
  type        = string
  default     = "dev"
}

variable "vnet_address_space" {
  description = "Address space for vnet. Calculation has not been fully done on minimum size"
  type = list(string)
  default = ["10.0.0.0/16"]
}

variable "subnet_default_address_space" {
  description = "Address space for subnet that does not need delegation (private endpoints, etc.)"
  type = list(string)
  default = ["10.0.0.0/24"]
}
