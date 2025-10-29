# ============================================
# ECS Fargate Datadog Module Variables
# ============================================

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for ECS tasks"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs for ECS tasks"
  type        = list(string)
}

variable "assign_public_ip" {
  description = "Assign public IP to ECS tasks"
  type        = bool
  default     = true
}

variable "task_cpu" {
  description = "CPU for the ECS task (256, 512, 1024, etc.)"
  type        = string
  default     = "256"
}

variable "task_memory" {
  description = "Memory for the ECS task in MB (512, 1024, 2048, etc.)"
  type        = string
  default     = "512"
}

variable "desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}

variable "datadog_api_key" {
  description = "Datadog API key"
  type        = string
  sensitive   = true
}

variable "datadog_site" {
  description = "Datadog site (e.g., datadoghq.com)"
  type        = string
  default     = "datadoghq.com"
}

variable "app_image" {
  description = "Docker image for the FastAPI application (e.g., fastapi-dogstatsd:latest)"
  type        = string
  default     = "fastapi-dogstatsd:latest"
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

