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