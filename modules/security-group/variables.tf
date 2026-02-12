variable "name_prefix" {
  description = "Name prefix for security group (e.g., project-env)"
  type        = string
}

variable "project_name" {
  description = "Project name for description (e.g., chanhyeok)"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC where security group will be created"
  type        = string
}

variable "my_ip_cidr" {
  description = "Your IP address in CIDR notation (e.g., 1.2.3.4/32)"
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to the security group"
  type        = map(string)
  default     = {}
}

variable "service" {
  description = "Service name for tagging (e.g., ec2, rds, ecs)"
  type        = string
  default     = "ec2"
}

variable "ingress_rules" {
  description = "List of ingress rules for the security group"
  type = list(object({
    description = string
    from_port   = number
    to_port     = number
    protocol    = string
    cidr_blocks = list(string)
    use_my_ip   = optional(bool, false)
  }))
  default = []
}

variable "egress_rules" {
  description = "List of egress rules for the security group"
  type = list(object({
    description = string
    from_port   = number
    to_port     = number
    protocol    = string
    cidr_blocks = list(string)
    use_my_ip   = optional(bool, false)
  }))
  default = []
}

