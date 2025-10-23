# ============================================
# VPC Module
# ============================================

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-vpc"
    }
  )
}

# Internet Gateway
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-igw"
    }
  )
}

# Public Subnet 1
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr
  map_public_ip_on_launch = true
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-public-subnet-1"
    }
  )
}

# Public Subnet 2
resource "aws_subnet" "public2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet2_cidr
  map_public_ip_on_launch = true
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-public-subnet-2"
    }
  )
}

# Private Subnet
resource "aws_subnet" "private" {
  vpc_id     = aws_vpc.main.id
  cidr_block = var.private_subnet_cidr
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-private-subnet-1"
    }
  )
}

# Public Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  
  lifecycle {
    prevent_destroy = true
  }
  
  tags = merge(
    var.common_tags,
    {
      Name = "${var.name_prefix}-public-rt"
    }
  )
}

# Route to IGW in public route table
resource "aws_route" "public_internet_access" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
  
  lifecycle {
    prevent_destroy = true
  }
}

# Associate public subnet 1 with public route table
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
    var.common_tags,
    {
      Name = "${var.name_prefix}-private-rt"
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

# Shared Base Security Group
resource "aws_security_group" "shared_base" {
  name        = "${var.name_prefix}-shared-base-sg"
  description = "Shared base security group with common egress rules"
  vpc_id      = aws_vpc.main.id

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
    var.common_tags,
    {
      Name        = "${var.name_prefix}-shared-base-sg"
      Description = "Shared base security group - do not add user-specific rules here"
    }
  )
}

