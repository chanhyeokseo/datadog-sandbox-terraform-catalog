# ============================================
# EC2 Instances Configuration
# ============================================

# ============================================
# EC2 Linux Basic Instance
# ============================================
module "ec2_basic" {
  source             = "./modules/ec2-basic"
  name_prefix        = local.name_prefix
  instance_type      = var.ec2_instance_type
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = [module.security_group.security_group_id]
  key_name           = var.ec2_key_name
  custom_ami_id      = data.aws_ami.amazon_linux_2023.id
  common_tags        = local.common_tags
}

# EC2 Linux Basic Outputs
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
# EC2 Linux Datadog Host
# ============================================
module "ec2_datadog_host" {
  source = "./modules/ec2-datadog-host"

  name_prefix        = local.name_prefix
  instance_type      = var.ec2_instance_type
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = [module.security_group.security_group_id]
  key_name           = var.ec2_key_name
  custom_ami_id      = data.aws_ami.amazon_linux_2023.id

  datadog_api_key = var.datadog_api_key
  datadog_site    = var.datadog_site
  creator = var.creator
  team    = var.team

  common_tags = local.common_tags
}

# EC2 Datadog Host Outputs
output "ec2_datadog_host_instance_id" {
  description = "ID of the Host-based Datadog EC2 instance"
  value       = module.ec2_datadog_host.instance_id
}

output "ec2_datadog_host_public_ip" {
  description = "Public IP of the Host-based Datadog EC2 instance"
  value       = module.ec2_datadog_host.instance_public_ip
}

output "ec2_datadog_host_ssh_command" {
  description = "SSH command to connect to the Host-based Datadog instance"
  value       = module.ec2_datadog_host.ssh_command
}

# ============================================
# EC2 Linux Datadog Docker
# ============================================
module "ec2_datadog_docker" {
  source = "./modules/ec2-datadog-docker"

  name_prefix        = local.name_prefix
  instance_type      = "t3.medium"
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = [module.security_group.security_group_id]
  key_name           = var.ec2_key_name
  custom_ami_id      = data.aws_ami.amazon_linux_2023.id

  datadog_api_key = var.datadog_api_key
  datadog_site    = var.datadog_site
  creator = var.creator
  team    = var.team

  common_tags = local.common_tags
}

# EC2 Datadog Docker Outputs
output "ec2_datadog_docker_instance_id" {
  description = "ID of the Docker Datadog EC2 instance"
  value       = module.ec2_datadog_docker.instance_id
}

output "ec2_datadog_docker_public_ip" {
  description = "Public IP of the Docker Datadog EC2 instance"
  value       = module.ec2_datadog_docker.instance_public_ip
}

output "ec2_datadog_docker_ssh_command" {
  description = "SSH command to connect to the Docker Datadog instance"
  value       = module.ec2_datadog_docker.ssh_command
}

# ============================================
# EC2 Windows Instance
# ============================================
module "ec2_windows" {
  source = "./modules/ec2-basic"

  name_prefix        = "${local.name_prefix}-windows"
  instance_type      = "t3.medium"
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = [module.security_group.security_group_id]
  key_name           = var.ec2_key_name
  custom_ami_id      = data.aws_ami.windows_2025.id
  get_password_data  = true

  common_tags = local.common_tags
}

# EC2 Windows Instance Outputs
output "ec2_windows_instance_id" {
  description = "ID of the Windows EC2 instance"
  value       = module.ec2_windows.instance_id
}

output "ec2_windows_public_ip" {
  description = "Public IP of the Windows EC2 instance"
  value       = module.ec2_windows.instance_public_ip
}

output "ec2_windows_rdp_info" {
  description = "RDP connection information for Windows instance"
  value       = "RDP to ${module.ec2_windows.instance_public_ip} | User: Administrator"
}

output "ec2_windows_password" {
  description = "Administrator password for Windows instance (decrypted)"
  value       = module.ec2_windows.password_data != "" ? rsadecrypt(module.ec2_windows.password_data, file(var.ssh_private_key_path)) : "Password not yet available (wait ~4 minutes after instance creation)"
  sensitive   = false # true if you want to redact the password in the output
}

# ============================================
# EC2 Windows Server 2016 Instance
# ============================================
module "ec2_windows_2016" {
  source = "./modules/ec2-basic"

  name_prefix        = "${local.name_prefix}-windows-2016"
  instance_type      = "t3.medium"
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = [module.security_group.security_group_id]
  key_name           = var.ec2_key_name
  custom_ami_id      = data.aws_ami.windows_2016.id
  get_password_data  = true

  common_tags = local.common_tags
}

# EC2 Windows 2016 Instance Outputs
output "ec2_windows_2016_instance_id" {
  description = "ID of the Windows 2016 EC2 instance"
  value       = module.ec2_windows_2016.instance_id
}

output "ec2_windows_2016_public_ip" {
  description = "Public IP of the Windows 2016 EC2 instance"
  value       = module.ec2_windows_2016.instance_public_ip
}

output "ec2_windows_2016_rdp_info" {
  description = "RDP connection information for Windows 2016 instance"
  value       = "RDP to ${module.ec2_windows_2016.instance_public_ip} | User: Administrator"
}

output "ec2_windows_2016_password" {
  description = "Administrator password for Windows 2016 instance (decrypted)"
  value       = module.ec2_windows_2016.password_data != "" ? rsadecrypt(module.ec2_windows_2016.password_data, file(var.ssh_private_key_path)) : "Password not yet available (wait ~4 minutes after instance creation)"
  sensitive   = false # true if you want to redact the password in the output
}

# ============================================
# EC2 Windows Server 2022 Instance
# ============================================
module "ec2_windows_2022" {
  source = "./modules/ec2-basic"

  name_prefix        = "${local.name_prefix}-windows-2022"
  instance_type      = "t3.medium"
  subnet_id          = local.vpc.public_subnet_id
  security_group_ids = [module.security_group.security_group_id]
  key_name           = var.ec2_key_name
  custom_ami_id      = data.aws_ami.windows_2022.id
  get_password_data  = true

  common_tags = local.common_tags
}

# EC2 Windows 2022 Instance Outputs
output "ec2_windows_2022_instance_id" {
  description = "ID of the Windows 2022 EC2 instance"
  value       = module.ec2_windows_2022.instance_id
}

output "ec2_windows_2022_public_ip" {
  description = "Public IP of the Windows 2022 EC2 instance"
  value       = module.ec2_windows_2022.instance_public_ip
}

output "ec2_windows_2022_rdp_info" {
  description = "RDP connection information for Windows 2022 instance"
  value       = "RDP to ${module.ec2_windows_2022.instance_public_ip} | User: Administrator"
}

output "ec2_windows_2022_password" {
  description = "Administrator password for Windows 2022 instance (decrypted)"
  value       = module.ec2_windows_2022.password_data != "" ? rsadecrypt(module.ec2_windows_2022.password_data, file(var.ssh_private_key_path)) : "Password not yet available (wait ~4 minutes after instance creation)"
  sensitive   = false # true if you want to redact the password in the output
}