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

module "ecr_apps" {
  source = "git::https://github.com/chanhyeokseo/datadog-sandbox-terraform-catalog.git//modules/ecr?ref=webui-dev"

  repository_name        = "${local.name_prefix}-apps"
  image_tag_mutability   = "MUTABLE"
  scan_on_push           = true
  force_delete           = true
  lifecycle_policy_count = 20

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-apps" })
}
