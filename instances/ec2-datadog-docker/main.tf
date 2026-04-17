# EC2 Linux with Datadog Container Agent
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
  name   = "${var.name_prefix}-personal-sg"
  vpc_id = var.vpc_id
}

locals {
  name_prefix = var.name_prefix
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

module "ec2_datadog_docker" {
  source = "../../modules/ec2-datadog-docker"

  name_prefix        = local.name_prefix
  instance_type      = var.ec2_instance_type
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = local.security_group_ids
  key_name            = var.ec2_key_name
  custom_ami_id       = data.aws_ami.amazon_linux_2023.id
  associate_public_ip        = var.ec2_associate_public_ip
  root_volume_size           = var.ec2_root_volume_size
  root_volume_type           = var.ec2_root_volume_type
  enable_detailed_monitoring = var.ec2_enable_detailed_monitoring
  datadog_api_key      = data.aws_ssm_parameter.datadog_api_key.value
  datadog_site         = var.datadog_site
  datadog_agent_image  = var.datadog_agent_image
  docker_run_command   = var.docker_run_command
  creator              = var.creator
  team                 = var.team
  common_tags          = local.common_tags
}
