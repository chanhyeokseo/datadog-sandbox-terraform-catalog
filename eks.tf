# # ============================================
# # EKS Cluster Configuration
# # ============================================
# module "eks_cluster" {
#   source = "./modules/eks"

#   name_prefix = local.project_name_prefix
#   region      = var.region

#   vpc_id     = local.vpc.vpc_id
#   subnet_ids = [local.vpc.public_subnet_id, local.vpc.public_subnet2_id]

#   enable_node_group   = true
#   node_instance_types = ["t3.medium"]
#   node_desired_size   = 2
#   node_min_size       = 1
#   node_max_size       = 4
#   node_disk_size      = 20
#   node_capacity_type  = "ON_DEMAND"

#   # Windows Node Group Configuration (optional, set to true if you want to use Windows nodes)
#   # Note: Windows nodes require Linux nodes to be enabled for CoreDNS
#   enable_windows_node_group   = true
#   windows_node_instance_types = ["t3.medium"]
#   windows_node_ami_type       = "WINDOWS_FULL_2022_x86_64" # Options: WINDOWS_CORE_2019_x86_64, WINDOWS_FULL_2019_x86_64, WINDOWS_CORE_2022_x86_64, WINDOWS_FULL_2022_x86_64
#   windows_node_desired_size   = 2
#   windows_node_min_size       = 1
#   windows_node_max_size       = 4
#   windows_node_disk_size      = 50
#   windows_node_capacity_type  = "ON_DEMAND"

#   # Fargate Configuration (optional, set to true if you want to use Fargate)
#   enable_fargate     = true
#   fargate_subnet_ids = [local.vpc.private_subnet_id]
#   fargate_namespaces = ["default", "kube-system"]

#   endpoint_public_access  = true
#   endpoint_private_access = true

#   common_tags = local.project_common_tags
# }

# # EKS Cluster Outputs
# output "eks_cluster_name" {
#   description = "Name of the EKS cluster"
#   value       = module.eks_cluster.cluster_name
# }

# output "eks_cluster_endpoint" {
#   description = "Endpoint for the EKS cluster"
#   value       = module.eks_cluster.cluster_endpoint
# }

# output "eks_kubeconfig_command" {
#   description = "Command to configure kubectl"
#   value       = module.eks_cluster.kubeconfig_command
# }

# output "eks_windows_node_group_name" {
#   description = "Name of the Windows node group"
#   value       = module.eks_cluster.windows_node_group_name
# }