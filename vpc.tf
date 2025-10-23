# ============================================
# VPC
# ============================================
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = merge(
    local.vpc_common_tags,
    {
      Name = "${local.vpc_name_prefix}-vpc"
    }
  )
}

# ============================================
# Internet Gateway
# ============================================
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = merge(
    local.vpc_common_tags,
    {
      Name = "${local.vpc_name_prefix}-igw"
    }
  )
}

# ============================================
# Subnets
# ============================================

# Public Subnet 1
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = local.public_subnet_cidr
  map_public_ip_on_launch = true
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = merge(
    local.vpc_common_tags,
    {
      Name = "${local.vpc_name_prefix}-public-subnet-1"
    }
  )
}

# Public Subnet 2
resource "aws_subnet" "public2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = local.public_subnet2_cidr
  map_public_ip_on_launch = true
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = merge(
    local.vpc_common_tags,
    {
      Name = "${local.vpc_name_prefix}-public-subnet-2"
    }
  )
}

# Private Subnet
resource "aws_subnet" "private" {
  vpc_id     = aws_vpc.main.id
  cidr_block = local.private_subnet_cidr
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = merge(
    local.vpc_common_tags,
    {
      Name = "${local.vpc_name_prefix}-private-subnet-1"
    }
  )
}

# ============================================
# Route Tables
# ============================================

# Public Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = merge(
    local.vpc_common_tags,
    {
      Name = "${local.vpc_name_prefix}-public-rt"
    }
  )
}

# ============================================
# Routes and Route Table Associations
# ============================================

# Route to IGW in public route table
resource "aws_route" "public_internet_access" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
  
  lifecycle {
    prevent_destroy = true
  }
}

# Associate public subnet with public route table
resource "aws_route_table_association" "public_assoc" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
  
  lifecycle {
    prevent_destroy = true
  }
}

# Associate public subnet 2 with public route table
resource "aws_route_table_association" "public2_assoc" {
  subnet_id      = aws_subnet.public2.id
  route_table_id = aws_route_table.public.id
  
  lifecycle {
    prevent_destroy = true
  }
}

# Private Route Table
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = merge(
    local.vpc_common_tags,
    {
      Name = "${local.vpc_name_prefix}-private-rt"
    }
  )
}

# Associate private subnet with private route table
resource "aws_route_table_association" "private_assoc" {
  subnet_id      = aws_subnet.private.id
  route_table_id = aws_route_table.private.id
  
  lifecycle {
    prevent_destroy = true
  }
}

# ============================================
# Security Groups
# ============================================

# Security Group for SSH access
resource "aws_security_group" "ec2" {
  name        = "${local.vpc_name_prefix}-ec2-sg"
  description = "Security group for EC2 access"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Allow SSH from my IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [local.my_ip_cidr]
  }

  ingress {
    description = "Allow UDP from my IP"
    from_port   = 8125
    to_port     = 8125
    protocol    = "udp"
    cidr_blocks = [local.my_ip_cidr]
  }

  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  lifecycle {
    prevent_destroy = true
  }

  tags = merge(
    local.vpc_common_tags,
    {
      Name = "${local.vpc_name_prefix}-ec2-sg"
    }
  )

}

# ============================================
# Outputs
# ============================================

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "ssh_security_group_id" {
  description = "Security group ID for EC2 access"
  value       = aws_security_group.ec2.id
}

output "my_public_ip" {
  description = "Your detected public IP address"
  value       = local.my_ip_cidr
}