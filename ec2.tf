# # ============================================
# # EC2 Instances Configuration
# # ============================================

# # ============================================
# # EC2 Basic Instance Module
# # ============================================
# module "ec2_basic" {
#   source = "./modules/ec2-basic"

#   name_prefix        = local.project_name_prefix
#   instance_type      = var.ec2_instance_type
#   subnet_id          = local.vpc.public_subnet_id
#   security_group_ids = [module.security_group.security_group_id]
#   key_name           = var.ec2_key_name
#   custom_ami_id      = data.aws_ami.amazon_linux_2023.id

#   common_tags = local.project_common_tags
# }

# # EC2 Basic Module Outputs
# output "ec2_basic_instance_id" {
#   description = "ID of the basic EC2 instance"
#   value       = module.ec2_basic.instance_id
# }

# output "ec2_basic_public_ip" {
#   description = "Public IP of the basic EC2 instance"
#   value       = module.ec2_basic.instance_public_ip
# }

# output "ec2_basic_ssh_command" {
#   description = "SSH command to connect to the basic EC2 instance"
#   value       = module.ec2_basic.ssh_command
# }

# # ============================================
# # EC2 Windows Instance Module
# # ============================================
# module "ec2_windows" {
#   source = "./modules/ec2-basic"

#   name_prefix        = "${local.project_name_prefix}-windows"
#   instance_type      = "t3.medium"
#   subnet_id          = local.vpc.public_subnet_id
#   security_group_ids = [module.security_group.security_group_id]
#   key_name           = var.ec2_key_name
#   custom_ami_id      = data.aws_ami.windows_2025.id

#   common_tags = local.project_common_tags
# }

# # EC2 Windows Module Outputs
# output "ec2_windows_instance_id" {
#   description = "ID of the Windows EC2 instance"
#   value       = module.ec2_windows.instance_id
# }

# output "ec2_windows_public_ip" {
#   description = "Public IP of the Windows EC2 instance"
#   value       = module.ec2_windows.instance_public_ip
# }

# output "ec2_windows_rdp_info" {
#   description = "RDP connection information for Windows instance"
#   value       = "Use RDP to connect to ${module.ec2_windows.instance_public_ip} - Get password using your key pair"
# }

# # ============================================
# # EC2 Windows 2016 Instance Module
# # ============================================
# module "ec2_windows_2016" {
#   source = "./modules/ec2-basic"

#   name_prefix        = "${local.project_name_prefix}-windows-2016"
#   instance_type      = "t3.medium"
#   subnet_id          = local.vpc.public_subnet_id
#   security_group_ids = [module.security_group.security_group_id]
#   key_name           = var.ec2_key_name
#   custom_ami_id      = data.aws_ami.windows_2016.id

#   common_tags = local.project_common_tags
# }

# # EC2 Windows 2016 Module Outputs
# output "ec2_windows_2016_instance_id" {
#   description = "ID of the Windows 2016 EC2 instance"
#   value       = module.ec2_windows_2016.instance_id
# }

# output "ec2_windows_2016_public_ip" {
#   description = "Public IP of the Windows 2016 EC2 instance"
#   value       = module.ec2_windows_2016.instance_public_ip
# }

# output "ec2_windows_2016_rdp_info" {
#   description = "RDP connection information for Windows 2016 instance"
#   value       = "Use RDP to connect to ${module.ec2_windows_2016.instance_public_ip} - Get password using your key pair"
# }

# # ============================================
# # EC2 Datadog Host Module
# # ============================================
# module "ec2_datadog_host" {
#   source = "./modules/ec2-datadog-host"

#   name_prefix       = local.project_name_prefix
#   instance_type     = var.ec2_instance_type
#   subnet_id         = module.vpc.public_subnet_id
#   security_group_ids = [module.security_group.security_group_id]
#   key_name          = var.ec2_key_name
#   custom_ami_id     = data.aws_ami.amazon_linux_2023.id

#   datadog_api_key = var.datadog_api_key
#   datadog_site    = var.datadog_site
#   project_name    = var.project_name
#   environment     = var.project_env

#   common_tags = local.project_common_tags
# }

# # EC2 Datadog Host Module Outputs
# output "host_datadog_instance_id" {
#   description = "ID of the Host-based Datadog EC2 instance"
#   value       = module.ec2_datadog_host.instance_id
# }

# output "host_datadog_public_ip" {
#   description = "Public IP of the Host-based Datadog EC2 instance"
#   value       = module.ec2_datadog_host.instance_public_ip
# }

# output "host_datadog_ssh_command" {
#   description = "SSH command to connect to the Host-based Datadog instance"
#   value       = module.ec2_datadog_host.ssh_command
# }

# # ============================================
# # EC2 Datadog Docker Module
# # ============================================
# module "ec2_datadog_docker" {
#   source = "./modules/ec2-datadog-docker"

#   name_prefix        = local.project_name_prefix
#   instance_type      = "t3.medium"
#   subnet_id          = local.vpc.public_subnet_id
#   security_group_ids = [module.security_group.security_group_id]
#   key_name           = var.ec2_key_name
#   custom_ami_id      = data.aws_ami.amazon_linux_2023.id

#   datadog_api_key = var.datadog_api_key
#   datadog_site    = var.datadog_site
#   project_name    = var.project_name
#   environment     = var.project_env

#   common_tags = local.project_common_tags
# }

# # EC2 Datadog Docker Module Outputs
# output "docker_datadog_instance_id" {
#   description = "ID of the Docker Datadog EC2 instance"
#   value       = module.ec2_datadog_docker.instance_id
# }

# output "docker_datadog_public_ip" {
#   description = "Public IP of the Docker Datadog EC2 instance"
#   value       = module.ec2_datadog_docker.instance_public_ip
# }

# output "docker_datadog_ssh_command" {
#   description = "SSH command to connect to the Docker Datadog instance"
#   value       = module.ec2_datadog_docker.ssh_command
# }

# # ============================================
# # ECS EC2 Container Instance
# # ============================================

# # Get ECS optimized AMI
# data "aws_ami" "ecs_optimized" {
#   most_recent = true
#   owners      = ["amazon"]

#   filter {
#     name   = "name"
#     values = ["amzn2-ami-ecs-hvm-*-x86_64-ebs"]
#   }

#   filter {
#     name   = "virtualization-type"
#     values = ["hvm"]
#   }
# }

# # IAM Role for ECS EC2 Instance
# resource "aws_iam_role" "ecs_instance_role" {
#   name = "${local.project_name_prefix}-ecs-instance-role"

#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Action = "sts:AssumeRole"
#         Effect = "Allow"
#         Principal = {
#           Service = "ec2.amazonaws.com"
#         }
#       }
#     ]
#   })

#   tags = merge(
#     local.project_common_tags,
#     {
#       Name = "${local.project_name_prefix}-ecs-instance-role"
#     }
#   )
# }

# # Attach ECS Instance Role Policy
# resource "aws_iam_role_policy_attachment" "ecs_instance_role_policy" {
#   role       = aws_iam_role.ecs_instance_role.name
#   policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
# }

# # IAM Instance Profile
# resource "aws_iam_instance_profile" "ecs_instance_profile" {
#   name = "${local.project_name_prefix}-ecs-instance-profile"
#   role = aws_iam_role.ecs_instance_role.name

#   tags = merge(
#     local.project_common_tags,
#     {
#       Name = "${local.project_name_prefix}-ecs-instance-profile"
#     }
#   )
# }

# # ECS EC2 Instance
# resource "aws_instance" "ecs_instance" {
#   ami                    = data.aws_ami.ecs_optimized.id
#   instance_type          = "t3.medium"  # 4GB RAM for ECS tasks
#   subnet_id              = module.vpc.public_subnet_id
#   vpc_security_group_ids = [module.security_group.security_group_id]
#   key_name               = var.ec2_key_name
#   iam_instance_profile   = aws_iam_instance_profile.ecs_instance_profile.name

#   user_data = <<-EOF
#               #!/bin/bash
#               echo ECS_CLUSTER=${module.ecs_ec2_datadog.cluster_name} >> /etc/ecs/ecs.config
#               EOF

#   tags = merge(
#     local.project_common_tags,
#     {
#       Name = "${local.project_name_prefix}-ecs-instance"
#     }
#   )
# }

# # ECS Instance Outputs
# output "ecs_instance_id" {
#   description = "ID of the ECS EC2 instance"
#   value       = aws_instance.ecs_instance.id
# }

# output "ecs_instance_public_ip" {
#   description = "Public IP of the ECS EC2 instance"
#   value       = aws_instance.ecs_instance.public_ip
# }

# output "ecs_instance_ssh_command" {
#   description = "SSH command to connect to the ECS instance"
#   value       = "ssh -i ~/.ssh/${var.ec2_key_name}.pem ec2-user@${aws_instance.ecs_instance.public_ip}"
# }