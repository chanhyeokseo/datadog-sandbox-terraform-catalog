# ============================================
# ECS Cluster Configurations
# ============================================

# ============================================
# ECS Fargate Only Cluster
# ============================================
module "ecs_fargate" {
  source = "./modules/ecs"

  name_prefix    = "${local.name_prefix}-fargate"
  enable_fargate = var.ecs_enable_fargate
  enable_ec2     = false

  common_tags = local.common_tags
}

output "ecs_fargate_cluster_name" {
  description = "Name of the ECS Fargate cluster"
  value       = module.ecs_fargate.cluster_name
}

output "ecs_fargate_cluster_arn" {
  description = "ARN of the ECS Fargate cluster"
  value       = module.ecs_fargate.cluster_arn
}

# ============================================
# ECS EC2 Cluster
# ============================================
module "ecs_ec2" {
  source = "./modules/ecs"

  name_prefix = "${local.name_prefix}-ec2"

  # Fargate Configuration (optional, set to true if you want to use Fargate)
  enable_fargate = false
  enable_ec2     = var.ecs_enable_ec2

  subnet_ids           = [local.vpc.public_subnet_id, local.vpc.public_subnet2_id]
  security_group_ids   = [module.security_group.security_group_id]
  instance_type        = var.ec2_instance_type
  custom_ami_id        = data.aws_ami.ecs_optimized.id
  key_name             = var.ec2_key_name
  ec2_min_size         = 1
  ec2_max_size         = 3
  ec2_desired_capacity = 1

  common_tags = local.common_tags
}

output "ecs_ec2_cluster_name" {
  description = "Name of the ECS EC2 cluster"
  value       = module.ecs_ec2.cluster_name
}

output "ecs_ec2_cluster_arn" {
  description = "ARN of the ECS EC2 cluster"
  value       = module.ecs_ec2.cluster_arn
}

output "ecs_ec2_asg_name" {
  description = "Name of the ECS EC2 Auto Scaling Group"
  value       = module.ecs_ec2.autoscaling_group_name
}