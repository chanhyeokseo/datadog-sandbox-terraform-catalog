# ============================================
# App Deploy Module - Variables
# ============================================

variable "app_name" {
  description = "Name of the application"
  type        = string
}

variable "app_path" {
  description = "Path to the application source directory (containing Dockerfile)"
  type        = string
}

variable "ecr_repository_url" {
  description = "ECR repository URL to push the image"
  type        = string
}

variable "image_tag" {
  description = "Tag for the Docker image"
  type        = string
  default     = "latest"
}

variable "aws_region" {
  description = "AWS region for ECR"
  type        = string
}

variable "build_args" {
  description = "Build arguments for Docker build (key=value format)"
  type        = map(string)
  default     = {}
}

variable "dockerfile_path" {
  description = "Path to Dockerfile relative to app_path"
  type        = string
  default     = "Dockerfile"
}

variable "force_rebuild" {
  description = "Force rebuild by changing this value"
  type        = string
  default     = ""
}


