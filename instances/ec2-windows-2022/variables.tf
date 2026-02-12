variable "vpc_id" {
  type = string
}
variable "public_subnet_id" {
  type = string
}
variable "project_name" {
  type = string
}
variable "project_env" {
  type = string
}
variable "region" {
  type = string
}
variable "ec2_key_name" {
  type = string
}
variable "ec2_instance_type" {
  type    = string
  default = "t3.medium"
}
variable "creator" {
  type = string
}
variable "team" {
  type = string
}
variable "public_subnet2_id" {
  type    = string
  default = ""
}
variable "private_subnet_id" {
  type    = string
  default = ""
}
variable "security_group_ids" {
  type    = list(string)
  default = []
}
variable "datadog_api_key" {
  type    = string
  default = ""
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
