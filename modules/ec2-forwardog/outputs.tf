# ============================================
# EC2 Forwardog Module Outputs
# ============================================

output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.forwardog.id
}

output "instance_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.forwardog.public_ip
}

output "instance_private_ip" {
  description = "Private IP address of the EC2 instance"
  value       = aws_instance.forwardog.private_ip
}

output "instance_public_dns" {
  description = "Public DNS name of the EC2 instance"
  value       = aws_instance.forwardog.public_dns
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i ${var.key_name}.pem ec2-user@${aws_instance.forwardog.public_ip}"
}

output "forwardog_url" {
  description = "URL to access Forwardog service"
  value       = "http://${aws_instance.forwardog.public_ip}:8000"
}

output "docker_compose_logs_command" {
  description = "Command to view all container logs"
  value       = "cd /opt/forwardog && docker compose logs -f"
}

output "docker_compose_status_command" {
  description = "Command to check container status"
  value       = "cd /opt/forwardog && docker compose ps"
}

