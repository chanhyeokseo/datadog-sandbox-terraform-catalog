variable "vpc_id" {
  type = string
}
variable "public_subnet_id" {
  type = string
}
variable "private_subnet_id" {
  type = string
}
variable "region" {
  type = string
}
variable "ec2_key_name" {
  type = string
}
variable "creator" {
  type = string
}
variable "team" {
  type = string
}
variable "name_prefix" {
  type = string
}
variable "public_subnet2_id" {
  type    = string
  default = ""
}
variable "ec2_instance_type" {
  type    = string
  default = "t3.micro"
}
variable "ec2_associate_public_ip" {
  type    = bool
  default = true
}
variable "ec2_root_volume_size" {
  type    = number
  default = 30
}
variable "ec2_root_volume_type" {
  type    = string
  default = "gp3"
}
variable "ec2_enable_detailed_monitoring" {
  type    = bool
  default = false
}
variable "datadog_api_key" {
  type    = string
  default = ""
}
variable "datadog_site" {
  type    = string
  default = "datadoghq.com"
}
variable "datadog_agent_version" {
  type    = string
  default = "latest"
}
variable "rds_username" {
  type    = string
  default = "datadog"
}
variable "rds_password" {
  type      = string
  sensitive = true

  validation {
    condition     = length(var.rds_password) >= 8
    error_message = "rds_password must be at least 8 characters."
  }
}
variable "rds_instance_class" {
  type    = string
  default = "db.t3.micro"
}
variable "dbm_postgres_datadog_password" {
  type      = string
  default   = ""
  sensitive = true
}
variable "aws_access_key_id" {
  type    = string
  default = ""
}
variable "aws_secret_access_key" {
  type    = string
  default = ""
}
variable "aws_session_token" {
  type    = string
  default = ""
}
