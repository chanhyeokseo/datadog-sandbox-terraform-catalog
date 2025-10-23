# ============================================
# ECS Fargate Module
# ============================================

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.name_prefix}-ecs-cluster"

  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-ecs-cluster"
    }
  )
}

# ============================================
# IAM Roles for ECS Fargate
# ============================================

# ECS Task Execution Role (for Fargate to pull images and write logs)
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.name_prefix}-ecs-task-execution-role"

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
      Name = "${var.name_prefix}-ecs-task-execution-role"
    }
  )
}

# Attach AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ECS Task Role (for application to access AWS services)
resource "aws_iam_role" "ecs_task_role" {
  name = "${var.name_prefix}-ecs-task-role"

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
      Name = "${var.name_prefix}-ecs-task-role"
    }
  )
}

# ============================================
# ECS Task Definition
# ============================================
resource "aws_ecs_task_definition" "app" {
  family                   = "${var.name_prefix}-app"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = var.container_definitions

  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-app-task"
    }
  )
}

# ============================================
# ECS Service
# ============================================
resource "aws_ecs_service" "app" {
  name            = "${var.name_prefix}-app-service"
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
      Name = "${var.name_prefix}-app-service"
    }
  )
}

