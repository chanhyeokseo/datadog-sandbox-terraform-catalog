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

variable "enable_node_group" {
  type    = bool
  default = true
}
variable "node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}
variable "node_desired_size" {
  type    = number
  default = 2
}
variable "node_min_size" {
  type    = number
  default = 1
}
variable "node_max_size" {
  type    = number
  default = 4
}
variable "node_disk_size" {
  type    = number
  default = 20
}
variable "node_capacity_type" {
  type    = string
  default = "ON_DEMAND"
}

variable "enable_windows_node_group" {
  type    = bool
  default = false
}
variable "windows_node_instance_types" {
  type    = list(string)
  default = ["t3.medium"]
}
variable "windows_node_ami_type" {
  type    = string
  default = "WINDOWS_FULL_2022_x86_64"
}
variable "windows_node_desired_size" {
  type    = number
  default = 2
}
variable "windows_node_min_size" {
  type    = number
  default = 1
}
variable "windows_node_max_size" {
  type    = number
  default = 4
}
variable "windows_node_disk_size" {
  type    = number
  default = 50
}
variable "windows_node_capacity_type" {
  type    = string
  default = "ON_DEMAND"
}

variable "enable_fargate" {
  type    = bool
  default = false
}
variable "fargate_namespaces" {
  type    = list(string)
  default = ["default", "kube-system"]
}

variable "endpoint_public_access" {
  type    = bool
  default = true
}
variable "endpoint_private_access" {
  type    = bool
  default = true
}
