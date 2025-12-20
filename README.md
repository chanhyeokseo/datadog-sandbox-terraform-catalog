# DogSTAC: Datadog Sandbox with Terraform AWS Catalog

## Table of Contents

- [Prerequisites](#prerequisites)
- [For New Users: Importing Shared VPC](#for-new-users-importing-shared-vpc)
- [AWS Credentials Setup](#aws-credentials-setup)

## Prerequisites

- Terraform
- AWS Account
- AWS CLI configured
- Docker (only required when building container images)

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
