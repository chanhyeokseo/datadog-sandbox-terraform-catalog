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
  project_name_prefix = "${var.project_name}-${var.project_env}"
  project_common_tags = {
    Project     = var.project_name
    Environment = var.project_env
    ManagedBy   = "Terraform"
    creator     = var.creator
    team        = var.team
  }
}

module "lambda_python_tracing_example" {
  source = "git::https://github.com/chanhyeokseo/datadog-sandbox-terraform-catalog.git//modules/lambda-datadog-extension?ref=webui-dev"

  function_name = "${local.project_name_prefix}-python-tracing-example-app"
  source_dir    = "${path.module}/../../apps/lambda/python/tracing-example-app"
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 128

  environment_variables = {
    ENVIRONMENT  = var.project_env
    PROJECT_NAME = var.project_name
    APP_NAME     = "python-tracing-example-app"
  }

  datadog_extension_layer_version = 91
  datadog_python_layer_version    = 120
  datadog_api_key                 = var.datadog_api_key
  datadog_env                     = var.project_env
  datadog_service                 = "python-tracing-example-app"
  datadog_site                    = var.datadog_site
  datadog_version                 = "1.0.0"
  datadog_enable_tracing          = true
  aws_region                      = var.region

  enable_function_url    = true
  function_url_auth_type = "NONE"

  tags = merge(local.project_common_tags, {
    Name        = "${local.project_name_prefix}-python-tracing-example-app"
    Application = "python-tracing-example-app"
  })
}
