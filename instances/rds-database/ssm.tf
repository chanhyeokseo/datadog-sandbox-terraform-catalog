data "aws_ssm_parameter" "rds_password" {
  name = "/dogstac-${var.name_prefix}/sensitive/rds_password"
}
