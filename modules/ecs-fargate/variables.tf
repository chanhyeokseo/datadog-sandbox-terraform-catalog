# ============================================
# ECS Fargate Module Variables
# ============================================

variable "name_prefix" {
  description = "Name prefix for ECS resources"
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
  description = "Whether to assign a public IP to ECS tasks"
  type        = bool
  default     = true
}

variable "task_cpu" {
  description = "CPU units for the ECS task (256, 512, 1024, 2048, 4096)"
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

variable "container_definitions" {
  description = "Container definitions JSON for the ECS task"
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

