# Guide: Importing Shared VPC Resources

This guide helps new users import the existing shared VPC infrastructure into their local Terraform state, allowing them to manage their own resources (like EC2 instances) within the shared VPC.

## Overview

The shared VPC infrastructure is already deployed and includes:
- VPC
- Internet Gateway
- Public and Private Subnets
- Route Tables and Associations
- Security Groups

**You will import these** to reference them, but **you won't manage them** (to prevent accidental changes).

## Step 1: Configure Your Variables

Create or update `terraform.tfvars` using `terraform.tfvars.example`.

## Step 2: Get Existing VPC Resource IDs

You need to get the IDs of existing resources. Run these AWS CLI commands:

```bash
# Set the region
export AWS_REGION="ap-northeast-2"

# Get VPC ID
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=shared-test-vpc" --query 'Vpcs[0].VpcId' --output text

# Get Internet Gateway ID
aws ec2 describe-internet-gateways --filters "Name=tag:Name,Values=shared-test-igw" --query 'InternetGateways[0].InternetGatewayId' --output text

# Get Public Subnet 1 ID
aws ec2 describe-subnets --filters "Name=tag:Name,Values=shared-test-public-subnet-1" --query 'Subnets[0].SubnetId' --output text

# Get Public Subnet 2 ID
aws ec2 describe-subnets --filters "Name=tag:Name,Values=shared-test-public-subnet-2" --query 'Subnets[0].SubnetId' --output text

# Get Private Subnet ID
aws ec2 describe-subnets --filters "Name=tag:Name,Values=shared-test-private-subnet-1" --query 'Subnets[0].SubnetId' --output text

# Get Public Route Table ID
aws ec2 describe-route-tables --filters "Name=tag:Name,Values=shared-test-public-rt" --query 'RouteTables[0].RouteTableId' --output text

# Get Private Route Table ID
aws ec2 describe-route-tables --filters "Name=tag:Name,Values=shared-test-private-rt" --query 'RouteTables[0].RouteTableId' --output text

# Get Security Group ID
aws ec2 describe-security-groups --filters "Name=tag:Name,Values=shared-test-ec2-sg" --query 'SecurityGroups[0].GroupId' --output text
```

Save these IDs - you'll need them in the next step.

## Step 3: Initialize Terraform

```bash
terraform init
```

## Step 4: Import VPC Resources

Replace `<RESOURCE_ID>` with the actual IDs from Step 2:

```bash
# Import VPC
terraform import aws_vpc.main <VPC_ID>

# Import Internet Gateway
terraform import aws_internet_gateway.igw <IGW_ID>

# Import Public Subnet 1
terraform import aws_subnet.public <PUBLIC_SUBNET_1_ID>

# Import Public Subnet 2
terraform import aws_subnet.public2 <PUBLIC_SUBNET_2_ID>

# Import Private Subnet
terraform import aws_subnet.private <PRIVATE_SUBNET_ID>

# Import Public Route Table
terraform import aws_route_table.public <PUBLIC_RT_ID>

# Import Private Route Table
terraform import aws_route_table.private <PRIVATE_RT_ID>

# Import Route to Internet Gateway
terraform import aws_route.public_internet_access <PUBLIC_RT_ID>_0.0.0.0/0

# Import Route Table Associations
terraform import aws_route_table_association.public_assoc <PUBLIC_SUBNET_1_ID>/<PUBLIC_RT_ID>
terraform import aws_route_table_association.public2_assoc <PUBLIC_SUBNET_2_ID>/<PUBLIC_RT_ID>
terraform import aws_route_table_association.private_assoc <PRIVATE_SUBNET_ID>/<PRIVATE_RT_ID>

# Import Security Group
terraform import aws_security_group.ec2 <SECURITY_GROUP_ID>
```

### Example with Real IDs:

```bash
# Example (replace with your actual IDs)
terraform import aws_vpc.main vpc-0123456789abcdef0
terraform import aws_internet_gateway.igw igw-0123456789abcdef0
terraform import aws_subnet.public subnet-0123456789abcdef0
# ... and so on
```

## Step 5: Verify Import

After importing, verify that Terraform recognizes the resources:

```bash
terraform plan
```

You should see:
- ✅ No changes needed for VPC resources (they're already correct)
- ⚠️  Changes for your personal resources (EC2 instance will be created)

If you see changes to VPC resources, double-check:
1. Your `terraform.tfvars` matches the existing VPC settings
2. The VPC CIDR blocks match
3. All resource IDs are correct

## Step 6: Create Your Personal Resources

Now you can create your own EC2 instance:

```bash
terraform apply
```

This will create:
- Your EC2 instance with the name `your-name-test-host`
- Using the shared VPC and subnets
- Using the shared security group

## Alternative: Use Remote State (Recommended for Teams)

Instead of importing, you can use Terraform's remote state data source. This is better for teams.

### Option A: Using Data Sources (Recommended)

Create a new file `vpc-data.tf` to replace the VPC resources:

```hcl
# ============================================
# Shared VPC Resources (Read-Only)
# ============================================

# Look up existing VPC
data "aws_vpc" "shared" {
  filter {
    name   = "tag:Name"
    values = ["shared-test-vpc"]
  }
}

# Look up existing subnets
data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.shared.id]
  }
  
  filter {
    name   = "tag:Name"
    values = ["shared-test-public-subnet-*"]
  }
}

# Look up existing security group
data "aws_security_group" "ec2" {
  filter {
    name   = "tag:Name"
    values = ["shared-test-ec2-sg"]
  }
  
  vpc_id = data.aws_vpc.shared.id
}

# Create local values for easy reference
locals {
  vpc_id = data.aws_vpc.shared.id
  public_subnet_ids = data.aws_subnets.public.ids
  security_group_id = data.aws_security_group.ec2.id
}
```

Then update `ec2.tf` to use these data sources:

```hcl
resource "aws_instance" "host" {
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = var.ec2_instance_type

  subnet_id                   = local.public_subnet_ids[0]
  vpc_security_group_ids      = [local.security_group_id]
  associate_public_ip_address = true

  key_name = var.ec2_key_name

  tags = merge(
    local.project_common_tags,
    {
      Name = "${local.project_name_prefix}-host"
    }
  )
}
```

And **delete or comment out** the VPC resource definitions in `vpc.tf`.

## Important Notes

### For Shared VPC Owner:
- ✅ Manages all VPC resources
- ✅ Can import existing resources
- ⚠️  Be careful with `terraform destroy` - it affects everyone!

### For Other Users:
- ✅ Use data sources to reference shared VPC
- ✅ Create only your personal resources (EC2, etc.)
- ❌ Don't import VPC resources unless necessary
- ❌ Never run `terraform destroy` on imported VPC resources

## Troubleshooting

### Issue: "Resource already exists"
**Solution**: The resource is already imported. Check with `terraform state list`

### Issue: "No changes" but resources not visible
**Solution**: Verify your `terraform.tfvars` values match the existing infrastructure

### Issue: Import command fails
**Solution**: 
1. Verify the resource ID is correct
2. Check you have proper AWS permissions
3. Ensure you're in the correct AWS region

### Issue: Plan shows changes after import
**Solution**: Your Terraform configuration doesn't match the actual resource. Update your `.tf` files to match.

## Useful Commands

```bash
# List all imported resources
terraform state list

# Show details of a specific resource
terraform state show aws_vpc.main

# Remove a resource from state (without deleting it)
terraform state rm aws_vpc.main

# View current outputs
terraform output
```

## Team Workflow Recommendation

**Best Practice**: Use a separate repository or workspace for each user:

1. **Shared VPC Repository**: Managed by infrastructure team
   - Contains: VPC, Subnets, IGW, Route Tables, Shared Security Groups
   - Outputs: VPC ID, Subnet IDs, Security Group IDs

2. **Personal Resources Repository**: For each developer
   - Uses data sources to reference shared VPC
   - Contains: Personal EC2 instances, Lambda functions, etc.
   - No VPC management

This prevents accidental changes to shared infrastructure!

## Questions?

- Check if resource names match the expected pattern
- Verify CIDR blocks match the existing VPC
- Ensure your AWS credentials have proper permissions
- Review Terraform state: `terraform state list`

