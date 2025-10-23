# ============================================
# Local Values
# ============================================
locals {
  # Naming prefixes
  vpc_name_prefix     = "${var.vpc_name}-${var.vpc_env}"
  project_name_prefix = "${var.project_name}-${var.project_env}"
  
  # Common tags for VPC resources
  vpc_common_tags = {
    VPCName     = "${var.vpc_name}-${var.vpc_env}-vpc"
    Environment = var.vpc_env
    ManagedBy   = "Terraform"
  }
  
  # Common tags for project resources
  project_common_tags = {
    Project     = var.project_name
    Environment = var.project_env
    ManagedBy   = "Terraform"
  }
  
  # Subnet CIDR blocks (auto-calculated from VPC CIDR)
  # cidrsubnet(prefix, newbits, netnum)
  public_subnet_cidr   = cidrsubnet(var.vpc_cidr, 8, 1)
  public_subnet2_cidr  = cidrsubnet(var.vpc_cidr, 8, 2)
  private_subnet_cidr  = cidrsubnet(var.vpc_cidr, 8, 3)
  
  # My public IP address (auto-detected)
  my_ip_cidr = "${chomp(data.http.my_ip.response_body)}/32"
}

