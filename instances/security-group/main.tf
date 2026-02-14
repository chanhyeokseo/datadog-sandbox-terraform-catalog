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
  name_prefix = "${var.creator}-${var.team}"
  my_ip_cidr  = "${chomp(data.http.my_ip.response_body)}/32"
  common_tags = {
    ManagedBy = "Terraform"
    creator   = var.creator
    team      = var.team
  }
}

module "security_group" {
  source = "git::https://github.com/chanhyeokseo/datadog-sandbox-terraform-catalog.git//modules/security-group?ref=webui-dev"

  name_prefix   = local.name_prefix
  vpc_id        = var.vpc_id
  my_ip_cidr    = local.my_ip_cidr
  common_tags   = local.common_tags
  ingress_rules = var.sg_ingress_rules
  egress_rules  = var.sg_egress_rules
}
