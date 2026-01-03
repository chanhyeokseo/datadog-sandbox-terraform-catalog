# ============================================
# EKS Module Variables
# ============================================

variable "name_prefix" {
  description = "Name prefix for EKS resources"
  type        = string
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS cluster. Leave empty to use latest version."
  type        = string
  default     = ""
}

# ============================================
# Network Configuration
# ============================================

variable "vpc_id" {
  description = "VPC ID where EKS cluster will be created"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for EKS cluster (at least 2 in different AZs)"
  type        = list(string)
}

# ============================================
# Node Group Configuration
# ============================================

variable "enable_node_group" {
  description = "Enable managed node group"
  type        = bool
  default     = true
}

variable "node_instance_types" {
  description = "Instance types for the node group"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_desired_size" {
  description = "Desired number of nodes"
  type        = number
  default     = 2
}

variable "node_min_size" {
  description = "Minimum number of nodes"
  type        = number
  default     = 1
}

variable "node_max_size" {
  description = "Maximum number of nodes"
  type        = number
  default     = 4
}

variable "node_disk_size" {
  description = "Disk size in GB for worker nodes"
  type        = number
  default     = 20
}

variable "node_ami_type" {
  description = "AMI type for the node group (AL2_x86_64, AL2_x86_64_GPU, AL2_ARM_64, BOTTLEROCKET_x86_64, BOTTLEROCKET_ARM_64)"
  type        = string
  default     = "AL2023_x86_64_STANDARD"
}

variable "node_capacity_type" {
  description = "Capacity type for the node group (ON_DEMAND, SPOT)"
  type        = string
  default     = "ON_DEMAND"
}

# ============================================
# Fargate Configuration
# ============================================

variable "enable_fargate" {
  description = "Enable Fargate profile"
  type        = bool
  default     = false
}

variable "fargate_namespaces" {
  description = "List of Kubernetes namespaces for Fargate profile"
  type        = list(string)
  default     = ["default", "kube-system"]
}

variable "fargate_subnet_ids" {
  description = "List of private subnet IDs for Fargate profile (must be private subnets)"
  type        = list(string)
  default     = []
}

# ============================================
# Access Configuration
# ============================================

variable "endpoint_public_access" {
  description = "Enable public access to EKS API endpoint"
  type        = bool
  default     = true
}

variable "endpoint_private_access" {
  description = "Enable private access to EKS API endpoint"
  type        = bool
  default     = true
}

variable "public_access_cidrs" {
  description = "List of CIDR blocks that can access the EKS public API endpoint"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# ============================================
# Add-ons Configuration
# ============================================

variable "enable_cluster_addons" {
  description = "Enable EKS managed add-ons (vpc-cni, coredns, kube-proxy)"
  type        = bool
  default     = true
}

# ============================================
# Tags
# ============================================

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "service" {
  description = "Service name for tagging"
  type        = string
  default     = "eks"
}

variable "region" {
  description = "AWS region for kubeconfig command"
  type        = string
  default     = "ap-northeast-2"
}

