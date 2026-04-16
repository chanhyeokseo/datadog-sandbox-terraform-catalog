terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.38.0"
    }
  }
}
provider "aws" {
  region = var.region
}

data "aws_vpc" "main" {
  id = var.vpc_id
}
data "aws_subnet" "public" {
  id = var.public_subnet_id
}
data "aws_subnet" "private" {
  id = var.private_subnet_id
}
data "aws_security_group" "dogstac" {
  filter {
    name   = "tag:Name"
    values = ["${var.name_prefix}-personal-sg"]
  }
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }
}

locals {
  name_prefix = var.name_prefix
  common_tags = {
    ManagedBy = "Terraform"
    creator   = var.creator
    team      = var.team
  }
}

module "rds_database" {
  source = "../../modules/rds"

  name_prefix             = "${local.name_prefix}-rds"
  rds_type                = var.rds_type
  db_username             = var.rds_username
  db_password             = data.aws_ssm_parameter.rds_password.value
  instance_class          = var.rds_instance_class
  allocated_storage       = var.rds_allocated_storage
  subnet_ids              = [data.aws_subnet.private.id, data.aws_subnet.public.id]
  vpc_id                  = data.aws_vpc.main.id
  allowed_security_groups = [data.aws_security_group.dogstac.id]
  backup_retention_period = 0
  common_tags             = local.common_tags
}
