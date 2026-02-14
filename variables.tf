# ============================================
# Variables
# ============================================

# Resource Naming
variable "name_prefix" {
  description = "Short prefix for all resource names (e.g., chanhyeok-sandbox). Only [A-Za-z0-9_-], max 20 chars."
  type        = string

  validation {
    condition     = can(regex("^[0-9A-Za-z][0-9A-Za-z_-]*$", var.name_prefix)) && length(var.name_prefix) <= 20
    error_message = "name_prefix must match [0-9A-Za-z_-], start with alphanumeric, and be at most 20 characters."
  }
}

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

# RDS Configuration
variable "rds_username" {
  description = "Master username for RDS/DocumentDB instances"
  type        = string
  default     = "dbadmin"
}

variable "rds_password" {
  description = "Master password for RDS/DocumentDB instances"
  type        = string
  sensitive   = true
  default     = ""
}

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

# ============================================
# Required Tagging Policy
# ============================================
variable "creator" {
  description = "Creator of the resources (firstname.lastname format)"
  type        = string
}

variable "team" {
  description = "Team name (e.g., technical-support-engineering)"
  type        = string
}

# ============================================
# DBM Auto-Config
# ============================================
variable "dbm_postgres_datadog_password" {
  description = "Password for the datadog PostgreSQL user (for DBM monitoring)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "ssh_private_key_path" {
  description = "Path to SSH private key for EC2 provisioner connection"
  type        = string
  default     = "./chanhyeok.pem"
}