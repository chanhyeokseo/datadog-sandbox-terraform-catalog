# ============================================
# Lambda Function Module - Variables
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


variable "vpc_config" {
  description = "VPC configuration (subnet_ids, security_group_ids)"
  type = object({
    subnet_ids         = list(string)
    security_group_ids = list(string)
  })
  default = null
}

variable "dead_letter_target_arn" {
  description = "Dead Letter Queue ARN (SQS or SNS)"
  type        = string
  default     = null
}

variable "additional_policy_arns" {
  description = "List of additional policy ARNs to attach to Lambda role"
  type        = list(string)
  default     = []
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


variable "create_alias" {
  description = "Create Lambda function alias"
  type        = bool
  default     = false
}

variable "alias_name" {
  description = "Lambda function alias name"
  type        = string
  default     = "live"
}

variable "alias_function_version" {
  description = "Function version to point alias to ($LATEST or version number)"
  type        = string
  default     = "$LATEST"
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}

