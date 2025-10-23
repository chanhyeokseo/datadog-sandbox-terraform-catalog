# # ============================================
# # EC2 Instance
# # ============================================
# resource "aws_instance" "host" {
#   ami           = data.aws_ami.amazon_linux_2023.id
#   instance_type = var.ec2_instance_type

#   subnet_id = aws_subnet.public.id
#   # Attach both shared and personal security groups
#   vpc_security_group_ids = [
#     aws_security_group.personal_ec2.id
#   ]
#   associate_public_ip_address = true

#   key_name = var.ec2_key_name

#   tags = merge(
#     local.project_common_tags,
#     {
#       Name = "${local.project_name_prefix}-host"
#     }
#   )
# }

# # ============================================
# # Outputs
# # ============================================

# output "ssh_command" {
#   description = "SSH command to connect to the EC2 host"
#   value       = "ssh -i ${var.ec2_key_name}.pem ec2-user@${aws_instance.host.public_ip}"
# }