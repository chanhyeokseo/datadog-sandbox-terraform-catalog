output "security_group_id" {
  description = "ID of the security group"
  value       = aws_security_group.main.id
}

output "security_group_name" {
  description = "Name of the security group"
  value       = aws_security_group.main.name
}

output "security_group_ingress_rules" {
  description = "Ingress rules of the security group"
  value       = aws_security_group.main.ingress
}

output "security_group_egress_rules" {
  description = "Egress rules of the security group"
  value       = aws_security_group.main.egress
}

