# ============================================
# EC2 Datadog Host Module Variables
# ============================================

variable "name_prefix" {
  description = "Name prefix for EC2 instance"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "subnet_id" {
  description = "ID of the subnet where instance will be launched"
  type        = string
}

variable "security_group_ids" {
  description = "List of security group IDs to attach to the instance"
  type        = list(string)
}

variable "key_name" {
  description = "Name of the EC2 key pair for SSH access"
  type        = string
}

variable "associate_public_ip" {
  description = "Whether to associate a public IP address"
  type        = bool
  default     = true
}

variable "datadog_api_key" {
  description = "Datadog API key for agent authentication"
  type        = string
  sensitive   = true
}

variable "datadog_site" {
  description = "Datadog site (e.g., datadoghq.com, datadoghq.eu)"
  type        = string
  default     = "datadoghq.com"
}

variable "project_name" {
  description = "Project name for tagging"
  type        = string
}

variable "environment" {
  description = "Environment name for tagging"
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

