moved {
  from = aws_security_group.personal
  to   = aws_security_group.main
}

resource "aws_security_group" "main" {
  name        = "${var.name_prefix}-personal-sg"
  description = "Personal security group for ${var.project_name} EC2 access"
  vpc_id      = var.vpc_id

  dynamic "ingress" {
    for_each = length(var.ingress_rules) > 0 ? var.ingress_rules : [
      {
        description = "Allow SSH from my IP"
        from_port   = 22
        to_port     = 22
        protocol    = "tcp"
        cidr_blocks = [var.my_ip_cidr]
        use_my_ip   = true
      },
      {
        description = "Allow RDP from my IP"
        from_port   = 3389
        to_port     = 3389
        protocol    = "tcp"
        cidr_blocks = [var.my_ip_cidr]
        use_my_ip   = true
      },
      {
        description = "Allow HTTP (8000) from anywhere"
        from_port   = 8000
        to_port     = 8000
        protocol    = "tcp"
        cidr_blocks = [var.my_ip_cidr]
        use_my_ip   = true
      },
      {
        description = "Allow HTTP (80) from anywhere"
        from_port   = 80
        to_port     = 80
        protocol    = "tcp"
        cidr_blocks = [var.my_ip_cidr]
        use_my_ip   = true
      }
    ]
    content {
      description = ingress.value.description
      from_port   = ingress.value.from_port
      to_port     = ingress.value.to_port
      protocol    = ingress.value.protocol
      cidr_blocks = ingress.value.use_my_ip ? [var.my_ip_cidr] : ingress.value.cidr_blocks
    }
  }

  dynamic "egress" {
    for_each = length(var.egress_rules) > 0 ? var.egress_rules : [
      {
        description = "Allow all outbound traffic"
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks = ["0.0.0.0/0"]
        use_my_ip   = false
      }
    ]
    content {
      description = egress.value.description
      from_port   = egress.value.from_port
      to_port     = egress.value.to_port
      protocol    = egress.value.protocol
      cidr_blocks = egress.value.cidr_blocks
    }
  }

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-personal-sg"
      service = var.service
    }
  )
}