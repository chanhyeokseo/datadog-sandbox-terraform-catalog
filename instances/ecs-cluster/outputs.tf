output "cluster_name" {
  value = module.ecs_cluster.cluster_name
}

output "cluster_arn" {
  value = module.ecs_cluster.cluster_arn
}

output "region" {
  value = var.region
}

output "enable_fargate" {
  value = var.enable_fargate
}

output "enable_ec2" {
  value = var.enable_ec2
}

output "autoscaling_group_name" {
  value = module.ecs_cluster.autoscaling_group_name
}

output "task_execution_role_arn" {
  value = module.ecs_cluster.task_execution_role_arn
}

output "task_role_arn" {
  value = module.ecs_cluster.task_role_arn
}

output "ec2_instance_type" {
  value = var.ec2_instance_type
}

output "ec2_min_size" {
  value = var.ec2_min_size
}

output "ec2_max_size" {
  value = var.ec2_max_size
}

output "ec2_desired_capacity" {
  value = var.ec2_desired_capacity
}

output "subnet_ids" {
  value = var.enable_ec2 ? [var.public_subnet_id, var.public_subnet2_id] : [var.public_subnet_id, var.public_subnet2_id]
}

output "security_group_ids" {
  value = length(var.security_group_ids) > 0 ? var.security_group_ids : (
    var.enable_ec2 ? try([data.aws_security_group.personal[0].id], []) : []
  )
}
