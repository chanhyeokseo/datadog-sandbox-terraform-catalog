# ============================================
# Basic EC2 Module Outputs
# ============================================

output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.host.id
}

output "instance_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.host.public_ip
}

output "instance_private_ip" {
  description = "Private IP address of the EC2 instance"
  value       = aws_instance.host.private_ip
}

output "instance_public_dns" {
  description = "Public DNS name of the EC2 instance"
  value       = aws_instance.host.public_dns
}

output "instance_state" {
  description = "State of the EC2 instance"
  value       = aws_instance.host.instance_state
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i ${var.key_name}.pem ec2-user@${aws_instance.host.public_ip}"
}

output "ami_id" {
  description = "AMI ID used for the instance"
  value       = aws_instance.host.ami
}

output "password_data" {
  description = "Encrypted password data for Windows instances (use rsadecrypt to decrypt)"
  value       = aws_instance.host.password_data
  sensitive   = true
}

