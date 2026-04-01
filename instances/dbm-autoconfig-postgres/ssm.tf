data "aws_ssm_parameter" "datadog_api_key" {
  name = "/dogstac-${var.name_prefix}/sensitive/datadog_api_key"
}

data "aws_ssm_parameter" "rds_password" {
  name = "/dogstac-${var.name_prefix}/sensitive/rds_password"
}

data "aws_ssm_parameter" "dbm_postgres_datadog_password" {
  name = "/dogstac-${var.name_prefix}/sensitive/dbm_postgres_datadog_password"
}
