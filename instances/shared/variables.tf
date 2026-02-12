variable "project_name" {
  type = string
}
variable "project_env" {
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
variable "ec2_key_name" {
  type = string
}
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
variable "datadog_api_key" {
  type    = string
  default = ""
}

variable "sg_ingress_rules" {
  description = "List of ingress rules for the security group"
  type = list(object({
    description = string
    from_port   = number
    to_port     = number
    protocol    = string
    cidr_blocks = list(string)
    use_my_ip   = optional(bool, false)
  }))
  default = []
}

variable "sg_egress_rules" {
  description = "List of egress rules for the security group"
  type = list(object({
    description = string
    from_port   = number
    to_port     = number
    protocol    = string
    cidr_blocks = list(string)
    use_my_ip   = optional(bool, false)
  }))
  default = []
}
