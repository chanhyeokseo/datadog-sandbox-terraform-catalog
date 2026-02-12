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
  project_name_prefix = "${var.project_name}-${var.project_env}"
  project_common_tags = {
    Project     = var.project_name
    Environment = var.project_env
    ManagedBy   = "Terraform"
    creator     = var.creator
    team        = var.team
  }
}

module "ecs_fargate" {
  source = "../../modules/ecs"

  name_prefix    = "${local.project_name_prefix}-fargate"
  enable_fargate = var.ecs_enable_fargate
  enable_ec2     = false
  common_tags    = local.project_common_tags
}
