# ============================================
# Datadog DBM Configuration
# ============================================
# This file creates a complete DBM setup with:
# - EC2 instance with Datadog Agent
# - RDS PostgreSQL instance

# ============================================
# PostgreSQL DBM
# ============================================
module "dbm_postgres_ec2" {
  source = "./modules/ec2-datadog-host"

  name_prefix        = "${local.name_prefix}-dbm-postgres"
  instance_type      = var.ec2_instance_type
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = [module.security_group.security_group_id]
  key_name           = var.ec2_key_name
  custom_ami_id      = data.aws_ami.amazon_linux_2023.id

  datadog_api_key = var.datadog_api_key
  datadog_site    = var.datadog_site
  creator = var.creator
  team    = var.team

  common_tags = local.common_tags
}

module "dbm_postgres_rds" {
  source = "./modules/rds"

  name_prefix = "${local.name_prefix}-dbm"
  rds_type    = "postgres"

  db_name     = "datadog"
  db_username = var.rds_username
  db_password = var.rds_password

  instance_class    = var.rds_instance_class
  allocated_storage = 20

  subnet_ids              = [local.vpc.private_subnet_id, local.vpc.public_subnet_id]
  vpc_id                  = local.vpc.vpc_id
  allowed_security_groups = [module.security_group.security_group_id]

  common_tags = local.common_tags
}

output "dbm_postgres_ec2_ssh" {
  description = "SSH command for PostgreSQL DBM test EC2"
  value       = module.dbm_postgres_ec2.ssh_command
}

output "dbm_postgres_ec2_ip" {
  description = "Public IP of PostgreSQL DBM test EC2"
  value       = module.dbm_postgres_ec2.instance_public_ip
}

output "dbm_postgres_rds_endpoint" {
  description = "PostgreSQL RDS endpoint"
  value       = module.dbm_postgres_rds.db_endpoint
}

output "dbm_postgres_rds_port" {
  description = "PostgreSQL RDS port"
  value       = module.dbm_postgres_rds.db_port
}