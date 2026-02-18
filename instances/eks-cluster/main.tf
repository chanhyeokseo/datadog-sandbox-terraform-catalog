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
  name_prefix = var.name_prefix
  common_tags = {
    ManagedBy = "Terraform"
    creator   = var.creator
    team      = var.team
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

  name_prefix = local.name_prefix
  region      = var.region
  vpc_id      = local.vpc.vpc_id
  subnet_ids  = [local.vpc.public_subnet_id, local.vpc.public_subnet2_id]

  enable_node_group   = var.enable_node_group
  node_instance_types = var.node_instance_types
  node_desired_size   = var.node_desired_size
  node_min_size       = var.node_min_size
  node_max_size       = var.node_max_size
  node_disk_size      = var.node_disk_size
  node_capacity_type  = var.node_capacity_type

  enable_windows_node_group   = var.enable_windows_node_group
  windows_node_instance_types = var.windows_node_instance_types
  windows_node_ami_type       = var.windows_node_ami_type
  windows_node_desired_size   = var.windows_node_desired_size
  windows_node_min_size       = var.windows_node_min_size
  windows_node_max_size       = var.windows_node_max_size
  windows_node_disk_size      = var.windows_node_disk_size
  windows_node_capacity_type  = var.windows_node_capacity_type

  enable_fargate     = var.enable_fargate
  fargate_subnet_ids = [local.vpc.private_subnet_id]
  fargate_namespaces = var.fargate_namespaces

  endpoint_public_access  = var.endpoint_public_access
  endpoint_private_access = var.endpoint_private_access
  common_tags             = local.common_tags
}
