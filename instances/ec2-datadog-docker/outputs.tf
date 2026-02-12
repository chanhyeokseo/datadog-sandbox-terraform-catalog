output "instance_id" {
  value = module.ec2_datadog_docker.instance_id
}
output "public_ip" {
  value = module.ec2_datadog_docker.instance_public_ip
}
output "ssh_command" {
  value = module.ec2_datadog_docker.ssh_command
}
