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

  # RDP access from your IP
  ingress {
    description = "Allow RDP from my IP"
    from_port   = 3389
    to_port     = 3389
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  # HTTP access for FastAPI app (open to world for testing)
  ingress {
    description = "Allow HTTP (8000) from anywhere"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  # HTTP access for general web traffic
  ingress {
    description = "Allow HTTP (80) from anywhere"
    from_port   = 80
    to_port     = 80
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
      Name    = "${var.name_prefix}-personal-sg"
      service = var.service
    }
  )
}