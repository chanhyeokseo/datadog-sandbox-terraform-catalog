output "rds_endpoint" {
  value = module.rds_database.db_endpoint
}
output "rds_port" {
  value = module.rds_database.db_port
}
output "db_type" {
  value = module.rds_database.db_type
}
output "db_instance_id" {
  value = module.rds_database.db_instance_id
}
output "security_group_id" {
  value = module.rds_database.security_group_id
}
