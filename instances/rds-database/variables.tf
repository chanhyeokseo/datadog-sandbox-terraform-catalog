variable "vpc_id" {
  type = string
}
variable "public_subnet_id" {
  type = string
}
variable "public_subnet2_id" {
  type    = string
  default = ""
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
variable "rds_type" {
  type    = string
  default = "postgres"
}
variable "rds_username" {
  type    = string
  default = "dbadmin"
}
variable "rds_instance_class" {
  type    = string
  default = "db.t3.micro"
}
variable "rds_allocated_storage" {
  type    = number
  default = 20
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
