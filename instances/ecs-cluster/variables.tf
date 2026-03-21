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

variable "region" {
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

variable "ec2_key_name" {
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

variable "enable_fargate" {
  type    = bool
  default = true
}

variable "enable_ec2" {
  type    = bool
  default = false
}

variable "ec2_instance_type" {
  type    = string
  default = "t3.medium"
}

variable "ec2_min_size" {
  type    = number
  default = 1
}

variable "ec2_max_size" {
  type    = number
  default = 3
}

variable "ec2_desired_capacity" {
  type    = number
  default = 1
}

variable "security_group_ids" {
  type    = list(string)
  default = []
}
