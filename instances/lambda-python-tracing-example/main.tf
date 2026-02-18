terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}
provider "aws" {
  region = var.region
}

locals {
  name_prefix = var.name_prefix
  common_tags = {
    ManagedBy = "Terraform"
    creator   = var.creator
    team      = var.team
  }
}

module "lambda_python_tracing_example" {
  source = "../../modules/lambda-datadog-extension"

  function_name = "${local.name_prefix}-python-tracing-example-app"
  source_dir    = "${path.module}/../../apps/lambda/python/tracing-example-app"
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 128

  environment_variables = {
    CREATOR  = var.creator
    TEAM     = var.team
    APP_NAME = "python-tracing-example-app"
  }

  datadog_extension_layer_version = 91
  datadog_python_layer_version    = 120
  datadog_api_key                 = var.datadog_api_key
  datadog_env                     = var.team
  datadog_service                 = "python-tracing-example-app"
  datadog_site                    = var.datadog_site
  datadog_version                 = "1.0.0"
  datadog_enable_tracing          = true
  aws_region                      = var.region

  enable_function_url    = true
  function_url_auth_type = "NONE"

  tags = merge(local.common_tags, {
    Name        = "${local.name_prefix}-python-tracing-example-app"
    Application = "python-tracing-example-app"
  })
}
