
variable "repository_name" {
  description = "Name of the ECR repository"
  type        = string
}

variable "image_tag_mutability" {
  description = "Tag mutability setting for the repository (MUTABLE or IMMUTABLE)"
  type        = string
  default     = "MUTABLE"
}

variable "scan_on_push" {
  description = "Enable image scanning on push"
  type        = bool
  default     = true
}

variable "force_delete" {
  description = "Delete repository even if it contains images"
  type        = bool
  default     = true
}

variable "lifecycle_policy_count" {
  description = "Number of images to keep (0 to disable lifecycle policy)"
  type        = number
  default     = 10
}

variable "tags" {
  description = "Tags to apply to the repository"
  type        = map(string)
  default     = {}
}


