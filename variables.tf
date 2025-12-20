# ============================================
# Variables
# ============================================

# Shared/VPC Resources
variable "vpc_id" {
  description = "ID of existing VPC to use (e.g., vpc-xxxxxxxxx)"
  type        = string
}

variable "public_subnet_id" {
  description = "ID of existing public subnet 1"
  type        = string
}

variable "public_subnet2_id" {
  description = "ID of existing public subnet 2"
  type        = string
}

variable "private_subnet_id" {
  description = "ID of existing private subnet"
  type        = string
}

# Project-specific Resources
variable "project_name" {
  description = "Project or personal identifier (e.g., chanhyeok)"
  type        = string
}

variable "project_env" {
  description = "Environment for project resources (e.g., dev, test, prod)"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-2"
}

# EC2 Configuration
variable "ec2_instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "ec2_key_name" {
  description = "Name of the EC2 key pair for SSH access"
  type        = string
}

# Datadog Configuration
variable "datadog_api_key" {
  description = "Datadog API key for agent authentication"
  type        = string
  sensitive   = true
}

variable "datadog_site" {
  description = "Datadog site (e.g., datadoghq.com, datadoghq.eu, us3.datadoghq.com)"
  type        = string
  default     = "datadoghq.com"
}