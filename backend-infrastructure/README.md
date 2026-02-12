# Backend Infrastructure Setup

This directory contains Terraform configuration to create the infrastructure needed for remote state management:
- **S3 Bucket**: Stores Terraform state files
- **DynamoDB Table**: Provides state locking to prevent concurrent modifications

## ✅ Parallel Operations Guaranteed

Each instance uses a **unique S3 key** and gets a **separate DynamoDB lock**:

```
Instance: ec2-basic     → Lock: bucket/instances/ec2-basic/terraform.tfstate-md5
Instance: eks-cluster   → Lock: bucket/instances/eks-cluster/terraform.tfstate-md5
Instance: rds-postgres  → Lock: bucket/instances/rds-postgres/terraform.tfstate-md5
```

**Different locks = No interference = Full parallelism** 🚀

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.0
- Permissions to create S3 buckets and DynamoDB tables

## Setup Instructions

### 1. Configure Variables

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and set your values:
- `state_bucket_name`: Must be globally unique (e.g., `mycompany-terraform-states-20240213`)
- `region`: AWS region where backend resources will be created

### 2. Initialize and Apply

```bash
cd backend-infrastructure

# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Create the backend infrastructure
terraform apply
```

### 3. Save the Outputs

```bash
terraform output -json > backend-config.json
```

## What Gets Created

### S3 Bucket
- **Versioning**: Enabled (keeps history of state changes)
- **Encryption**: AES256 server-side encryption
- **Public Access**: Blocked
- **Lifecycle**: Old versions deleted after 90 days

### DynamoDB Table
- **Billing**: Pay-per-request (no upfront costs)
- **Key**: LockID (String)
- **Purpose**: Prevents concurrent state modifications per resource

## Cost Estimation

**Total estimated cost: ~$0.05 - $0.10 per month**

- S3 Storage: ~$0.02/month (< 1GB)
- DynamoDB: ~$0.01/month (< 1000 requests)

## Next Steps

After creating the backend infrastructure:
1. Update instance `backend.tf` files with the bucket name
2. Run `terraform init -migrate-state` in each instance directory
3. Verify state migration was successful
4. Delete local `terraform.tfstate` files
