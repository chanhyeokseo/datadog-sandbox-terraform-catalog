# ============================================
# Basic EC2 Instance Module
# ============================================

# Data source for Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# EC2 Instance
resource "aws_instance" "host" {
  ami           = var.custom_ami_id != "" ? var.custom_ami_id : data.aws_ami.amazon_linux_2023.id
  instance_type = var.instance_type

  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = var.security_group_ids
  associate_public_ip_address = var.associate_public_ip

  key_name = var.key_name

  user_data                   = var.user_data
  user_data_replace_on_change = var.user_data_replace_on_change

  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-host"
    }
  )
}

