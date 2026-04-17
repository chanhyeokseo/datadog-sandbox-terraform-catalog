output "instance_id" {
  value = module.ec2_windows_2025_datadog.instance_id
}
output "public_ip" {
  value = module.ec2_windows_2025_datadog.instance_public_ip
}
output "rdp_info" {
  value = "RDP to ${module.ec2_windows_2025_datadog.instance_public_ip} | User: Administrator"
}
output "windows_password" {
  value     = try(rsadecrypt(module.ec2_windows_2025_datadog.password_data, file("../../keys/${var.ec2_key_name}.pem")), "")
  sensitive = true
}
