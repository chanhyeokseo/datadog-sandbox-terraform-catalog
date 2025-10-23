# ============================================
# Security Group Module Outputs
# ============================================

output "security_group_id" {
  description = "ID of the personal security group"
  value       = aws_security_group.personal.id
}

output "security_group_name" {
  description = "Name of the personal security group"
  value       = aws_security_group.personal.name
}

