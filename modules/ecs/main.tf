
resource "aws_ecs_cluster" "main" {
  name = "${var.name_prefix}-ecs-cluster"

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-ecs-cluster"
      service = var.service
    }
  )
}


resource "aws_ecs_cluster_capacity_providers" "main" {
  count        = var.enable_fargate || var.enable_ec2 ? 1 : 0
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = concat(
    var.enable_fargate ? ["FARGATE", "FARGATE_SPOT"] : [],
    var.enable_ec2 ? [aws_ecs_capacity_provider.ec2[0].name] : []
  )

  dynamic "default_capacity_provider_strategy" {
    for_each = var.enable_fargate ? [1] : []
    content {
      base              = 0
      weight            = 1
      capacity_provider = "FARGATE"
    }
  }
}

resource "aws_ecs_capacity_provider" "ec2" {
  count = var.enable_ec2 ? 1 : 0
  name  = "${var.name_prefix}-ecs-ec2-cp"

  auto_scaling_group_provider {
    auto_scaling_group_arn = aws_autoscaling_group.ecs[0].arn

    managed_scaling {
      maximum_scaling_step_size = 2
      minimum_scaling_step_size = 1
      status                    = "ENABLED"
      target_capacity           = 100
    }
  }

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-ecs-ec2-cp"
      service = var.service
    }
  )
}


resource "aws_autoscaling_group" "ecs" {
  count               = var.enable_ec2 ? 1 : 0
  name                = "${var.name_prefix}-ecs-asg"
  vpc_zone_identifier = var.subnet_ids
  min_size            = var.ec2_min_size
  max_size            = var.ec2_max_size
  desired_capacity    = var.ec2_desired_capacity

  launch_template {
    id      = aws_launch_template.ecs[0].id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "${var.name_prefix}-ecs-instance"
    propagate_at_launch = true
  }

  tag {
    key                 = "AmazonECSManaged"
    value               = "true"
    propagate_at_launch = true
  }

  dynamic "tag" {
    for_each = merge(var.common_tags, { service = var.service })
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_launch_template" "ecs" {
  count         = var.enable_ec2 ? 1 : 0
  name          = "${var.name_prefix}-ecs-launch-template"
  image_id      = var.custom_ami_id
  instance_type = var.instance_type

  vpc_security_group_ids = var.security_group_ids

  iam_instance_profile {
    name = aws_iam_instance_profile.ecs_instance[0].name
  }

  key_name = var.key_name

  user_data = base64encode(<<-EOF
    #!/bin/bash
    echo ECS_CLUSTER=${aws_ecs_cluster.main.name} >> /etc/ecs/ecs.config
    ${var.additional_user_data}
  EOF
  )

  tag_specifications {
    resource_type = "instance"
    tags = merge(
      var.common_tags,
      {
        Name    = "${var.name_prefix}-ecs-instance"
        service = var.service
      }
    )
  }

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-ecs-launch-template"
      service = var.service
    }
  )
}


resource "aws_iam_role" "ecs_instance_role" {
  count = var.enable_ec2 ? 1 : 0
  name  = "${var.name_prefix}-ecs-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-ecs-instance-role"
      service = var.service
    }
  )
}

resource "aws_iam_role_policy_attachment" "ecs_instance_role_policy" {
  count      = var.enable_ec2 ? 1 : 0
  role       = aws_iam_role.ecs_instance_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_instance_profile" "ecs_instance" {
  count = var.enable_ec2 ? 1 : 0
  name  = "${var.name_prefix}-ecs-instance-profile"
  role  = aws_iam_role.ecs_instance_role[0].name

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-ecs-instance-profile"
      service = var.service
    }
  )
}


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
      Name    = "${var.name_prefix}-ecs-task-execution-role"
      service = var.service
    }
  )
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

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
      Name    = "${var.name_prefix}-ecs-task-role"
      service = var.service
    }
  )
}

