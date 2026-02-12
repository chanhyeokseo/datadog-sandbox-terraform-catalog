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
  id = var.public_subnet_id
}
data "aws_subnet" "public2" {
  id = var.public_subnet2_id
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

module "ecs_ec2" {
  source = "../../modules/ecs"

  name_prefix    = "${local.project_name_prefix}-ec2"
  enable_fargate = false
  enable_ec2     = var.ecs_enable_ec2

  subnet_ids           = [data.aws_subnet.public.id, data.aws_subnet.public2.id]
  security_group_ids   = var.security_group_ids
  instance_type        = var.ec2_instance_type
  custom_ami_id        = data.aws_ami.ecs_optimized.id
  key_name             = var.ec2_key_name
  ec2_min_size         = 1
  ec2_max_size         = 3
  ec2_desired_capacity = 1

  common_tags = local.project_common_tags
}
