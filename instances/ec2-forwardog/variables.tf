variable "vpc_id" {
  type = string
}
variable "public_subnet_id" {
  type = string
}
variable "public_subnet2_id" {
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
variable "ec2_instance_type" {
  type    = string
  default = "t3.micro"
}
variable "ec2_associate_public_ip" {
  type    = bool
  default = true
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
variable "datadog_api_key" {
  type = string
}
variable "datadog_site" {
  type    = string
  default = "datadoghq.com"
}
variable "datadog_agent_image" {
  type    = string
  default = "gcr.io/datadoghq/agent:latest"
}
variable "security_group_ids" {
  type    = list(string)
  default = []
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
