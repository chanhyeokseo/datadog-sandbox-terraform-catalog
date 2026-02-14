# ============================================
# Lambda Functions Configuration
# ============================================

locals {
  # Common Lambda configuration
  lambda_defaults = {
    runtime     = "python3.11"
    handler     = "handler.lambda_handler"
    timeout     = 30
    memory_size = 128
  }

  # Common environment variables
  lambda_common_env = {
    CREATOR = var.creator
    TEAM    = var.team
  }

  # Common Function URL settings
  lambda_function_url_config = {
    enable    = true
    auth_type = "NONE"
  }
}

# ============================================
# Python Example App Function
# ============================================
module "lambda_python_example" {
  source = "./modules/lambda"

  function_name = "${local.name_prefix}-python-example-app"
  source_dir    = "${path.module}/apps/lambda/python/example-app"
  handler       = local.lambda_defaults.handler
  runtime       = local.lambda_defaults.runtime
  timeout       = local.lambda_defaults.timeout
  memory_size   = local.lambda_defaults.memory_size

  environment_variables = merge(
    local.lambda_common_env,
    {
      APP_NAME = "python-example-app"
    }
  )

  enable_function_url    = local.lambda_function_url_config.enable
  function_url_auth_type = local.lambda_function_url_config.auth_type

  tags = merge(
    local.common_tags,
    {
      Name        = "${local.name_prefix}-python-example-app"
      Application = "python-example-app"
      Function    = "simple-example"
    }
  )
}

# Python Example App Function Outputs
output "lambda_python_example_function_name" {
  description = "Python Example App Function name"
  value       = module.lambda_python_example.function_name
}

output "lambda_python_example_function_url" {
  description = "Python Example App Function URL"
  value       = module.lambda_python_example.function_url
}

# ============================================
# Python Example Tracing App Function
# ============================================
module "lambda_python_tracing_example" {
  source = "./modules/lambda-datadog-extension"

  function_name = "${local.name_prefix}-python-tracing-example-app"
  source_dir    = "${path.module}/apps/lambda/python/tracing-example-app"
  handler       = local.lambda_defaults.handler
  runtime       = local.lambda_defaults.runtime
  timeout       = local.lambda_defaults.timeout
  memory_size   = local.lambda_defaults.memory_size

  environment_variables = merge(
    local.lambda_common_env,
    {
      APP_NAME = "python-tracing-example-app"
    }
  )

  # Datadog Configuration
  datadog_extension_layer_version = 91
  datadog_python_layer_version    = 120
  datadog_api_key                 = var.datadog_api_key
  datadog_env                     = var.team
  datadog_service                 = "python-tracing-example-app"
  datadog_site                    = var.datadog_site
  datadog_version                 = "1.0.0"
  datadog_enable_tracing          = true
  aws_region                      = var.region

  enable_function_url    = local.lambda_function_url_config.enable
  function_url_auth_type = local.lambda_function_url_config.auth_type

  tags = merge(
    local.common_tags,
    {
      Name        = "${local.name_prefix}-python-tracing-example-app"
      Application = "python-tracing-example-app"
      Function    = "tracing-example"
      Tracing     = "enabled"
    }
  )
}

# Python Example Tracing App Function Outputs
output "lambda_python_tracing_example_function_name" {
  description = "Python Example Tracing App Function name"
  value       = module.lambda_python_tracing_example.function_name
}

output "lambda_python_tracing_example_function_url" {
  description = "Python Example Tracing App Function URL"
  value       = module.lambda_python_tracing_example.function_url
}

output "lambda_python_tracing_example_available_endpoints" {
  description = "Available endpoints for the tracing example app"
  value = [
    "/",
    "/add-tag",
    "/set-error",
    "/trace-decorator",
    "/manual-span",
    "/nested-spans",
    "/custom-metrics",
    "/health",
    "/slow"
  ]
}

