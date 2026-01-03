# ============================================
# RDS Instance Module
# ============================================

locals {
  engine_config = {
    postgres = {
      engine               = "postgres"
      engine_version       = var.engine_version != "" ? var.engine_version : "16.11"
      port                 = 5432
      parameter_family     = "postgres16"
      license_model        = null
      supports_db_name     = true
    }
    mysql = {
      engine               = "mysql"
      engine_version       = var.engine_version != "" ? var.engine_version : "8.0"
      port                 = 3306
      parameter_family     = "mysql8.0"
      license_model        = null
      supports_db_name     = true
    }
    oracle = {
      engine               = "oracle-se2"
      engine_version       = var.engine_version != "" ? var.engine_version : "19"
      port                 = 1521
      parameter_family     = "oracle-se2-19"
      license_model        = "license-included"
      supports_db_name     = false
    }
    sqlserver = {
      engine               = "sqlserver-ex"
      engine_version       = var.engine_version != "" ? var.engine_version : "16.00"
      port                 = 1433
      parameter_family     = "sqlserver-ex-16.0"
      license_model        = "license-included"
      supports_db_name     = false
    }
    docdb = {
      engine               = "docdb"
      engine_version       = var.engine_version != "" ? var.engine_version : "5.0"
      port                 = 27017
      parameter_family     = "docdb5.0"
      license_model        = null
      supports_db_name     = false
    }
  }

  selected_engine = local.engine_config[var.rds_type]
  is_docdb        = var.rds_type == "docdb"
  is_postgres     = var.rds_type == "postgres"
}

# ============================================
# DB Subnet Group
# ============================================
resource "aws_db_subnet_group" "main" {
  count = local.is_docdb ? 0 : 1

  name        = "${var.name_prefix}-rds-subnet-group"
  description = "Subnet group for ${var.name_prefix} RDS instance"
  subnet_ids  = var.subnet_ids

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-rds-subnet-group"
      service = var.service
    }
  )
}

# ============================================
# DocumentDB Subnet Group
# ============================================
resource "aws_docdb_subnet_group" "main" {
  count = local.is_docdb ? 1 : 0

  name        = "${var.name_prefix}-docdb-subnet-group"
  description = "Subnet group for ${var.name_prefix} DocumentDB cluster"
  subnet_ids  = var.subnet_ids

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-docdb-subnet-group"
      service = var.service
    }
  )
}

# ============================================
# Security Group for Database
# ============================================
resource "aws_security_group" "db" {
  name        = "${var.name_prefix}-${var.rds_type}-sg"
  description = "Security group for ${var.name_prefix} ${var.rds_type} database"
  vpc_id      = var.vpc_id

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-${var.rds_type}-sg"
      service = var.service
    }
  )
}

resource "aws_security_group_rule" "db_ingress_sg" {
  count = length(var.allowed_security_groups)

  type                     = "ingress"
  from_port                = local.selected_engine.port
  to_port                  = local.selected_engine.port
  protocol                 = "tcp"
  source_security_group_id = var.allowed_security_groups[count.index]
  security_group_id        = aws_security_group.db.id
  description              = "Allow ${var.rds_type} access from security group"
}

resource "aws_security_group_rule" "db_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.db.id
  description       = "Allow all outbound traffic"
}

# ============================================
# RDS Instance (for PostgreSQL, MySQL, Oracle, SQL Server)
# ============================================
resource "aws_db_instance" "main" {
  count = local.is_docdb ? 0 : 1

  identifier = "${var.name_prefix}-${var.rds_type}"

  engine         = local.selected_engine.engine
  engine_version = local.selected_engine.engine_version
  port           = local.selected_engine.port
  license_model  = local.selected_engine.license_model

  instance_class        = var.instance_class
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage > 0 ? var.max_allocated_storage : null
  storage_type          = "gp3"
  storage_encrypted     = var.storage_encrypted

  db_name  = local.selected_engine.supports_db_name ? var.db_name : null
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main[0].name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = var.publicly_accessible

  multi_az                = var.multi_az
  backup_retention_period = var.backup_retention_period

  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.name_prefix}-${var.rds_type}-final-snapshot"
  deletion_protection       = var.deletion_protection

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-${var.rds_type}"
      service = var.service
    }
  )
}

# ============================================
# DocumentDB Cluster (for Amazon DocumentDB)
# ============================================
resource "aws_docdb_cluster" "main" {
  count = local.is_docdb ? 1 : 0

  cluster_identifier = "${var.name_prefix}-docdb"

  engine         = "docdb"
  engine_version = local.selected_engine.engine_version
  port           = local.selected_engine.port

  master_username = var.db_username
  master_password = var.db_password

  db_subnet_group_name   = aws_docdb_subnet_group.main[0].name
  vpc_security_group_ids = [aws_security_group.db.id]

  storage_encrypted       = var.storage_encrypted
  backup_retention_period = var.backup_retention_period

  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.name_prefix}-docdb-final-snapshot"
  deletion_protection       = var.deletion_protection

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-docdb"
      service = var.service
    }
  )
}

resource "aws_docdb_cluster_instance" "main" {
  count = local.is_docdb ? 1 : 0

  identifier         = "${var.name_prefix}-docdb-instance"
  cluster_identifier = aws_docdb_cluster.main[0].id
  instance_class     = var.instance_class

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-docdb-instance"
      service = var.service
    }
  )
}

