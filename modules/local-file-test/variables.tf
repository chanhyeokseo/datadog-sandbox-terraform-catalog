variable "filename" {
  description = "Name of the file to create"
  type        = string
}

variable "content" {
  description = "Content to write into the file"
  type        = string
  default     = ""
}
