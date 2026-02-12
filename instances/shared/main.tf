# Security Group
terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
    http = {
      source = "hashicorp/http"
    }
  }
}
provider "aws" {
  region = var.region
}

data "http" "my_ip" {
  url = "https://ifconfig.me/ip"
}

locals {
  project_name_prefix = "${var.project_name}-${var.project_env}"
  my_ip_cidr          = "${chomp(data.http.my_ip.response_body)}/32"
  project_common_tags = {
    Project     = var.project_name
    Environment = var.project_env
    ManagedBy   = "Terraform"
    creator     = var.creator
    team        = var.team
  }
}

module "security_group" {
  source = "../../modules/security-group"

  name_prefix   = local.project_name_prefix
  project_name  = var.project_name
  vpc_id        = var.vpc_id
  my_ip_cidr    = local.my_ip_cidr
  common_tags   = local.project_common_tags
  ingress_rules = var.sg_ingress_rules
  egress_rules  = var.sg_egress_rules
}
