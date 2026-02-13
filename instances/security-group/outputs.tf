output "project_name_prefix" {
  value = local.project_name_prefix
}
output "project_common_tags" {
  value = local.project_common_tags
}
output "security_group_id" {
  value = module.security_group.security_group_id
}
output "security_group_name" {
  value = module.security_group.security_group_name
}
output "security_group_ingress_rules" {
  value = module.security_group.security_group_ingress_rules
}
output "security_group_egress_rules" {
  value = module.security_group.security_group_egress_rules
}
output "vpc_id" {
  value = var.vpc_id
}
output "public_subnet_id" {
  value = var.public_subnet_id
}
output "public_subnet2_id" {
  value = var.public_subnet2_id
}
output "private_subnet_id" {
  value = var.private_subnet_id
}
output "ec2_key_name" {
  value = var.ec2_key_name
}
