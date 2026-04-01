variable "vpc_id" {
  type = string
}
variable "public_subnet_id" {
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
variable "private_subnet_id" {
  type    = string
  default = ""
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
