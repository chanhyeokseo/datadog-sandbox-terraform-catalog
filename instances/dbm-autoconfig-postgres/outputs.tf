output "instance_id" {
  value = module.dbm_autoconfig_ec2.instance_id
}
output "public_ip" {
  value = module.dbm_autoconfig_ec2.instance_public_ip
}
output "ssh_command" {
  value = module.dbm_autoconfig_ec2.ssh_command
}
output "rds_endpoint" {
  value = module.dbm_autoconfig_rds.db_endpoint
}
output "rds_port" {
  value = module.dbm_autoconfig_rds.db_port
}
