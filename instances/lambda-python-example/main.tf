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

module "lambda_python_example" {
  source = "git::https://github.com/chanhyeokseo/datadog-sandbox-terraform-catalog.git//modules/lambda?ref=webui-dev"

  function_name = "${local.name_prefix}-python-example-app"
  source_dir    = "${path.module}/../../apps/lambda/python/example-app"
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 128

  environment_variables = {
    CREATOR  = var.creator
    TEAM     = var.team
    APP_NAME = "python-example-app"
  }

  enable_function_url    = true
  function_url_auth_type = "NONE"

  tags = merge(local.common_tags, {
    Name        = "${local.name_prefix}-python-example-app"
    Application = "python-example-app"
  })
}
