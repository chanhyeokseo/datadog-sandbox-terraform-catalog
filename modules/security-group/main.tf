# ============================================
# Personal Security Group Module
# ============================================

resource "aws_security_group" "personal" {
  name        = "${var.name_prefix}-personal-sg"
  description = "Personal security group for ${var.project_name} EC2 access"
  vpc_id      = var.vpc_id

  # SSH access from your IP
  ingress {
    description = "Allow SSH from my IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-personal-sg"
    }
  )
}

