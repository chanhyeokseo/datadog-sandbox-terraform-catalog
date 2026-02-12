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

module "lambda_python_example" {
  source = "../../modules/lambda"

  function_name = "${local.project_name_prefix}-python-example-app"
  source_dir    = "${path.module}/../../apps/lambda/python/example-app"
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 128

  environment_variables = {
    ENVIRONMENT  = var.project_env
    PROJECT_NAME = var.project_name
    APP_NAME     = "python-example-app"
  }

  enable_function_url    = true
  function_url_auth_type = "NONE"

  tags = merge(local.project_common_tags, {
    Name        = "${local.project_name_prefix}-python-example-app"
    Application = "python-example-app"
  })
}
