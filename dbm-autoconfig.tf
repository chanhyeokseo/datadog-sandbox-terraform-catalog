# # ============================================
# # Datadog DBM Auto-Configuration
# # ============================================
# # This file creates a complete DBM setup with:
# # - EC2 instance with Datadog Agent
# # - RDS PostgreSQL instance
# # - Datadog Agent configuration for DBM
# # - PostgreSQL DBM configuration

# # ============================================
# # PostgreSQL DBM Auto-Config EC2
# # ============================================
# module "dbm_autoconfig_ec2" {
#   source = "./modules/ec2-datadog-host"

#   name_prefix        = "${local.project_name_prefix}-dbm-autoconfig"
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

# # ============================================
# # PostgreSQL RDS for DBM Auto-Config
# # ============================================
# module "dbm_autoconfig_rds" {
#   source = "./modules/rds"

#   name_prefix = "${local.project_name_prefix}-dbm-autoconfig"
#   rds_type    = "postgres"

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

# # ============================================
# # Null Resource for DBM Auto-Configuration
# # ============================================
# # This runs after both EC2 and RDS are created to:
# # 1. Set up PostgreSQL datadog user, schema, and functions
# # 2. Configure Datadog Agent for DBM

# resource "null_resource" "dbm_autoconfig_setup" {
#   depends_on = [
#     module.dbm_autoconfig_ec2,
#     module.dbm_autoconfig_rds
#   ]

#   # Re-run if RDS endpoint changes
#   triggers = {
#     rds_endpoint = module.dbm_autoconfig_rds.db_endpoint
#     ec2_id       = module.dbm_autoconfig_ec2.instance_id
#   }

#   connection {
#     type        = "ssh"
#     user        = "ec2-user"
#     private_key = file(pathexpand(var.ssh_private_key_path))
#     host        = module.dbm_autoconfig_ec2.instance_public_ip
#     timeout     = "5m"
#   }

#   # Wait for EC2 instance to be ready and Datadog agent to be installed
#   provisioner "remote-exec" {
#     inline = [
#       "echo 'Waiting for instance to be ready...'",
#       "sleep 60",
#       "echo 'Installing PostgreSQL client...'",
#       "sudo dnf install -y postgresql16",
#     ]
#   }

#   # Setup PostgreSQL for Datadog DBM
#   provisioner "remote-exec" {
#     inline = [
#       "echo 'Setting up PostgreSQL for Datadog DBM...'",
#       "export PGPASSWORD='${var.rds_password}'",
      
#       # Create pg_stat_statements extension in postgres database (default Agent connection)
#       "psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p ${module.dbm_autoconfig_rds.db_port} -U ${var.rds_username} -d postgres -c \"CREATE EXTENSION IF NOT EXISTS pg_stat_statements;\"",
      
#       # Create pg_stat_statements extension in datadog database
#       "psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p ${module.dbm_autoconfig_rds.db_port} -U ${var.rds_username} -d datadog -c \"CREATE EXTENSION IF NOT EXISTS pg_stat_statements;\"",
      
#       # Create datadog user
#       "psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p ${module.dbm_autoconfig_rds.db_port} -U ${var.rds_username} -d datadog -c \"CREATE USER datadog WITH password '${var.dbm_postgres_datadog_password}';\" || echo 'User may already exist'",
      
#       # Create datadog schema
#       "psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p ${module.dbm_autoconfig_rds.db_port} -U ${var.rds_username} -d datadog -c \"CREATE SCHEMA IF NOT EXISTS datadog;\"",
      
#       # Grant permissions
#       "psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p ${module.dbm_autoconfig_rds.db_port} -U ${var.rds_username} -d datadog -c \"GRANT USAGE ON SCHEMA datadog TO datadog;\"",
#       "psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p ${module.dbm_autoconfig_rds.db_port} -U ${var.rds_username} -d datadog -c \"GRANT USAGE ON SCHEMA public TO datadog;\"",
#       "psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p ${module.dbm_autoconfig_rds.db_port} -U ${var.rds_username} -d datadog -c \"GRANT pg_monitor TO datadog;\"",
      
#       # Grant SELECT on pg_stat_statements to datadog user
#       "psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p ${module.dbm_autoconfig_rds.db_port} -U ${var.rds_username} -d datadog -c \"GRANT SELECT ON pg_stat_statements TO datadog;\"",
#       "psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p ${module.dbm_autoconfig_rds.db_port} -U ${var.rds_username} -d postgres -c \"GRANT SELECT ON pg_stat_statements TO datadog;\"",
      
#       # Add public schema (where pg_stat_statements is created) to datadog user search_path
#       "psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p ${module.dbm_autoconfig_rds.db_port} -U ${var.rds_username} -d datadog -c \"ALTER ROLE datadog SET search_path = '\\\"\\$user\\\"',public;\"",
      
#       # Create explain_statement function
#       <<-EOF
#       psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p ${module.dbm_autoconfig_rds.db_port} -U ${var.rds_username} -d datadog <<'EOSQL'
#       CREATE OR REPLACE FUNCTION datadog.explain_statement(
#          l_query TEXT,
#          OUT explain JSON
#       )
#       RETURNS SETOF JSON AS
#       $$
#       DECLARE
#       curs REFCURSOR;
#       plan JSON;
#       BEGIN
#          OPEN curs FOR EXECUTE pg_catalog.concat('EXPLAIN (FORMAT JSON) ', l_query);
#          FETCH curs INTO plan;
#          CLOSE curs;
#          RETURN QUERY SELECT plan;
#       END;
#       $$
#       LANGUAGE 'plpgsql'
#       RETURNS NULL ON NULL INPUT
#       SECURITY DEFINER;
#       EOSQL
#       EOF
#       ,
#       "echo 'PostgreSQL DBM setup complete!'"
#     ]
#   }

#   # Configure Datadog Agent for PostgreSQL DBM
#   provisioner "remote-exec" {
#     inline = [
#       "echo 'Configuring Datadog Agent for PostgreSQL DBM...'",
      
#       "sudo mkdir -p /etc/datadog-agent/conf.d/postgres.d",
      
#       <<-EOF
#       sudo tee /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null <<'EOYAML'
#       init_config:

#       instances:
#         - dbm: true
#           host: ${module.dbm_autoconfig_rds.db_endpoint}
#           port: ${module.dbm_autoconfig_rds.db_port}
#           username: datadog
#           password: '${var.dbm_postgres_datadog_password}'
#           aws:
#             instance_endpoint: ${module.dbm_autoconfig_rds.db_endpoint}
#             region: ${var.region}
#           tags:
#             - "dbinstanceidentifier:${local.project_name_prefix}-dbm-autoconfig-postgres"
#             - "env:${var.project_env}"
#             - "project:${var.project_name}"
#       EOYAML
#       EOF
#       ,
      
#       "sudo chown dd-agent:dd-agent /etc/datadog-agent/conf.d/postgres.d/conf.yaml",
#       "sudo chmod 640 /etc/datadog-agent/conf.d/postgres.d/conf.yaml",
      
#       "sudo systemctl restart datadog-agent",
#     ]
#   }
# }

# # ============================================
# # Outputs
# # ============================================
# output "dbm_autoconfig_ec2_ssh" {
#   description = "SSH command for DBM auto-config EC2"
#   value       = module.dbm_autoconfig_ec2.ssh_command
# }

# output "dbm_autoconfig_ec2_ip" {
#   description = "Public IP of DBM auto-config EC2"
#   value       = module.dbm_autoconfig_ec2.instance_public_ip
# }

# output "dbm_autoconfig_rds_endpoint" {
#   description = "PostgreSQL RDS endpoint"
#   value       = module.dbm_autoconfig_rds.db_endpoint
# }

# output "dbm_autoconfig_rds_port" {
#   description = "PostgreSQL RDS port"
#   value       = module.dbm_autoconfig_rds.db_port
# }

