# ============================================
# EC2 Datadog Docker Module Outputs
# ============================================

output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.datadog_host.id
}

output "instance_public_ip" {
  description = "Public IP address of the EC2 instance"
  value       = aws_instance.datadog_host.public_ip
}

output "instance_private_ip" {
  description = "Private IP address of the EC2 instance"
  value       = aws_instance.datadog_host.private_ip
}

output "instance_public_dns" {
  description = "Public DNS name of the EC2 instance"
  value       = aws_instance.datadog_host.public_dns
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh -i ${var.key_name}.pem ec2-user@${aws_instance.datadog_host.public_ip}"
}

output "docker_logs_command" {
  description = "Command to view Datadog agent container logs"
  value       = "docker logs -f dd-agent"
}

output "docker_status_command" {
  description = "Command to check Datadog agent status in container"
  value       = "docker exec dd-agent agent status"
}

