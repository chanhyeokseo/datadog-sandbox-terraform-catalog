# ============================================
# Lambda Function Module with Datadog Lambda Extension - Variables
# ============================================

variable "function_name" {
  description = "Lambda function name"
  type        = string
}

variable "source_dir" {
  description = "Directory path containing Lambda function source code"
  type        = string
}

variable "handler" {
  description = "Lambda function handler (e.g., handler.lambda_handler)"
  type        = string
  default     = "handler.lambda_handler"
}

variable "runtime" {
  description = "Lambda runtime (e.g., python3.11, python3.12)"
  type        = string
  default     = "python3.11"
}

variable "timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 128
}

variable "environment_variables" {
  description = "Lambda function environment variables"
  type        = map(string)
  default     = {}
}

variable "exclude_files" {
  description = "File patterns to exclude from ZIP archive"
  type        = list(string)
  default     = [
    "*.md",
    ".git",
    ".gitignore",
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    "venv",
    ".venv"
  ]
}


variable "enable_function_url" {
  description = "Enable Lambda function URL"
  type        = bool
  default     = false
}

variable "function_url_auth_type" {
  description = "Lambda function URL authentication type (NONE or AWS_IAM)"
  type        = string
  default     = "NONE"
}

variable "datadog_extension_layer_version" {
  description = "Datadog Extension layer version"
  type        = number
  default     = 91
}

variable "datadog_python_layer_version" {
  description = "Datadog Python layer version"
  type        = number
  default     = 120
}

variable "datadog_api_key_secret_arn" {
  description = "ARN of AWS Secrets Manager secret containing Datadog API key"
  type        = string
  default     = ""
}

variable "datadog_api_key" {
  description = "Datadog API key in plaintext (not recommended for production)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "datadog_env" {
  description = "Datadog environment tag"
  type        = string
}

variable "datadog_service" {
  description = "Datadog service name"
  type        = string
}

variable "datadog_site" {
  description = "Datadog site (e.g., datadoghq.com)"
  type        = string
  default     = "datadoghq.com"
}

variable "datadog_version" {
  description = "Datadog version tag"
  type        = string
  default     = "1.0.0"
}

variable "datadog_enable_tracing" {
  description = "Enable Datadog APM tracing"
  type        = bool
  default     = true
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
