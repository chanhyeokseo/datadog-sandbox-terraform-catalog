# ============================================
# Security Group Module
# ============================================

variable "sg_ingress_rules" {
  description = "Security Group ingress rules"
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

variable "sg_egress_rules" {
  description = "Security Group egress rules"
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

module "security_group" {
  source = "./modules/security-group"

  name_prefix  = local.name_prefix
  vpc_id       = local.vpc.vpc_id
  my_ip_cidr   = local.my_ip_cidr

  ingress_rules = var.sg_ingress_rules
  egress_rules  = var.sg_egress_rules

  common_tags = local.common_tags
}

# Output security group rules for WebUI
output "security_group_ingress_rules" {
  description = "Ingress rules of the security group"
  value       = module.security_group.ingress_rules
}

output "security_group_egress_rules" {
  description = "Egress rules of the security group"
  value       = module.security_group.egress_rules
}
