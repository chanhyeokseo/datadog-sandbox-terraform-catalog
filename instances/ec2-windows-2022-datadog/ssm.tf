data "aws_ssm_parameter" "datadog_api_key" {
  name = "/dogstac-${var.name_prefix}/sensitive/datadog_api_key"
}
