# # ============================================
# # Datadog DBM Configuration
# # ============================================
# This file creates a complete DBM setup with:
# - EC2 instance with Datadog Agent
# - RDS PostgreSQL instance

# ============================================
# PostgreSQL DBM Test
# ============================================
module "dbm_postgres_ec2" {
  source = "./modules/ec2-datadog-host"

  name_prefix        = "${local.project_name_prefix}-dbm-postgres"
  instance_type      = var.ec2_instance_type
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = [module.security_group.security_group_id]
  key_name           = var.ec2_key_name
  custom_ami_id      = data.aws_ami.amazon_linux_2023.id

  datadog_api_key = var.datadog_api_key
  datadog_site    = var.datadog_site
  project_name    = var.project_name
  environment     = var.project_env

  common_tags = local.project_common_tags
}

module "dbm_postgres_rds" {
  source = "./modules/rds"

  name_prefix = "${local.project_name_prefix}-dbm"
  rds_type    = "postgres"

  db_name     = "datadog"
  db_username = var.rds_username
  db_password = var.rds_password

  instance_class    = var.rds_instance_class
  allocated_storage = 20

  subnet_ids              = [local.vpc.private_subnet_id, local.vpc.public_subnet_id]
  vpc_id                  = local.vpc.vpc_id
  allowed_security_groups = [module.security_group.security_group_id]

  common_tags = local.project_common_tags
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

# # ============================================
# # MySQL DBM Test
# # ============================================
# module "dbm_mysql_ec2" {
#   source = "./modules/ec2-datadog-host"

#   name_prefix        = "${local.project_name_prefix}-dbm-mysql"
#   instance_type      = var.ec2_instance_type
#   subnet_id          = local.vpc.public_subnet_id
#   security_group_ids = [module.security_group.security_group_id]
#   key_name           = var.ec2_key_name
#   custom_ami_id      = data.aws_ami.amazon_linux_2023.id

#   datadog_api_key = var.datadog_api_key
#   datadog_site    = var.datadog_site
#   project_name    = var.project_name
#   environment     = var.project_env

#   common_tags = local.project_common_tags
# }

# module "dbm_mysql_rds" {
#   source = "./modules/rds"

#   name_prefix = "${local.project_name_prefix}-dbm"
#   rds_type    = "mysql"

#   db_name     = "datadog"
#   db_username = var.rds_username
#   db_password = var.rds_password

#   instance_class    = var.rds_instance_class
#   allocated_storage = 20

#   subnet_ids              = [local.vpc.private_subnet_id, local.vpc.public_subnet_id]
#   vpc_id                  = local.vpc.vpc_id
#   allowed_security_groups = [module.security_group.security_group_id]

#   common_tags = local.project_common_tags
# }

# output "dbm_mysql_ec2_ssh" {
#   description = "SSH command for MySQL DBM test EC2"
#   value       = module.dbm_mysql_ec2.ssh_command
# }

# output "dbm_mysql_ec2_ip" {
#   description = "Public IP of MySQL DBM test EC2"
#   value       = module.dbm_mysql_ec2.instance_public_ip
# }

# output "dbm_mysql_rds_endpoint" {
#   description = "MySQL RDS endpoint"
#   value       = module.dbm_mysql_rds.db_endpoint
# }

# output "dbm_mysql_rds_port" {
#   description = "MySQL RDS port"
#   value       = module.dbm_mysql_rds.db_port
# }

# # ============================================
# # Oracle DBM Test
# # ============================================
# module "dbm_oracle_ec2" {
#   source = "./modules/ec2-datadog-host"

#   name_prefix        = "${local.project_name_prefix}-dbm-oracle"
#   instance_type      = var.ec2_instance_type
#   subnet_id          = local.vpc.public_subnet_id
#   security_group_ids = [module.security_group.security_group_id]
#   key_name           = var.ec2_key_name
#   custom_ami_id      = data.aws_ami.amazon_linux_2023.id

#   datadog_api_key = var.datadog_api_key
#   datadog_site    = var.datadog_site
#   project_name    = var.project_name
#   environment     = var.project_env

#   common_tags = local.project_common_tags
# }

# module "dbm_oracle_rds" {
#   source = "./modules/rds"

#   name_prefix = "${local.project_name_prefix}-dbm"
#   rds_type    = "oracle"

#   db_username = var.rds_username
#   db_password = var.rds_password

#   instance_class    = "db.m5.large"  # Oracle requires larger instance
#   allocated_storage = 20

#   subnet_ids              = [local.vpc.private_subnet_id, local.vpc.public_subnet_id]
#   vpc_id                  = local.vpc.vpc_id
#   allowed_security_groups = [module.security_group.security_group_id]

#   common_tags = local.project_common_tags
# }

# output "dbm_oracle_ec2_ssh" {
#   description = "SSH command for Oracle DBM test EC2"
#   value       = module.dbm_oracle_ec2.ssh_command
# }

# output "dbm_oracle_ec2_ip" {
#   description = "Public IP of Oracle DBM test EC2"
#   value       = module.dbm_oracle_ec2.instance_public_ip
# }

# output "dbm_oracle_rds_endpoint" {
#   description = "Oracle RDS endpoint"
#   value       = module.dbm_oracle_rds.db_endpoint
# }

# output "dbm_oracle_rds_port" {
#   description = "Oracle RDS port"
#   value       = module.dbm_oracle_rds.db_port
# }

# # ============================================
# # SQL Server DBM Test
# # ============================================
# module "dbm_sqlserver_ec2" {
#   source = "./modules/ec2-datadog-host"

#   name_prefix        = "${local.project_name_prefix}-dbm-sqlserver"
#   instance_type      = var.ec2_instance_type
#   subnet_id          = local.vpc.public_subnet_id
#   security_group_ids = [module.security_group.security_group_id]
#   key_name           = var.ec2_key_name
#   custom_ami_id      = data.aws_ami.amazon_linux_2023.id

#   datadog_api_key = var.datadog_api_key
#   datadog_site    = var.datadog_site
#   project_name    = var.project_name
#   environment     = var.project_env

#   common_tags = local.project_common_tags
# }

# module "dbm_sqlserver_rds" {
#   source = "./modules/rds"

#   name_prefix = "${local.project_name_prefix}-dbm"
#   rds_type    = "sqlserver"

#   db_username = var.rds_username
#   db_password = var.rds_password

#   instance_class    = var.rds_instance_class
#   allocated_storage = 20

#   subnet_ids              = [local.vpc.private_subnet_id, local.vpc.public_subnet_id]
#   vpc_id                  = local.vpc.vpc_id
#   allowed_security_groups = [module.security_group.security_group_id]

#   common_tags = local.project_common_tags
# }

# output "dbm_sqlserver_ec2_ssh" {
#   description = "SSH command for SQL Server DBM test EC2"
#   value       = module.dbm_sqlserver_ec2.ssh_command
# }

# output "dbm_sqlserver_ec2_ip" {
#   description = "Public IP of SQL Server DBM test EC2"
#   value       = module.dbm_sqlserver_ec2.instance_public_ip
# }

# output "dbm_sqlserver_rds_endpoint" {
#   description = "SQL Server RDS endpoint"
#   value       = module.dbm_sqlserver_rds.db_endpoint
# }

# output "dbm_sqlserver_rds_port" {
#   description = "SQL Server RDS port"
#   value       = module.dbm_sqlserver_rds.db_port
# }

# # ============================================
# # Amazon DocumentDB DBM Test
# # ============================================
# module "dbm_docdb_ec2" {
#   source = "./modules/ec2-datadog-host"

#   name_prefix        = "${local.project_name_prefix}-dbm-docdb"
#   instance_type      = var.ec2_instance_type
#   subnet_id          = local.vpc.public_subnet_id
#   security_group_ids = [module.security_group.security_group_id]
#   key_name           = var.ec2_key_name
#   custom_ami_id      = data.aws_ami.amazon_linux_2023.id

#   datadog_api_key = var.datadog_api_key
#   datadog_site    = var.datadog_site
#   project_name    = var.project_name
#   environment     = var.project_env

#   common_tags = local.project_common_tags
# }

# module "dbm_docdb" {
#   source = "./modules/rds"

#   name_prefix = "${local.project_name_prefix}-dbm"
#   rds_type    = "docdb"

#   db_username = var.rds_username
#   db_password = var.rds_password

#   instance_class = "db.t3.medium"  # DocumentDB minimum instance

#   subnet_ids              = [local.vpc.private_subnet_id, local.vpc.public_subnet_id]
#   vpc_id                  = local.vpc.vpc_id
#   allowed_security_groups = [module.security_group.security_group_id]

#   common_tags = local.project_common_tags
# }

# output "dbm_docdb_ec2_ssh" {
#   description = "SSH command for DocumentDB DBM test EC2"
#   value       = module.dbm_docdb_ec2.ssh_command
# }

# output "dbm_docdb_ec2_ip" {
#   description = "Public IP of DocumentDB DBM test EC2"
#   value       = module.dbm_docdb_ec2.instance_public_ip
# }

# output "dbm_docdb_endpoint" {
#   description = "DocumentDB cluster endpoint"
#   value       = module.dbm_docdb.db_endpoint
# }

# output "dbm_docdb_reader_endpoint" {
#   description = "DocumentDB reader endpoint"
#   value       = module.dbm_docdb.docdb_reader_endpoint
# }

# output "dbm_docdb_port" {
#   description = "DocumentDB port"
#   value       = module.dbm_docdb.db_port
# }

