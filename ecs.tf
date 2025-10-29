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

# # ============================================
# # ECS Fargate with Datadog Agent Configuration
# # ============================================
# # NOTE: To enable this module, you must first uncomment resources in ecr.tf
# #       (ECR repository, Docker build/push, and related outputs)
# module "ecs_fargate_datadog" {
#   source = "./modules/ecs-fargate-datadog"

#   name_prefix = local.project_name_prefix

#   subnet_ids         = [module.vpc.public_subnet_id, module.vpc.public_subnet2_id]
#   security_group_ids = [module.security_group.security_group_id]
#   assign_public_ip   = true

#   task_cpu      = "256"
#   task_memory   = "512"
#   desired_count = 1

#   datadog_api_key = var.datadog_api_key
#   datadog_site    = var.datadog_site

#   app_image = "fastapi-dogstatsd:latest"
  
#   depends_on = [null_resource.docker_build_push]

#   common_tags = local.project_common_tags
# }

# # ECS Fargate Datadog Module Outputs
# output "ecs_datadog_cluster_name" {
#   description = "Name of the ECS cluster with Datadog"
#   value       = module.ecs_fargate_datadog.cluster_name
# }

# output "ecs_datadog_cluster_arn" {
#   description = "ARN of the ECS cluster with Datadog"
#   value       = module.ecs_fargate_datadog.cluster_arn
# }

# output "ecs_datadog_service_name" {
#   description = "Name of the ECS service with Datadog"
#   value       = module.ecs_fargate_datadog.service_name
# }

# output "ecs_datadog_task_definition_arn" {
#   description = "ARN of the ECS task definition with Datadog"
#   value       = module.ecs_fargate_datadog.task_definition_arn
# }

# output "ecs_datadog_task_role_arn" {
#   description = "ARN of the ECS task role with Datadog permissions"
#   value       = module.ecs_fargate_datadog.task_role_arn
# }

# output "ecs_datadog_app_image_uri" {
#   description = "Full URI of the application Docker image being used"
#   value       = module.ecs_fargate_datadog.app_image_uri
# }