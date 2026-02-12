
variable "name_prefix" {
  description = "Name prefix for RDS resources"
  type        = string
}

variable "rds_type" {
  description = "Type of RDS database engine (postgres, mysql, oracle, sqlserver, docdb)"
  type        = string
  validation {
    condition     = contains(["postgres", "mysql", "oracle", "sqlserver", "docdb"], var.rds_type)
    error_message = "rds_type must be one of: postgres, mysql, oracle, sqlserver, docdb"
  }
}

variable "db_name" {
  description = "Name of the database to create (not applicable for Oracle, SQL Server, DocumentDB)"
  type        = string
  default     = "appdb"
}

variable "db_username" {
  description = "Master username for the database"
  type        = string
  default     = "admin"
}

variable "db_password" {
  description = "Master password for the database"
  type        = string
  sensitive   = true
}

variable "instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Maximum allocated storage for autoscaling in GB (set to 0 to disable)"
  type        = number
  default     = 100
}

variable "engine_version" {
  description = "Database engine version (leave empty for latest)"
  type        = string
  default     = ""
}

variable "subnet_ids" {
  description = "List of subnet IDs for DB subnet group"
  type        = list(string)
}

variable "vpc_id" {
  description = "VPC ID for the security group"
  type        = string
}

variable "allowed_security_groups" {
  description = "Security group IDs allowed to access the database"
  type        = list(string)
  default     = []
}

variable "publicly_accessible" {
  description = "Whether the database should be publicly accessible"
  type        = bool
  default     = false
}

variable "multi_az" {
  description = "Enable Multi-AZ deployment for high availability"
  type        = bool
  default     = false
}

variable "storage_encrypted" {
  description = "Enable storage encryption"
  type        = bool
  default     = true
}

variable "backup_retention_period" {
  description = "Number of days to retain automated backups (0-35)"
  type        = number
  default     = 7
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot when deleting the database"
  type        = bool
  default     = true
}

variable "deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = false
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "service" {
  description = "Service name for tagging (e.g., rds, docdb)"
  type        = string
  default     = "rds"
}

