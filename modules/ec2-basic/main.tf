# ============================================
# Basic EC2 Instance Module
# ============================================

resource "aws_instance" "host" {
  ami           = var.custom_ami_id
  instance_type = var.instance_type

  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = var.security_group_ids
  associate_public_ip_address = var.associate_public_ip

  key_name = var.key_name

  user_data                   = var.user_data
  user_data_replace_on_change = var.user_data_replace_on_change

  lifecycle {
    ignore_changes = [ami]
  }

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-host"
      service = var.service
    }
  )
}

