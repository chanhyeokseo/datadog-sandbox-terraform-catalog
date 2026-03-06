output "cluster_name" {
  value = module.eks_cluster.cluster_name
}
output "cluster_endpoint" {
  value = module.eks_cluster.cluster_endpoint
}
output "kubeconfig_command" {
  value = module.eks_cluster.kubeconfig_command
}
output "windows_node_group_name" {
  value = module.eks_cluster.windows_node_group_name
}
output "sso_login_command" {
  value = module.eks_cluster.sso_login_command
}
output "enable_node_group" {
  value = var.enable_node_group
}
output "node_instance_types" {
  value = var.node_instance_types
}
output "node_desired_size" {
  value = var.node_desired_size
}
output "node_min_size" {
  value = var.node_min_size
}
output "node_max_size" {
  value = var.node_max_size
}
output "node_disk_size" {
  value = var.node_disk_size
}
output "node_capacity_type" {
  value = var.node_capacity_type
}
output "enable_windows_node_group" {
  value = var.enable_windows_node_group
}
output "windows_node_instance_types" {
  value = var.windows_node_instance_types
}
output "windows_node_ami_type" {
  value = var.windows_node_ami_type
}
output "windows_node_desired_size" {
  value = var.windows_node_desired_size
}
output "windows_node_min_size" {
  value = var.windows_node_min_size
}
output "windows_node_max_size" {
  value = var.windows_node_max_size
}
output "windows_node_disk_size" {
  value = var.windows_node_disk_size
}
output "windows_node_capacity_type" {
  value = var.windows_node_capacity_type
}
output "enable_fargate" {
  value = var.enable_fargate
}
output "fargate_namespaces" {
  value = var.fargate_namespaces
}
output "endpoint_public_access" {
  value = var.endpoint_public_access
}
output "endpoint_private_access" {
  value = var.endpoint_private_access
}