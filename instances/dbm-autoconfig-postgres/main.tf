terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
    null = {
      source = "hashicorp/null"
    }
  }
}
provider "aws" {
  region = var.region
}

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-kernel-*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
data "aws_vpc" "main" {
  id = var.vpc_id
}
data "aws_subnet" "public" {
  id = var.public_subnet_id
}
data "aws_subnet" "private" {
  id = var.private_subnet_id
}
data "aws_security_group" "dogstac" {
  filter {
    name   = "tag:Name"
    values = ["${var.name_prefix}-personal-sg"]
  }
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }
}

locals {
  name_prefix = var.name_prefix
  common_tags = {
    ManagedBy = "Terraform"
    creator   = var.creator
    team      = var.team
  }
  vpc = {
    vpc_id            = data.aws_vpc.main.id
    public_subnet_id  = data.aws_subnet.public.id
    private_subnet_id = data.aws_subnet.private.id
  }
}

module "dbm_autoconfig_ec2" {
  source = "../../modules/ec2-datadog-host"

  name_prefix        = "${local.name_prefix}-dbm-autoconfig"
  instance_type      = var.ec2_instance_type
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = [data.aws_security_group.dogstac.id]
  key_name            = var.ec2_key_name
  custom_ami_id       = data.aws_ami.amazon_linux_2023.id
  associate_public_ip        = var.ec2_associate_public_ip
  root_volume_size           = var.ec2_root_volume_size
  root_volume_type           = var.ec2_root_volume_type
  enable_detailed_monitoring = var.ec2_enable_detailed_monitoring
  datadog_api_key       = var.datadog_api_key
  datadog_site          = var.datadog_site
  datadog_agent_version = var.datadog_agent_version
  creator               = var.creator
  team                  = var.team
  common_tags           = local.common_tags
}

resource "aws_db_parameter_group" "postgres_dbm" {
  name   = "${local.name_prefix}-dbm-autoconfig-pg16"
  family = "postgres16"

  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements"
    apply_method = "pending-reboot"
  }
  parameter {
닝    name         = "track_activity_query_size"
    value        = "4096"
    apply_method = "pending-reboot"
  }
  parameter {
    name         = "pg_stat_statements.track"
    value        = "ALL"
    apply_method = "pending-reboot"
  }
  parameter {
    name         = "pg_stat_statements.max"
    value        = "10000"
    apply_method = "pending-reboot"
  }
  parameter {
    name         = "track_io_timing"
    value        = "1"
    apply_method = "pending-reboot"
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-dbm-autoconfig-pg16" })
}

module "dbm_autoconfig_rds" {
  source = "../../modules/rds"

  name_prefix             = "${local.name_prefix}-dbm-autoconfig"
  rds_type                = "postgres"
  db_name                 = "datadog"
  db_username             = var.rds_username
  db_password             = var.rds_password
  instance_class          = var.rds_instance_class
  allocated_storage       = 20
  parameter_group_name    = aws_db_parameter_group.postgres_dbm.name
  subnet_ids              = [local.vpc.private_subnet_id, local.vpc.public_subnet_id]
  vpc_id                  = local.vpc.vpc_id
  allowed_security_groups = [data.aws_security_group.dogstac.id]
  backup_retention_period = 0
  common_tags             = local.common_tags
}

resource "null_resource" "dbm_setup" {
  depends_on = [module.dbm_autoconfig_ec2, module.dbm_autoconfig_rds]

  triggers = {
    rds_endpoint = module.dbm_autoconfig_rds.db_endpoint
  }

  connection {
    type        = "ssh"
    host        = module.dbm_autoconfig_ec2.instance_public_ip
    user        = "ec2-user"
    private_key = file("../../keys/${var.ec2_key_name}.pem")
    timeout     = "5m"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo dnf install -y postgresql16 > /dev/null 2>&1",

      "PGPASSWORD='${var.rds_password}' psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p 5432 -U ${var.rds_username} -d datadog -c \"DO \\$\\$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'datadog') THEN CREATE ROLE datadog WITH LOGIN PASSWORD '${var.dbm_postgres_datadog_password}'; END IF; END \\$\\$;\"",
      "PGPASSWORD='${var.rds_password}' psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p 5432 -U ${var.rds_username} -d datadog -c \"ALTER ROLE datadog INHERIT;\"",
      "PGPASSWORD='${var.rds_password}' psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p 5432 -U ${var.rds_username} -d datadog -c \"GRANT pg_monitor TO datadog;\"",
      "PGPASSWORD='${var.rds_password}' psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p 5432 -U ${var.rds_username} -d datadog -c \"CREATE SCHEMA IF NOT EXISTS datadog; GRANT USAGE ON SCHEMA datadog TO datadog; GRANT USAGE ON SCHEMA public TO datadog;\"",
      "PGPASSWORD='${var.rds_password}' psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p 5432 -U ${var.rds_username} -d datadog -c \"CREATE EXTENSION IF NOT EXISTS pg_stat_statements SCHEMA public;\"",

      "PGPASSWORD='${var.rds_password}' psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p 5432 -U ${var.rds_username} -d datadog -c \"CREATE OR REPLACE FUNCTION datadog.pg_stat_activity() RETURNS SETOF pg_stat_activity AS 'SELECT * FROM pg_catalog.pg_stat_activity;' LANGUAGE sql SECURITY DEFINER;\"",
      "PGPASSWORD='${var.rds_password}' psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p 5432 -U ${var.rds_username} -d datadog -c \"CREATE OR REPLACE FUNCTION datadog.pg_stat_statements() RETURNS SETOF pg_stat_statements AS 'SELECT * FROM pg_stat_statements;' LANGUAGE sql SECURITY DEFINER;\"",

      "PGPASSWORD='${var.rds_password}' psql -h ${module.dbm_autoconfig_rds.db_endpoint} -p 5432 -U ${var.rds_username} -d datadog <<'EOSQL'",
      "CREATE OR REPLACE FUNCTION datadog.explain_statement(",
      "   l_query TEXT, OUT explain JSON",
      ") RETURNS SETOF JSON AS $$",
      "DECLARE",
      "  curs REFCURSOR;",
      "  plan JSON;",
      "BEGIN",
      "   SET TRANSACTION READ ONLY;",
      "   OPEN curs FOR EXECUTE pg_catalog.concat('EXPLAIN (FORMAT JSON) ', l_query);",
      "   FETCH curs INTO plan;",
      "   CLOSE curs;",
      "   RETURN QUERY SELECT plan;",
      "END;",
      "$$ LANGUAGE 'plpgsql' RETURNS NULL ON NULL INPUT SECURITY DEFINER;",
      "EOSQL",

      "sudo mkdir -p /etc/datadog-agent/conf.d/postgres.d",
      "echo 'init_config:' | sudo tee /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null",
      "echo 'instances:' | sudo tee -a /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null",
      "echo '  - dbm: true' | sudo tee -a /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null",
      "echo '    host: ${module.dbm_autoconfig_rds.db_endpoint}' | sudo tee -a /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null",
      "echo '    port: 5432' | sudo tee -a /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null",
      "echo '    username: datadog' | sudo tee -a /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null",
      "echo '    password: \"${var.dbm_postgres_datadog_password}\"' | sudo tee -a /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null",
      "echo '    dbname: datadog' | sudo tee -a /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null",
      "echo '    aws:' | sudo tee -a /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null",
      "echo '      instance_endpoint: ${module.dbm_autoconfig_rds.db_endpoint}' | sudo tee -a /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null",
      "echo '      region: ${var.region}' | sudo tee -a /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null",
      "echo '    tags:' | sudo tee -a /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null",
      "echo '      - dbinstanceidentifier:${local.name_prefix}-dbm-autoconfig-postgres' | sudo tee -a /etc/datadog-agent/conf.d/postgres.d/conf.yaml > /dev/null",

      "sudo systemctl restart datadog-agent",
    ]
  }
}
