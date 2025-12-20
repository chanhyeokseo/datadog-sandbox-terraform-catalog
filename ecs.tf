# ============================================
# ECS Cluster Configurations
# ============================================

# ============================================
# ECS Fargate Only Cluster
# ============================================
module "ecs_fargate" {
  source = "./modules/ecs"

  name_prefix    = "${local.project_name_prefix}-fargate"
  enable_fargate = true
  enable_ec2     = false

  common_tags = local.project_common_tags
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
# ECS EC2 Only Cluster
# ============================================
module "ecs_ec2" {
  source = "./modules/ecs"

  name_prefix    = "${local.project_name_prefix}-ec2"
  enable_fargate = false
  enable_ec2     = true

  subnet_ids           = [module.vpc.public_subnet_id, module.vpc.public_subnet2_id]
  security_group_ids   = [module.security_group.security_group_id]
  instance_type        = var.ec2_instance_type
  custom_ami_id        = data.aws_ami.ecs_optimized.id
  key_name             = var.ec2_key_name
  ec2_min_size         = 1
  ec2_max_size         = 3
  ec2_desired_capacity = 1

  common_tags = local.project_common_tags
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

# ============================================
# ECS Hybrid Cluster (Fargate + EC2)
# ============================================
module "ecs_hybrid" {
  source = "./modules/ecs"

  name_prefix    = "${local.project_name_prefix}-hybrid"
  enable_fargate = true
  enable_ec2     = true

  subnet_ids           = [module.vpc.public_subnet_id, module.vpc.public_subnet2_id]
  security_group_ids   = [module.security_group.security_group_id]
  instance_type        = var.ec2_instance_type
  custom_ami_id        = data.aws_ami.ecs_optimized.id
  key_name             = var.ec2_key_name
  ec2_min_size         = 0
  ec2_max_size         = 3
  ec2_desired_capacity = 0

  common_tags = local.project_common_tags
}

output "ecs_hybrid_cluster_name" {
  description = "Name of the ECS Hybrid cluster"
  value       = module.ecs_hybrid.cluster_name
}

output "ecs_hybrid_cluster_arn" {
  description = "ARN of the ECS Hybrid cluster"
  value       = module.ecs_hybrid.cluster_arn
}

output "ecs_hybrid_asg_name" {
  description = "Name of the ECS Hybrid Auto Scaling Group"
  value       = module.ecs_hybrid.autoscaling_group_name
}