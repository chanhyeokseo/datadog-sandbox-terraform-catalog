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

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-kernel-*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
data "aws_subnet" "public" {
  id = var.public_subnet_id
}
data "aws_security_group" "personal_sg" {
  name   = "${var.creator}-${var.team}-personal-sg"
  vpc_id = var.vpc_id
}

locals {
  name_prefix = "${var.creator}-${var.team}"
  common_tags = {
    ManagedBy = "Terraform"
    creator   = var.creator
    team      = var.team
  }
  vpc = {
    public_subnet_id = data.aws_subnet.public.id
  }
  security_group_ids = length(var.security_group_ids) > 0 ? var.security_group_ids : [data.aws_security_group.personal_sg.id]
}

module "ec2_basic" {
  source = "git::https://github.com/chanhyeokseo/datadog-sandbox-terraform-catalog.git//modules/ec2-basic?ref=webui-dev"

  name_prefix        = local.name_prefix
  instance_type      = var.ec2_instance_type
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = local.security_group_ids
  key_name           = var.ec2_key_name
  custom_ami_id      = data.aws_ami.amazon_linux_2023.id
  common_tags        = local.common_tags
}
