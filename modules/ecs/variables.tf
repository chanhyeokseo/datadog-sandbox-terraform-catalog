# ============================================
# ECS Cluster Module Variables
# ============================================

variable "name_prefix" {
  description = "Name prefix for ECS resources"
  type        = string
}

# ============================================
# Capacity Provider Flags
# ============================================

variable "enable_fargate" {
  description = "Enable Fargate capacity provider"
  type        = bool
  default     = true
}

variable "enable_ec2" {
  description = "Enable EC2 capacity provider"
  type        = bool
  default     = false
}

# ============================================
# EC2 Configuration (required if enable_ec2 = true)
# ============================================

variable "subnet_ids" {
  description = "List of subnet IDs for ECS EC2 instances"
  type        = list(string)
  default     = []
}

variable "security_group_ids" {
  description = "List of security group IDs for ECS EC2 instances"
  type        = list(string)
  default     = []
}

variable "instance_type" {
  description = "EC2 instance type for ECS container instances"
  type        = string
  default     = "t3.medium"
}

variable "custom_ami_id" {
  description = "Custom AMI ID for ECS optimized instances"
  type        = string
  default     = null
}

variable "key_name" {
  description = "SSH key pair name for EC2 instances"
  type        = string
  default     = null
}

variable "ec2_min_size" {
  description = "Minimum number of EC2 instances in the Auto Scaling Group"
  type        = number
  default     = 1
}

variable "ec2_max_size" {
  description = "Maximum number of EC2 instances in the Auto Scaling Group"
  type        = number
  default     = 3
}

variable "ec2_desired_capacity" {
  description = "Desired number of EC2 instances in the Auto Scaling Group"
  type        = number
  default     = 1
}

variable "additional_user_data" {
  description = "Additional user data script to run on EC2 instances"
  type        = string
  default     = ""
}

# ============================================
# Common
# ============================================

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

