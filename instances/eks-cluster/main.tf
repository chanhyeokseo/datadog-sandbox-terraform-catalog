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

locals {
  project_name_prefix = "${var.project_name}-${var.project_env}"
  project_common_tags = {
    Project     = var.project_name
    Environment = var.project_env
    ManagedBy   = "Terraform"
    creator     = var.creator
    team        = var.team
  }
  vpc = {
    vpc_id            = data.aws_vpc.main.id
    public_subnet_id  = data.aws_subnet.public.id
    public_subnet2_id = data.aws_subnet.public2.id
    private_subnet_id = data.aws_subnet.private.id
  }
}

module "eks_cluster" {
  source = "../../modules/eks"

  name_prefix = local.project_name_prefix
  region      = var.region
  vpc_id      = local.vpc.vpc_id
  subnet_ids  = [local.vpc.public_subnet_id, local.vpc.public_subnet2_id]

  enable_node_group   = true
  node_instance_types = ["t3.medium"]
  node_desired_size   = 2
  node_min_size       = 1
  node_max_size       = 4
  node_disk_size      = 20
  node_capacity_type  = "ON_DEMAND"

  enable_windows_node_group   = true
  windows_node_instance_types = ["t3.medium"]
  windows_node_ami_type       = "WINDOWS_FULL_2022_x86_64"
  windows_node_desired_size   = 2
  windows_node_min_size       = 1
  windows_node_max_size       = 4
  windows_node_disk_size      = 50
  windows_node_capacity_type  = "ON_DEMAND"

  enable_fargate     = true
  fargate_subnet_ids = [local.vpc.private_subnet_id]
  fargate_namespaces = ["default", "kube-system"]

  endpoint_public_access  = true
  endpoint_private_access = true
  common_tags             = local.project_common_tags
}
