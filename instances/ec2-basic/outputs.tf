output "instance_id" {
  value = module.ec2_basic.instance_id
}
output "public_ip" {
  value = module.ec2_basic.instance_public_ip
}
output "ssh_command" {
  value = module.ec2_basic.ssh_command
}
