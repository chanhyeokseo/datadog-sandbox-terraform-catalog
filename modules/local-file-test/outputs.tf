output "file_path" {
  description = "Absolute path of the created file"
  value       = local_file.this.filename
}

output "file_id" {
  description = "ID of the local file resource"
  value       = local_file.this.id
}
