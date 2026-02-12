
output "function_name" {
  description = "Lambda function name"
  value       = module.lambda_datadog.function_name
}

output "function_arn" {
  description = "Lambda function ARN"
  value       = module.lambda_datadog.arn
}

output "role_arn" {
  description = "Lambda execution role ARN"
  value       = aws_iam_role.lambda_role.arn
}

output "role_name" {
  description = "Lambda execution role name"
  value       = aws_iam_role.lambda_role.name
}

output "log_group_name" {
  description = "CloudWatch Logs group name (automatically created by Lambda)"
  value       = "/aws/lambda/${var.function_name}"
}

output "function_url" {
  description = "Lambda function URL (if enabled)"
  value       = var.enable_function_url ? aws_lambda_function_url.function_url[0].function_url : null
}
