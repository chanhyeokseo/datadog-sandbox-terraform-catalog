# ============================================
# Main Configuration
# ============================================
terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
    http = {
      source = "hashicorp/http"
    }
    null = {
      source = "hashicorp/null"
    }
    tls = {
      source = "hashicorp/tls"
    }
  }
}

provider "aws" {
  region = var.region
}

data "http" "my_ip" {
  url = "https://ifconfig.me/ip"
}

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_ami" "windows_2025" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Windows_Server-2025-English-Full-Base-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }
}

data "aws_ami" "windows_2016" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Windows_Server-2016-English-Full-Base-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }
}

data "aws_ami" "windows_2019" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["Windows_Server-2019-English-Full-Base-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }
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

# ============================================
# Local Values
# ============================================
locals {
  project_name_prefix = "${var.project_name}-${var.project_env}"

  project_common_tags = {
    Project     = var.project_name
    Environment = var.project_env
    ManagedBy   = "Terraform"
    creator     = var.creator
    team        = var.team
  }

  my_ip_cidr = "${chomp(data.http.my_ip.response_body)}/32"
}

# ============================================
# VPC Data Sources (External Import)
# ============================================
data "aws_vpc" "main" {
  id = var.vpc_id
}

data "aws_subnet" "public" {
  id = var.public_subnet_id
}

data "aws_subnet" "public2" {
  id = var.public_subnet2_id
}

data "aws_subnet" "private" {
  id = var.private_subnet_id
}

# Wrapper locals for compatibility with existing module references
locals {
  vpc = {
    vpc_id            = data.aws_vpc.main.id
    public_subnet_id  = data.aws_subnet.public.id
    public_subnet2_id = data.aws_subnet.public2.id
    private_subnet_id = data.aws_subnet.private.id
  }
}

# ============================================
# Security Group Module
# ============================================
module "security_group" {
  source = "./modules/security-group"

  name_prefix  = local.project_name_prefix
  project_name = var.project_name
  vpc_id       = local.vpc.vpc_id
  my_ip_cidr   = local.my_ip_cidr

  common_tags = local.project_common_tags
}