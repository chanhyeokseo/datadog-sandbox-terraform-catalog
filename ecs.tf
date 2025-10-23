# # ============================================
# # ECS Fargate Basic Configuration
# # ============================================
# module "ecs_fargate" {
#   source = "./modules/ecs-fargate"

#   name_prefix = local.project_name_prefix

#   subnet_ids         = [module.vpc.public_subnet_id, module.vpc.public_subnet2_id]
#   security_group_ids = [module.security_group.security_group_id]
#   assign_public_ip   = true

#   task_cpu      = "256"
#   task_memory   = "512"
#   desired_count = 1

#   container_definitions = file("${path.module}/modules/ecs-fargate/task-definition.json")

#   common_tags = local.project_common_tags
# }

# # ECS Fargate Module Outputs
# output "ecs_cluster_name" {
#   description = "Name of the ECS cluster"
#   value       = module.ecs_fargate.cluster_name
# }

# output "ecs_cluster_arn" {
#   description = "ARN of the ECS cluster"
#   value       = module.ecs_fargate.cluster_arn
# }

# output "ecs_service_name" {
#   description = "Name of the ECS service"
#   value       = module.ecs_fargate.service_name
# }

# output "ecs_task_definition_arn" {
#   description = "ARN of the ECS task definition"
#   value       = module.ecs_fargate.task_definition_arn
# }