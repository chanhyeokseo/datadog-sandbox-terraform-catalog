
data "aws_region" "current" {}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "${path.module}/.terraform/lambda_${var.function_name}.zip"
  excludes    = var.exclude_files
}

locals {
  region = var.aws_region != "" ? var.aws_region : data.aws_region.current.id

  datadog_env_vars = {
    DD_API_KEY                 = var.datadog_api_key != "" ? var.datadog_api_key : null
    DD_API_KEY_SECRET_ARN      = var.datadog_api_key_secret_arn != "" ? var.datadog_api_key_secret_arn : null
    DD_ENV                     = var.datadog_env
    DD_SERVICE                 = var.datadog_service
    DD_SITE                    = var.datadog_site
    DD_VERSION                 = var.datadog_version
    DD_TRACE_ENABLED           = var.datadog_enable_tracing ? "true" : "false"
    DD_LOGS_INJECTION          = "true"
    DD_SERVERLESS_LOGS_ENABLED = "true"
    DD_CAPTURE_LAMBDA_PAYLOAD  = "true"
  }

  all_environment_variables = merge(var.environment_variables, local.datadog_env_vars)
}


resource "aws_iam_role" "lambda_role" {
  name = "${var.function_name}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name = "${var.function_name}-lambda-role"
    }
  )
}

resource "aws_iam_role_policy" "lambda_logs" {
  name = "${var.function_name}-lambda-logs"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy" "datadog_secret_access" {
  count = var.datadog_api_key_secret_arn != "" ? 1 : 0
  name  = "${var.function_name}-datadog-secret-access"
  role  = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = var.datadog_api_key_secret_arn
      }
    ]
  })
}



module "lambda_datadog" {
  source  = "DataDog/lambda-datadog/aws"
  version = "4.5.0"

  filename         = data.archive_file.lambda_zip.output_path
  function_name    = var.function_name
  role             = aws_iam_role.lambda_role.arn
  handler          = var.handler
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = var.runtime
  timeout          = var.timeout
  memory_size      = var.memory_size

  environment_variables = {
    for k, v in local.all_environment_variables :
    k => v if v != null
  }

  datadog_extension_layer_version = var.datadog_extension_layer_version
  datadog_python_layer_version    = var.datadog_python_layer_version

  tags = var.tags
}


resource "aws_lambda_function_url" "function_url" {
  count              = var.enable_function_url ? 1 : 0
  function_name      = module.lambda_datadog.function_name
  authorization_type = var.function_url_auth_type

  cors {
    allow_credentials = false
    allow_origins     = ["*"]
    allow_methods     = ["*"]
    allow_headers     = ["*"]
    expose_headers    = ["*"]
    max_age           = 86400
  }
}
