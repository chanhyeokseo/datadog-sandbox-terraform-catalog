
output "db_type" {
  description = "Type of database deployed"
  value       = var.rds_type
}

output "db_port" {
  description = "Database port"
  value       = local.selected_engine.port
}

output "security_group_id" {
  description = "ID of the database security group"
  value       = aws_security_group.db.id
}

output "db_instance_id" {
  description = "ID of the RDS instance (null for DocumentDB)"
  value       = local.is_docdb ? null : aws_db_instance.main[0].id
}

output "db_instance_arn" {
  description = "ARN of the RDS instance (null for DocumentDB)"
  value       = local.is_docdb ? null : aws_db_instance.main[0].arn
}

output "db_endpoint" {
  description = "Database endpoint (hostname)"
  value       = local.is_docdb ? aws_docdb_cluster.main[0].endpoint : aws_db_instance.main[0].address
}

output "db_connection_string" {
  description = "Full connection endpoint with port"
  value       = local.is_docdb ? "${aws_docdb_cluster.main[0].endpoint}:${local.selected_engine.port}" : "${aws_db_instance.main[0].address}:${local.selected_engine.port}"
}

output "docdb_cluster_id" {
  description = "ID of the DocumentDB cluster (null for RDS)"
  value       = local.is_docdb ? aws_docdb_cluster.main[0].id : null
}

output "docdb_cluster_arn" {
  description = "ARN of the DocumentDB cluster (null for RDS)"
  value       = local.is_docdb ? aws_docdb_cluster.main[0].arn : null
}

output "docdb_reader_endpoint" {
  description = "Reader endpoint for DocumentDB cluster (null for RDS)"
  value       = local.is_docdb ? aws_docdb_cluster.main[0].reader_endpoint : null
}

