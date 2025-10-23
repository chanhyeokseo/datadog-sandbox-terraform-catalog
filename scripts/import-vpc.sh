#!/bin/bash

# ============================================
# Import Shared VPC Resources Script
# ============================================
# This script helps import existing shared VPC resources into your Terraform state

set -e

echo "=========================================="
echo "Shared VPC Import Script"
echo "=========================================="
echo ""

# Configuration
REGION="${AWS_REGION:-ap-northeast-2}"
VPC_NAME_PREFIX="shared-test"

echo "Using AWS Region: $REGION"
echo "VPC Name Prefix: $VPC_NAME_PREFIX"
echo ""

# Function to get resource ID
get_resource_id() {
    local resource_type=$1
    local filter_name=$2
    local filter_value=$3
    local query=$4
    
    aws ec2 describe-${resource_type} \
        --region "$REGION" \
        --filters "Name=${filter_name},Values=${filter_value}" \
        --query "${query}" \
        --output text
}

echo "Step 1: Fetching VPC Resource IDs..."
echo "--------------------------------------"

# Get VPC ID
VPC_ID=$(get_resource_id "vpcs" "tag:Name" "${VPC_NAME_PREFIX}-vpc" 'Vpcs[0].VpcId')
echo "VPC ID: $VPC_ID"

# Get Internet Gateway ID
IGW_ID=$(get_resource_id "internet-gateways" "tag:Name" "${VPC_NAME_PREFIX}-igw" 'InternetGateways[0].InternetGatewayId')
echo "Internet Gateway ID: $IGW_ID"

# Get Subnet IDs
PUBLIC_SUBNET_1_ID=$(get_resource_id "subnets" "tag:Name" "${VPC_NAME_PREFIX}-public-subnet-1" 'Subnets[0].SubnetId')
echo "Public Subnet 1 ID: $PUBLIC_SUBNET_1_ID"

PUBLIC_SUBNET_2_ID=$(get_resource_id "subnets" "tag:Name" "${VPC_NAME_PREFIX}-public-subnet-2" 'Subnets[0].SubnetId')
echo "Public Subnet 2 ID: $PUBLIC_SUBNET_2_ID"

PRIVATE_SUBNET_1_ID=$(get_resource_id "subnets" "tag:Name" "${VPC_NAME_PREFIX}-private-subnet-1" 'Subnets[0].SubnetId')
echo "Private Subnet 1 ID: $PRIVATE_SUBNET_1_ID"

# Get Route Table IDs
PUBLIC_RT_ID=$(get_resource_id "route-tables" "tag:Name" "${VPC_NAME_PREFIX}-public-rt" 'RouteTables[0].RouteTableId')
echo "Public Route Table ID: $PUBLIC_RT_ID"

PRIVATE_RT_ID=$(get_resource_id "route-tables" "tag:Name" "${VPC_NAME_PREFIX}-private-rt" 'RouteTables[0].RouteTableId')
echo "Private Route Table ID: $PRIVATE_RT_ID"

# Get Security Group ID
SG_ID=$(get_resource_id "security-groups" "tag:Name" "${VPC_NAME_PREFIX}-ec2-sg" 'SecurityGroups[0].GroupId')
echo "Security Group ID: $SG_ID"

echo ""
echo "Step 2: Verifying all resources found..."
echo "--------------------------------------"

if [ -z "$VPC_ID" ] || [ "$VPC_ID" = "None" ]; then
    echo "❌ ERROR: VPC not found!"
    exit 1
fi

if [ -z "$IGW_ID" ] || [ "$IGW_ID" = "None" ]; then
    echo "❌ ERROR: Internet Gateway not found!"
    exit 1
fi

if [ -z "$PUBLIC_SUBNET_1_ID" ] || [ "$PUBLIC_SUBNET_1_ID" = "None" ]; then
    echo "❌ ERROR: Public Subnet 1 not found!"
    exit 1
fi

if [ -z "$PUBLIC_SUBNET_2_ID" ] || [ "$PUBLIC_SUBNET_2_ID" = "None" ]; then
    echo "❌ ERROR: Public Subnet 2 not found!"
    exit 1
fi

if [ -z "$PRIVATE_SUBNET_1_ID" ] || [ "$PRIVATE_SUBNET_1_ID" = "None" ]; then
    echo "❌ ERROR: Private Subnet 1 not found!"
    exit 1
fi

if [ -z "$PUBLIC_RT_ID" ] || [ "$PUBLIC_RT_ID" = "None" ]; then
    echo "❌ ERROR: Public Route Table not found!"
    exit 1
fi

if [ -z "$PRIVATE_RT_ID" ] || [ "$PRIVATE_RT_ID" = "None" ]; then
    echo "❌ ERROR: Private Route Table not found!"
    exit 1
fi

if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
    echo "❌ ERROR: Security Group not found!"
    exit 1
fi

echo "✅ All resource IDs retrieved successfully!"
echo ""

read -p "Do you want to proceed with importing these resources? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Import cancelled."
    exit 0
fi

echo ""
echo "Step 3: Importing resources into Terraform state..."
echo "--------------------------------------"

# Import VPC
echo "Importing VPC..."
terraform import aws_vpc.main "$VPC_ID" || echo "⚠️  VPC already imported or failed"

# Import Internet Gateway
echo "Importing Internet Gateway..."
terraform import aws_internet_gateway.igw "$IGW_ID" || echo "⚠️  IGW already imported or failed"

# Import Subnets
echo "Importing Public Subnet 1..."
terraform import aws_subnet.public "$PUBLIC_SUBNET_1_ID" || echo "⚠️  Public Subnet 1 already imported or failed"

echo "Importing Public Subnet 2..."
terraform import aws_subnet.public2 "$PUBLIC_SUBNET_2_ID" || echo "⚠️  Public Subnet 2 already imported or failed"

echo "Importing Private Subnet 1..."
terraform import aws_subnet.private "$PRIVATE_SUBNET_1_ID" || echo "⚠️  Private Subnet 1 already imported or failed"

# Import Route Tables
echo "Importing Public Route Table..."
terraform import aws_route_table.public "$PUBLIC_RT_ID" || echo "⚠️  Public Route Table already imported or failed"

echo "Importing Private Route Table..."
terraform import aws_route_table.private "$PRIVATE_RT_ID" || echo "⚠️  Private Route Table already imported or failed"

# Import Route (for public internet access)
echo "Importing Public Internet Route..."
terraform import aws_route.public_internet_access "${PUBLIC_RT_ID}_0.0.0.0/0" || echo "⚠️  Public Internet Route already imported or failed"

# Import Route Table Associations
echo "Importing Public Subnet 1 Route Table Association..."
terraform import aws_route_table_association.public_assoc "$PUBLIC_SUBNET_1_ID/$PUBLIC_RT_ID" || echo "⚠️  Public Subnet 1 association already imported or failed"

echo "Importing Public Subnet 2 Route Table Association..."
terraform import aws_route_table_association.public2_assoc "$PUBLIC_SUBNET_2_ID/$PUBLIC_RT_ID" || echo "⚠️  Public Subnet 2 association already imported or failed"

echo "Importing Private Subnet Route Table Association..."
terraform import aws_route_table_association.private_assoc "$PRIVATE_SUBNET_1_ID/$PRIVATE_RT_ID" || echo "⚠️  Private Subnet association already imported or failed"

# Import Security Group
echo "Importing EC2 Security Group..."
terraform import aws_security_group.ec2 "$SG_ID" || echo "⚠️  Security Group already imported or failed"

echo ""
echo "=========================================="
echo "✅ Import Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run 'terraform plan' to verify the import"
echo "2. Review any differences and update your configuration"
echo "3. Run 'terraform apply' to create your personal resources"
echo ""

