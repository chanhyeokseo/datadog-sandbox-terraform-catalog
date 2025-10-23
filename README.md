# Datadog Sandbox Terraform Caralog for AWS Infrastructure

This Terraform configuration manages AWS infrastructure including VPC, subnets, security groups, and EC2 instances.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [For New Users: Importing Shared VPC](#for-new-users-importing-shared-vpc)
- [AWS Credentials Setup](#aws-credentials-setup)

## Prerequisites

- Terraform
- AWS Account
- AWS CLI configured

## Quick Start

### First Time Setup (VPC Owner)

```bash
# 1. Configure AWS credentials
aws configure

# 2. Copy and edit variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

# 3. Initialize and apply
terraform init
terraform plan
terraform apply
```

### For New Users: Importing Shared VPC

**Quick Import (Automated):**
```bash
# 1. Copy and edit variables
cp terraform.tfvars.example terraform.tfvars

# 2. Make script executable
chmod +x scripts/import-vpc.sh

# 3. Run import script
./scripts/import-vpc.sh
```

## AWS Credentials Setup

This project uses AWS credentials through one of the following methods (in order of precedence):

### Option 1: Environment Variables (Recommended for local development)

```bash
export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export AWS_DEFAULT_REGION="ap-northeast-2"
```

### Option 2: AWS CLI Credentials File

Configure AWS CLI:
```bash
aws configure
```

This creates `~/.aws/credentials` with your credentials.

### Option 3: AWS Profile

If you use multiple AWS accounts, use named profiles:

```bash
aws configure --profile your-profile-name
```

Then specify the profile:
```bash
export AWS_PROFILE=your-profile-name
terraform plan
```