# ============================================
# Terraform Configuration
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

# ============================================
# AWS Provider
# ============================================
provider "aws" {
  region = var.region
  
  # Credentials will be loaded from:
  # 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
  # 2. AWS credentials file (~/.aws/credentials)
  # 3. IAM role (if running on EC2/ECS)
}

# ============================================
# Data Sources
# ============================================

# Get current public IP address
data "http" "my_ip" {
  url = "https://ipv4.icanhazip.com"
}

# Get latest Amazon Linux 2023 AMI
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