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

data "aws_ami" "ecs_optimized" {
  count       = var.enable_ec2 ? 1 : 0
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-ecs-hvm-*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_subnet" "public" {
  count = var.enable_ec2 ? 1 : 0
  id    = var.public_subnet_id
}

data "aws_subnet" "public2" {
  count = var.enable_ec2 ? 1 : 0
  id    = var.public_subnet2_id
}

data "aws_security_group" "personal" {
  count = var.enable_ec2 ? 1 : 0

  filter {
    name   = "group-name"
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
  sg_ids = var.enable_ec2 ? (
    length(var.security_group_ids) > 0
      ? var.security_group_ids
      : try([data.aws_security_group.personal[0].id], [])
  ) : []
}

module "ecs_cluster" {
  source = "../../modules/ecs"

  name_prefix    = local.name_prefix
  enable_fargate = var.enable_fargate
  enable_ec2     = var.enable_ec2

  subnet_ids           = var.enable_ec2 ? [data.aws_subnet.public[0].id, data.aws_subnet.public2[0].id] : []
  security_group_ids   = local.sg_ids
  instance_type        = var.ec2_instance_type
  custom_ami_id        = var.enable_ec2 ? data.aws_ami.ecs_optimized[0].id : null
  key_name             = var.enable_ec2 ? var.ec2_key_name : null
  ec2_min_size         = var.ec2_min_size
  ec2_max_size         = var.ec2_max_size
  ec2_desired_capacity = var.ec2_desired_capacity

  common_tags = local.common_tags
}
