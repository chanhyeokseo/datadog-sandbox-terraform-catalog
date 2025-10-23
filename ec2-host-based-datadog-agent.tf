# # ============================================
# # EC2 Instance with Datadog Agent
# # ============================================

# # User data script for installing Datadog agent
# locals {
#   datadog_user_data = <<-EOF
#     #!/bin/bash
#     set -e
    
#     # Update system
#     dnf update -y
    
#     # Install Datadog Agent
#     DD_API_KEY="${var.datadog_api_key}" \
#     DD_SITE="${var.datadog_site}" \
#     bash -c "$(curl -L https://install.datadoghq.com/scripts/install_script_agent7.sh)"
#   EOF
# }

# # EC2 Instance with Datadog Agent
# resource "aws_instance" "datadog_host" {
#   ami           = data.aws_ami.amazon_linux_2023.id
#   instance_type = var.ec2_instance_type

#   subnet_id                   = aws_subnet.public.id
#   vpc_security_group_ids      = [aws_security_group.ec2.id]
#   associate_public_ip_address = true

#   key_name = var.ec2_key_name

#   user_data = local.datadog_user_data

#   # Ensure user data runs on every boot (optional)
#   user_data_replace_on_change = true

#   tags = merge(
#     local.project_common_tags,
#     {
#       Name = "${local.project_name_prefix}-datadog-host"
#     }
#   )
# }

# # ============================================
# # Outputs
# # ============================================

# output "datadog_ssh_command" {
#   description = "SSH command to connect to the Datadog EC2 host"
#   value       = "ssh -i ${var.ec2_key_name}.pem ec2-user@${aws_instance.datadog_host.public_ip}"
# }