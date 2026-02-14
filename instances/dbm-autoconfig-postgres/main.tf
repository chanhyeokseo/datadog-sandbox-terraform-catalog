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
data "aws_vpc" "main" {
  id = var.vpc_id
}
data "aws_subnet" "public" {
  id = var.public_subnet_id
}
data "aws_subnet" "private" {
  id = var.private_subnet_id
}

locals {
  name_prefix = "${var.creator}-${var.team}"
  common_tags = {
    ManagedBy = "Terraform"
    creator   = var.creator
    team      = var.team
  }
  vpc = {
    vpc_id            = data.aws_vpc.main.id
    public_subnet_id  = data.aws_subnet.public.id
    private_subnet_id = data.aws_subnet.private.id
  }
}

module "dbm_autoconfig_ec2" {
  source = "git::https://github.com/chanhyeokseo/datadog-sandbox-terraform-catalog.git//modules/ec2-datadog-host?ref=webui-dev"

  name_prefix        = "${local.name_prefix}-dbm-autoconfig"
  instance_type      = var.ec2_instance_type
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = var.security_group_ids
  key_name           = var.ec2_key_name
  custom_ami_id      = data.aws_ami.amazon_linux_2023.id
  datadog_api_key       = var.datadog_api_key
  datadog_site          = var.datadog_site
  datadog_agent_version = var.datadog_agent_version
  creator               = var.creator
  team                  = var.team
  common_tags           = local.common_tags
}

module "dbm_autoconfig_rds" {
  source = "git::https://github.com/chanhyeokseo/datadog-sandbox-terraform-catalog.git//modules/rds?ref=webui-dev"

  name_prefix             = "${local.name_prefix}-dbm-autoconfig"
  rds_type                = "postgres"
  db_name                 = "datadog"
  db_username             = var.rds_username
  db_password             = var.rds_password
  instance_class          = var.rds_instance_class
  allocated_storage       = 20
  subnet_ids              = [local.vpc.private_subnet_id, local.vpc.public_subnet_id]
  vpc_id                  = local.vpc.vpc_id
  allowed_security_groups = var.security_group_ids
  common_tags             = local.common_tags
}
