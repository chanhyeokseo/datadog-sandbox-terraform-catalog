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
  vpc_name_prefix     = "${var.vpc_name}-${var.vpc_env}"
  project_name_prefix = "${var.project_name}-${var.project_env}"

  vpc_common_tags = {
    VPCName     = "${var.vpc_name}-${var.vpc_env}-vpc"
    Environment = var.vpc_env
    ManagedBy   = "Terraform"
  }

  project_common_tags = {
    Project     = var.project_name
    Environment = var.project_env
    ManagedBy   = "Terraform"
  }

  public_subnet_cidr  = cidrsubnet(var.vpc_cidr, 8, 1)
  public_subnet2_cidr = cidrsubnet(var.vpc_cidr, 8, 2)
  private_subnet_cidr = cidrsubnet(var.vpc_cidr, 8, 3)

  my_ip_cidr = "${chomp(data.http.my_ip.response_body)}/32"
}

# ============================================
# VPC Module
# ============================================
module "vpc" {
  source = "./modules/vpc"

  name_prefix = local.vpc_name_prefix
  vpc_cidr    = var.vpc_cidr

  public_subnet_cidr  = local.public_subnet_cidr
  public_subnet2_cidr = local.public_subnet2_cidr
  private_subnet_cidr = local.private_subnet_cidr

  common_tags = local.vpc_common_tags
}

# VPC Module Outputs
# output "vpc_id" {
#   description = "ID of the VPC"
#   value       = module.vpc.vpc_id
# }

# output "public_subnet_id" {
#   description = "ID of public subnet 1"
#   value       = module.vpc.public_subnet_id
# }

# output "public_subnet2_id" {
#   description = "ID of public subnet 2"
#   value       = module.vpc.public_subnet2_id
# }

# output "private_subnet_id" {
#   description = "ID of private subnet"
#   value       = module.vpc.private_subnet_id
# }

# ============================================
# Security Group Module
# ============================================
module "security_group" {
  source = "./modules/security-group"

  name_prefix  = local.project_name_prefix
  project_name = var.project_name
  vpc_id       = module.vpc.vpc_id
  my_ip_cidr   = local.my_ip_cidr

  common_tags = local.project_common_tags
}

# Security Group Module Outputs
# output "personal_security_group_id" {
#   description = "ID of your personal security group"
#   value       = module.security_group.security_group_id
# }

# output "my_public_ip" {
#   description = "Your detected public IP address"
#   value       = local.my_ip_cidr
# }