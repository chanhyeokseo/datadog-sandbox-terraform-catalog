terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}
provider "aws" {
  region = var.region
}

locals {
  name_prefix = "${var.creator}-${var.team}"
  common_tags = {
    ManagedBy = "Terraform"
    creator   = var.creator
    team      = var.team
  }
}

module "ecs_fargate" {
  source = "git::https://github.com/chanhyeokseo/datadog-sandbox-terraform-catalog.git//modules/ecs?ref=webui-dev"

  name_prefix    = "${local.name_prefix}-fargate"
  enable_fargate = var.ecs_enable_fargate
  enable_ec2     = false
  common_tags    = local.common_tags
}
