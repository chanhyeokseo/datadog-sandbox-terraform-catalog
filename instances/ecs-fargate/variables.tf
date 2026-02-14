variable "creator" {
  type = string
}
variable "team" {
  type = string
}
variable "region" {
  type = string
}
variable "ecs_enable_fargate" {
  type    = bool
  default = true
}
variable "ec2_key_name" {
  type    = string
  default = ""
}
variable "vpc_id" {
  type    = string
  default = ""
}
variable "public_subnet_id" {
  type    = string
  default = ""
}
variable "public_subnet2_id" {
  type    = string
  default = ""
}
variable "private_subnet_id" {
  type    = string
  default = ""
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
