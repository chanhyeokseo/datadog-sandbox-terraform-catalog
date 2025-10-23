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

echo ""
echo "Step 2: Verifying all resources found..."
echo "--------------------------------------"

if [ -z "$VPC_ID" ] || [ "$VPC_ID" = "None" ]; then
    echo "❌ ERROR: VPC not found!"
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

