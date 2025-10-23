# ============================================
# EC2 Instance
# ============================================
resource "aws_instance" "host" {
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = var.ec2_instance_type

  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.ec2.id]
  associate_public_ip_address = true

  key_name = var.ec2_key_name

  tags = merge(
    local.project_common_tags,
    {
      Name = "${local.project_name_prefix}-host"
    }
  )
}

# ============================================
# Outputs
# ============================================
output "ec2_host_public_ip" {
  description = "Public IP address of the EC2 host"
  value       = aws_instance.host.public_ip
}

output "ec2_host_public_dns" {
  description = "Public DNS name of the EC2 host"
  value       = aws_instance.host.public_dns
}

output "ec2_host_ami_id" {
  description = "AMI ID used for the EC2 host"
  value       = data.aws_ami.amazon_linux_2023.id
}

output "ec2_host_ami_name" {
  description = "AMI name used for the EC2 host"
  value       = data.aws_ami.amazon_linux_2023.name
}

output "ssh_command" {
  description = "SSH command to connect to the EC2 host"
  value       = "ssh -i ${var.ec2_key_name}.pem ec2-user@${aws_instance.host.public_ip}"
}