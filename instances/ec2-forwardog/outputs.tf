output "instance_id" {
  value = module.ec2_forwardog.instance_id
}
output "public_ip" {
  value = module.ec2_forwardog.instance_public_ip
}
output "ssh_command" {
  value = module.ec2_forwardog.ssh_command
}
output "forwardog_url" {
  value = module.ec2_forwardog.forwardog_url
}
