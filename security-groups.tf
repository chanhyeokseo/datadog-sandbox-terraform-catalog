# ============================================
# Security Groups
# ============================================

# Personal Security Group for EC2 access
resource "aws_security_group" "personal_ec2" {
  name        = "${local.project_name_prefix}-personal-sg"
  description = "Personal security group for ${var.project_name} EC2 access"
  vpc_id      = aws_vpc.main.id

  # SSH access from your IP
  ingress {
    description = "Allow SSH from my IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [local.my_ip_cidr]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    local.project_common_tags,
    {
      Name = "${local.project_name_prefix}-personal-sg"
    }
  )
}