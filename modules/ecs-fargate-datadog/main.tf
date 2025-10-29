# ============================================
# ECS Fargate Datadog Module
# ============================================

# Get AWS account ID and region
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Generate container definitions from template
locals {
  container_definitions = templatefile("${path.module}/task-definition.json.tpl", {
    datadog_api_key = var.datadog_api_key
    datadog_site    = var.datadog_site
    aws_account_id  = data.aws_caller_identity.current.account_id
    aws_region      = data.aws_region.current.name
    app_image       = var.app_image
  })
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.name_prefix}-ecs-datadog-cluster"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-ecs-datadog-cluster"
    }
  )
}

# ============================================
# IAM Roles for ECS Fargate with Datadog
# ============================================

# ECS Task Execution Role (for Fargate to pull images and write logs)
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.name_prefix}-datadog-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-datadog-task-execution-role"
    }
  )
}

# Attach AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ECS Task Role (for Datadog agent to access ECS metrics)
resource "aws_iam_role" "ecs_task_role" {
  name = "${var.name_prefix}-datadog-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-datadog-task-role"
    }
  )
}

# Policy for Datadog agent to access ECS metrics
resource "aws_iam_role_policy" "datadog_ecs_access" {
  name = "fargate-task-role-default-policy"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:ListClusters",
          "ecs:ListContainerInstances",
          "ecs:DescribeContainerInstances"
        ]
        Resource = "*"
      }
    ]
  })
}

# ============================================
# ECS Task Definition
# ============================================
resource "aws_ecs_task_definition" "app" {
  family                   = "${var.name_prefix}-datadog-app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = local.container_definitions

  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-datadog-app-task"
    }
  )
}

# ============================================
# ECS Service
# ============================================
resource "aws_ecs_service" "app" {
  name            = "${var.name_prefix}-datadog-app-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = var.assign_public_ip
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-datadog-app-service"
    }
  )
}

