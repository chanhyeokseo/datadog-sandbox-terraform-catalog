# ============================================
# ECS Cluster Module Outputs
# ============================================

output "cluster_id" {
  description = "ID of the ECS cluster"
  value       = aws_ecs_cluster.main.id
}

output "cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.main.arn
}

# ============================================
# EC2 Outputs (Conditional)
# ============================================

output "ec2_capacity_provider_name" {
  description = "Name of the EC2 capacity provider"
  value       = var.enable_ec2 ? aws_ecs_capacity_provider.ec2[0].name : null
}

output "autoscaling_group_name" {
  description = "Name of the Auto Scaling Group"
  value       = var.enable_ec2 ? aws_autoscaling_group.ecs[0].name : null
}

output "autoscaling_group_arn" {
  description = "ARN of the Auto Scaling Group"
  value       = var.enable_ec2 ? aws_autoscaling_group.ecs[0].arn : null
}

output "launch_template_id" {
  description = "ID of the Launch Template"
  value       = var.enable_ec2 ? aws_launch_template.ecs[0].id : null
}

output "ecs_instance_role_arn" {
  description = "ARN of the ECS EC2 instance role"
  value       = var.enable_ec2 ? aws_iam_role.ecs_instance_role[0].arn : null
}

output "ecs_instance_profile_arn" {
  description = "ARN of the ECS EC2 instance profile"
  value       = var.enable_ec2 ? aws_iam_instance_profile.ecs_instance[0].arn : null
}

# ============================================
# Task IAM Outputs (Always)
# ============================================

output "task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = aws_iam_role.ecs_task_execution_role.arn
}

output "task_role_arn" {
  description = "ARN of the ECS task role"
  value       = aws_iam_role.ecs_task_role.arn
}

