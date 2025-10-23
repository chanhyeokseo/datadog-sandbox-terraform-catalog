# # ============================================
# # ECS Cluster
# # ============================================
# resource "aws_ecs_cluster" "main" {
#   name = "${local.project_name_prefix}-ecs-cluster"

#   tags = merge(
#     local.project_common_tags,
#     {
#       Name = "${local.project_name_prefix}-ecs-cluster"
#     }
#   )
# }

# # ============================================
# # IAM Roles for ECS Fargate
# # ============================================

# # ECS Task Execution Role (for Fargate to pull images and write logs)
# resource "aws_iam_role" "ecs_task_execution_role" {
#   name = "${local.project_name_prefix}-ecs-task-execution-role"

#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Action = "sts:AssumeRole"
#         Effect = "Allow"
#         Principal = {
#           Service = "ecs-tasks.amazonaws.com"
#         }
#       }
#     ]
#   })

#   tags = merge(
#     local.project_common_tags,
#     {
#       Name = "${local.project_name_prefix}-ecs-task-execution-role"
#     }
#   )
# }

# # Attach AWS managed policy for ECS task execution
# resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
#   role       = aws_iam_role.ecs_task_execution_role.name
#   policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
# }

# # ECS Task Role (for application to access AWS services)
# resource "aws_iam_role" "ecs_task_role" {
#   name = "${local.project_name_prefix}-ecs-task-role"

#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Action = "sts:AssumeRole"
#         Effect = "Allow"
#         Principal = {
#           Service = "ecs-tasks.amazonaws.com"
#         }
#       }
#     ]
#   })

#   tags = merge(
#     local.project_common_tags,
#     {
#       Name = "${local.project_name_prefix}-ecs-task-role"
#     }
#   )
# }

# # ============================================
# # Security Group for Fargate Tasks
# # ============================================
# resource "aws_security_group" "ecs_tasks" {
#   name        = "${local.project_name_prefix}-ecs-tasks-sg"
#   description = "Security group for ECS Fargate tasks"
#   vpc_id      = aws_vpc.main.id

#   # ingress {
#   #   description = "Allow HTTP"
#   #   from_port   = 80
#   #   to_port     = 80
#   #   protocol    = "tcp"
#   #   cidr_blocks = ["0.0.0.0/0"]
#   # }

#   egress {
#     description = "Allow all outbound traffic"
#     from_port   = 0
#     to_port     = 0
#     protocol    = "-1"
#     cidr_blocks = ["0.0.0.0/0"]
#   }

#   tags = merge(
#     local.project_common_tags,
#     {
#       Name = "${local.project_name_prefix}-ecs-tasks-sg"
#     }
#   )
# }

# # ============================================
# # ECS Task Definition
# # ============================================
# resource "aws_ecs_task_definition" "app" {
#   family                   = "${local.project_name_prefix}-app"
#   network_mode             = "awsvpc"
#   requires_compatibilities = ["FARGATE"]
#   cpu                      = "256"
#   memory                   = "512"
#   execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
#   task_role_arn            = aws_iam_role.ecs_task_role.arn

#   container_definitions = file("ecs-fargate-task-definition.json")

#   tags = merge(
#     local.project_common_tags,
#     {
#       Name = "${local.project_name_prefix}-app-task"
#     }
#   )
# }

# # ============================================
# # ECS Service
# # ============================================
# resource "aws_ecs_service" "app" {
#   name            = "${local.project_name_prefix}-app-service"
#   cluster         = aws_ecs_cluster.main.id
#   task_definition = aws_ecs_task_definition.app.arn
#   desired_count   = 1
#   launch_type     = "FARGATE"

#   network_configuration {
#     subnets          = [aws_subnet.public.id, aws_subnet.public2.id]
#     security_groups  = [aws_security_group.ecs_tasks.id]
#     assign_public_ip = true
#   }

#   tags = merge(
#     local.project_common_tags,
#     {
#       Name = "${local.project_name_prefix}-app-service"
#     }
#   )
# }

# # ============================================
# # Outputs
# # ============================================
# output "ecs_cluster_name" {
#   description = "Name of the ECS cluster"
#   value       = aws_ecs_cluster.main.name
# }

# output "ecs_cluster_arn" {
#   description = "ARN of the ECS cluster"
#   value       = aws_ecs_cluster.main.arn
# }

# output "ecs_service_name" {
#   description = "Name of the ECS service"
#   value       = aws_ecs_service.app.name
# }

# output "ecs_task_definition_arn" {
#   description = "ARN of the ECS task definition"
#   value       = aws_ecs_task_definition.app.arn
# }

# output "ecs_security_group_id" {
#   description = "Security group ID for ECS tasks"
#   value       = aws_security_group.ecs_tasks.id
# }
