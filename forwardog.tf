# ============================================
# Forwardog Instance Configuration
# ============================================

module "ec2_forwardog" {
  source = "./modules/ec2-forwardog"

  name_prefix        = local.project_name_prefix
  instance_type      = "t3.medium"
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = [module.security_group.security_group_id]
  key_name           = var.ec2_key_name
  custom_ami_id      = data.aws_ami.amazon_linux_2023.id

  datadog_api_key = var.datadog_api_key
  datadog_site    = var.datadog_site
  project_name    = var.project_name
  environment     = var.project_env

  common_tags = local.project_common_tags
}

# Forwardog Outputs
output "forwardog_instance_id" {
  description = "ID of the Forwardog EC2 instance"
  value       = module.ec2_forwardog.instance_id
}

output "forwardog_public_ip" {
  description = "Public IP of the Forwardog EC2 instance"
  value       = module.ec2_forwardog.instance_public_ip
}

output "forwardog_ssh_command" {
  description = "SSH command to connect to the Forwardog instance"
  value       = module.ec2_forwardog.ssh_command
}

output "forwardog_url" {
  description = "URL to access Forwardog service"
  value       = module.ec2_forwardog.forwardog_url
}

output "forwardog_logs_command" {
  description = "Command to view Forwardog container logs"
  value       = module.ec2_forwardog.docker_compose_logs_command
}