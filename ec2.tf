# ============================================
# EC2 Instances Configuration
# ============================================

# ============================================
# EC2 Basic Instance Module
# ============================================
module "ec2_basic" {
  source = "./modules/ec2-basic"

  name_prefix        = local.project_name_prefix
  instance_type      = var.ec2_instance_type
  subnet_id          = module.vpc.public_subnet_id
  security_group_ids = [module.security_group.security_group_id]
  key_name           = var.ec2_key_name

  common_tags = local.project_common_tags
}

# EC2 Basic Module Outputs
output "ec2_basic_instance_id" {
  description = "ID of the basic EC2 instance"
  value       = module.ec2_basic.instance_id
}

output "ec2_basic_public_ip" {
  description = "Public IP of the basic EC2 instance"
  value       = module.ec2_basic.instance_public_ip
}

output "ec2_basic_ssh_command" {
  description = "SSH command to connect to the basic EC2 instance"
  value       = module.ec2_basic.ssh_command
}

# ============================================
# EC2 Datadog Host Module
# ============================================
module "ec2_datadog_host" {
  source = "./modules/ec2-datadog-host"

  name_prefix       = local.project_name_prefix
  instance_type     = var.ec2_instance_type
  subnet_id         = module.vpc.public_subnet_id
  security_group_ids = [module.security_group.security_group_id]
  key_name          = var.ec2_key_name

  datadog_api_key = var.datadog_api_key
  datadog_site    = var.datadog_site
  project_name    = var.project_name
  environment     = var.project_env

  common_tags = local.project_common_tags
}

# EC2 Datadog Host Module Outputs
output "host_datadog_instance_id" {
  description = "ID of the Host-based Datadog EC2 instance"
  value       = module.ec2_datadog_host.instance_id
}

output "host_datadog_public_ip" {
  description = "Public IP of the Host-based Datadog EC2 instance"
  value       = module.ec2_datadog_host.instance_public_ip
}

output "host_datadog_ssh_command" {
  description = "SSH command to connect to the Host-based Datadog instance"
  value       = module.ec2_datadog_host.ssh_command
}

# ============================================
# EC2 Datadog Docker Module
# ============================================
module "ec2_datadog_docker" {
  source = "./modules/ec2-datadog-docker"

  name_prefix        = local.project_name_prefix
  instance_type      = var.ec2_instance_type
  subnet_id          = module.vpc.public_subnet_id
  security_group_ids = [module.security_group.security_group_id]
  key_name           = var.ec2_key_name

  datadog_api_key = var.datadog_api_key
  datadog_site    = var.datadog_site
  project_name    = var.project_name
  environment     = var.project_env

  common_tags = local.project_common_tags
}

# EC2 Datadog Docker Module Outputs
output "docker_datadog_instance_id" {
  description = "ID of the Docker Datadog EC2 instance"
  value       = module.ec2_datadog_docker.instance_id
}

output "docker_datadog_public_ip" {
  description = "Public IP of the Docker Datadog EC2 instance"
  value       = module.ec2_datadog_docker.instance_public_ip
}

output "docker_datadog_ssh_command" {
  description = "SSH command to connect to the Docker Datadog instance"
  value       = module.ec2_datadog_docker.ssh_command
}

