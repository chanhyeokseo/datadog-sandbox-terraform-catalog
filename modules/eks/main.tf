# ============================================
# EKS Cluster Module
# ============================================

data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}

locals {
  cluster_name = "${var.name_prefix}-eks-cluster"
}

# ============================================
# IAM Role for EKS Cluster
# ============================================

resource "aws_iam_role" "cluster" {
  name = "${var.name_prefix}-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-eks-cluster-role"
      service = var.service
    }
  )
}

resource "aws_iam_role_policy_attachment" "cluster_policy" {
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster.name
}

resource "aws_iam_role_policy_attachment" "cluster_vpc_controller" {
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSVPCResourceController"
  role       = aws_iam_role.cluster.name
}

# ============================================
# EKS Cluster
# ============================================

resource "aws_eks_cluster" "main" {
  name     = local.cluster_name
  version  = var.cluster_version
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_public_access  = var.endpoint_public_access
    endpoint_private_access = var.endpoint_private_access
    public_access_cidrs     = var.public_access_cidrs
  }

  # Ensure that IAM Role permissions are created before and deleted after EKS Cluster handling.
  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy,
    aws_iam_role_policy_attachment.cluster_vpc_controller,
  ]

  tags = merge(
    var.common_tags,
    {
      Name    = local.cluster_name
      service = var.service
    }
  )
}

# ============================================
# EKS Add-ons
# ============================================

resource "aws_eks_addon" "vpc_cni" {
  count = var.enable_cluster_addons ? 1 : 0

  cluster_name = aws_eks_cluster.main.name
  addon_name   = "vpc-cni"

  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-vpc-cni"
      service = var.service
    }
  )
}

resource "aws_eks_addon" "coredns" {
  count = var.enable_cluster_addons && var.enable_node_group ? 1 : 0

  cluster_name = aws_eks_cluster.main.name
  addon_name   = "coredns"

  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  depends_on = [
    aws_eks_node_group.main
  ]

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-coredns"
      service = var.service
    }
  )
}

resource "aws_eks_addon" "kube_proxy" {
  count = var.enable_cluster_addons ? 1 : 0

  cluster_name = aws_eks_cluster.main.name
  addon_name   = "kube-proxy"

  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-kube-proxy"
      service = var.service
    }
  )
}

# ============================================
# IAM Role for Node Group
# ============================================

resource "aws_iam_role" "node" {
  count = var.enable_node_group ? 1 : 0

  name = "${var.name_prefix}-eks-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-eks-node-role"
      service = var.service
    }
  )
}

resource "aws_iam_role_policy_attachment" "node_worker" {
  count = var.enable_node_group ? 1 : 0

  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.node[0].name
}

resource "aws_iam_role_policy_attachment" "node_cni" {
  count = var.enable_node_group ? 1 : 0

  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.node[0].name
}

resource "aws_iam_role_policy_attachment" "node_ecr" {
  count = var.enable_node_group ? 1 : 0

  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.node[0].name
}

# ============================================
# EKS Node Group
# ============================================

resource "aws_eks_node_group" "main" {
  count = var.enable_node_group ? 1 : 0

  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.name_prefix}-node-group"
  node_role_arn   = aws_iam_role.node[0].arn
  subnet_ids      = var.subnet_ids

  instance_types = var.node_instance_types
  capacity_type  = var.node_capacity_type
  disk_size      = var.node_disk_size
  ami_type       = var.node_ami_type

  scaling_config {
    desired_size = var.node_desired_size
    min_size     = var.node_min_size
    max_size     = var.node_max_size
  }

  update_config {
    max_unavailable = 1
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_cni,
    aws_iam_role_policy_attachment.node_ecr,
  ]

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-node-group"
      service = var.service
    }
  )
}

# ============================================
# IAM Role for Fargate
# ============================================

resource "aws_iam_role" "fargate" {
  count = var.enable_fargate ? 1 : 0

  name = "${var.name_prefix}-eks-fargate-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "eks-fargate-pods.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-eks-fargate-role"
      service = var.service
    }
  )
}

resource "aws_iam_role_policy_attachment" "fargate_pod_execution" {
  count = var.enable_fargate ? 1 : 0

  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSFargatePodExecutionRolePolicy"
  role       = aws_iam_role.fargate[0].name
}

# ============================================
# EKS Fargate Profile
# ============================================

resource "aws_eks_fargate_profile" "main" {
  count = var.enable_fargate ? 1 : 0

  cluster_name           = aws_eks_cluster.main.name
  fargate_profile_name   = "${var.name_prefix}-fargate-profile"
  pod_execution_role_arn = aws_iam_role.fargate[0].arn
  subnet_ids             = var.subnet_ids

  dynamic "selector" {
    for_each = var.fargate_namespaces
    content {
      namespace = selector.value
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.fargate_pod_execution
  ]

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-fargate-profile"
      service = var.service
    }
  )
}

# ============================================
# OIDC Provider for IRSA (IAM Roles for Service Accounts)
# ============================================

data "tls_certificate" "cluster" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "cluster" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.cluster.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer

  tags = merge(
    var.common_tags,
    {
      Name    = "${var.name_prefix}-eks-oidc"
      service = var.service
    }
  )
}

