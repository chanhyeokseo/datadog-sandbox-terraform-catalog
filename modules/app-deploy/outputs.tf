# ============================================
# App Deploy Module - Outputs
# ============================================

output "image_uri" {
  description = "Full URI of the pushed Docker image"
  value       = local.full_image_uri
}

output "source_hash" {
  description = "Hash of source files (triggers rebuild on change)"
  value       = data.external.source_hash.result["hash"]
}

output "app_name" {
  description = "Name of the deployed application"
  value       = var.app_name
}


