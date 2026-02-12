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

module "ecr_apps" {
  source = "../../modules/ecr"

  repository_name        = "${local.project_name_prefix}-apps"
  image_tag_mutability   = "MUTABLE"
  scan_on_push           = true
  force_delete           = true
  lifecycle_policy_count = 20

  tags = merge(local.project_common_tags, { Name = "${local.project_name_prefix}-apps" })
}
