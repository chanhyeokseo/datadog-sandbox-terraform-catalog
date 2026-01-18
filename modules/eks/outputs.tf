# ============================================
# EKS Module Outputs
# ============================================

output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = aws_eks_cluster.main.name
}

output "cluster_arn" {
  description = "ARN of the EKS cluster"
  value       = aws_eks_cluster.main.arn
}

output "cluster_endpoint" {
  description = "Endpoint for the EKS cluster API server"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_version" {
  description = "Kubernetes version of the EKS cluster"
  value       = aws_eks_cluster.main.version
}

output "latest_eks_version" {
  description = "Latest recommended EKS version available"
  value       = data.external.eks_latest_version.result.version
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data for the cluster"
  value       = aws_eks_cluster.main.certificate_authority[0].data
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
}

output "cluster_iam_role_arn" {
  description = "IAM role ARN of the EKS cluster"
  value       = aws_iam_role.cluster.arn
}

output "oidc_provider_arn" {
  description = "ARN of the OIDC Provider for IRSA"
  value       = aws_iam_openid_connect_provider.cluster.arn
}

output "oidc_provider_url" {
  description = "URL of the OIDC Provider"
  value       = aws_iam_openid_connect_provider.cluster.url
}

# Node Group Outputs
output "node_group_name" {
  description = "Name of the EKS node group"
  value       = var.enable_node_group ? aws_eks_node_group.main[0].node_group_name : null
}

output "node_group_arn" {
  description = "ARN of the EKS node group"
  value       = var.enable_node_group ? aws_eks_node_group.main[0].arn : null
}

output "node_group_status" {
  description = "Status of the EKS node group"
  value       = var.enable_node_group ? aws_eks_node_group.main[0].status : null
}

output "node_iam_role_arn" {
  description = "IAM role ARN for the node group"
  value       = var.enable_node_group ? aws_iam_role.node[0].arn : null
}

# Windows Node Group Outputs
output "windows_node_group_name" {
  description = "Name of the Windows EKS node group"
  value       = var.enable_windows_node_group ? aws_eks_node_group.windows[0].node_group_name : null
}

output "windows_node_group_arn" {
  description = "ARN of the Windows EKS node group"
  value       = var.enable_windows_node_group ? aws_eks_node_group.windows[0].arn : null
}

output "windows_node_group_status" {
  description = "Status of the Windows EKS node group"
  value       = var.enable_windows_node_group ? aws_eks_node_group.windows[0].status : null
}

output "windows_node_iam_role_arn" {
  description = "IAM role ARN for the Windows node group"
  value       = var.enable_windows_node_group ? aws_iam_role.windows_node[0].arn : null
}

# Fargate Outputs
output "fargate_profile_name" {
  description = "Name of the Fargate profile"
  value       = var.enable_fargate ? aws_eks_fargate_profile.main[0].fargate_profile_name : null
}

output "fargate_profile_arn" {
  description = "ARN of the Fargate profile"
  value       = var.enable_fargate ? aws_eks_fargate_profile.main[0].arn : null
}

# Kubeconfig command
output "kubeconfig_command" {
  description = "Command to update kubeconfig for kubectl access"
  value       = "aws eks update-kubeconfig --region ${var.region} --name ${aws_eks_cluster.main.name}"
}

