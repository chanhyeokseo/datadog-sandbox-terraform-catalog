# ============================================
# Basic EC2 Module Variables
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

variable "custom_ami_id" {
  description = "Custom AMI ID (optional, defaults to latest Amazon Linux 2023)"
  type        = string
  default     = ""
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

variable "user_data" {
  description = "User data script to run on instance launch"
  type        = string
  default     = ""
}

variable "user_data_replace_on_change" {
  description = "Whether to replace instance when user data changes"
  type        = bool
  default     = false
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

