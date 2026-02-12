output "cluster_name" {
  value = module.ecs_ec2.cluster_name
}
output "cluster_arn" {
  value = module.ecs_ec2.cluster_arn
}
output "autoscaling_group_name" {
  value = module.ecs_ec2.autoscaling_group_name
}
