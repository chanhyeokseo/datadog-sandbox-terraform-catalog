# S3 Backend + Parameter Store Migration Guide

This guide explains how to migrate from local state files and local PEM keys to AWS-managed infrastructure.

## Overview

**Before**:
- ❌ Terraform state files stored locally (`instances/*/terraform.tfstate`)
- ❌ PEM keys stored in `keys/` directory
- ❌ Must clone entire repository (15GB+)
- ❌ No state locking for team collaboration

**After**:
- ✅ Terraform state files in S3 with versioning
- ✅ PEM keys encrypted in AWS Parameter Store
- ✅ DynamoDB-based state locking (parallel operations supported!)
- ✅ WebUI can run without full repository clone
- ✅ Team-friendly with proper access controls

## Architecture

```
┌─────────────┐
│   WebUI     │
└──────┬──────┘
       │
       ├─────────────────────────┐
       │                         │
       ▼                         ▼
┌─────────────────┐    ┌───────────────────┐
│  S3 Bucket      │    │ Parameter Store   │
│  - State Files  │    │  - SSH Keys       │
│  - Versioned    │    │  - Encrypted      │
│  - Encrypted    │    │  /ec2/keypairs/*  │
└─────────────────┘    └───────────────────┘
       │
       ▼
┌─────────────────┐
│  DynamoDB       │
│  - State Locks  │
│  - Per Instance │
└─────────────────┘
```

## Prerequisites

- AWS CLI configured
- AWS credentials with permissions for:
  - S3 (CreateBucket, PutObject, GetObject)
  - DynamoDB (CreateTable, PutItem, GetItem)
  - SSM Parameter Store (PutParameter, GetParameter)

## Migration Steps

### Step 1: Setup Backend Infrastructure via WebUI

1. **Access WebUI**
   ```bash
   cd webui
   ./run.sh  # or docker-compose up
   ```

2. **Navigate to Onboarding**
   - Open http://localhost:3000
   - Go to **Settings** → **Backend Configuration**

3. **Create Backend Infrastructure**
   - Enter a **globally unique** S3 bucket name
     - Example: `mycompany-terraform-states-20260213`
   - Select region: `ap-northeast-2` (or your preferred region)
   - Click **"Setup Backend"**

4. **WebUI will automatically**:
   - ✅ Create S3 bucket with encryption & versioning
   - ✅ Create DynamoDB table for state locking
   - ✅ Generate `backend.tf` for all instances
   - ✅ Verify configuration

### Step 2: Migrate State Files

The WebUI will guide you through migrating each instance:

1. **Select instances to migrate**
   - View list of instances with/without backend configured
   - Select instances to migrate (or "Migrate All")

2. **WebUI executes for each instance**:
   ```bash
   cd instances/<instance-name>
   terraform init -migrate-state
   ```

3. **Local state files backed up**
   - Original: `terraform.tfstate.backup-YYYYMMDD-HHMMSS`
   - Safe to delete after verification

4. **Verify migration**
   ```bash
   # Check S3
   aws s3 ls s3://your-bucket-name/instances/

   # Test terraform commands
   cd instances/ec2-basic
   terraform plan  # Should work with remote state
   ```

### Step 3: Upload SSH Keys to Parameter Store

**Option A: Via WebUI (Recommended)**

1. Go to **Settings** → **SSH Keys**
2. Click **"Upload Key"**
3. Select your `.pem` file
4. Enter key name (e.g., "chanhyeok")
5. Click **Upload**

**Option B: Via AWS CLI**

```bash
# Upload existing PEM key
aws ssm put-parameter \
  --name /ec2/keypairs/chanhyeok \
  --value file://keys/chanhyeok.pem \
  --type SecureString \
  --description "EC2 SSH private key"

# Verify
aws ssm get-parameter \
  --name /ec2/keypairs/chanhyeok \
  --with-decryption \
  --query 'Parameter.Version'
```

**Option C: Bulk Upload Script**

```bash
# Upload all keys from keys/ directory
for pem_file in keys/*.pem; do
  key_name=$(basename "$pem_file" .pem)
  aws ssm put-parameter \
    --name "/ec2/keypairs/$key_name" \
    --value "file://$pem_file" \
    --type SecureString \
    --overwrite
  echo "✅ Uploaded $key_name"
done
```

### Step 4: Test SSH Connections

1. **WebUI Terminal**
   - Navigate to an EC2 instance
   - Click **"Connect via SSH"**
   - WebUI will automatically use Parameter Store keys

2. **Manual Test**
   ```bash
   # Get key from Parameter Store
   aws ssm get-parameter \
     --name /ec2/keypairs/chanhyeok \
     --with-decryption \
     --query 'Parameter.Value' \
     --output text > /tmp/test-key.pem

   chmod 600 /tmp/test-key.pem
   ssh -i /tmp/test-key.pem ec2-user@<instance-ip>
   ```

### Step 5: Cleanup Local Files

After verifying everything works:

```bash
# Remove local state files (backed up in S3)
find instances -name "terraform.tfstate*" -type f

# Optional: Remove local keys (stored in Parameter Store)
# ⚠️ Only if you're sure they're safely uploaded!
# rm -rf keys/*.pem

# Update .gitignore
echo "*.tfstate*" >> .gitignore
echo "keys/*.pem" >> .gitignore
```

## Parallel Operations

Each instance has an **independent state file and lock**:

```python
# Example: Deploy 3 instances in parallel via WebUI
instances = ["ec2-basic", "eks-cluster", "rds-postgres"]

# Each gets its own lock:
# - LockID: bucket/instances/ec2-basic/terraform.tfstate-md5
# - LockID: bucket/instances/eks-cluster/terraform.tfstate-md5
# - LockID: bucket/instances/rds-postgres/terraform.tfstate-md5

# ✅ All can run simultaneously without blocking!
```

## Cost Estimation

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| **S3** | < 1GB state files | $0.02 |
| **S3 Requests** | ~1000 GET/PUT | $0.01 |
| **DynamoDB** | Pay-per-request | $0.01 |
| **Parameter Store** | Standard tier (< 4KB) | **Free** |
| **Parameter Store** | Advanced tier (> 4KB) | $0.05 per parameter |
| **TOTAL** | | **$0.05 - $0.10/month** |

## Security

### IAM Policy for WebUI

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/terraform-state-locks"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:PutParameter",
        "ssm:DescribeParameters"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/ec2/keypairs/*"
    }
  ]
}
```

## Rollback

If you need to rollback to local state:

```bash
cd instances/<instance-name>

# Pull state from S3
terraform state pull > terraform.tfstate

# Remove backend configuration
rm backend.tf

# Re-initialize with local backend
terraform init -migrate-state
```

## Troubleshooting

### Issue: "Error acquiring state lock"

```
Error: Error acquiring the state lock
Lock Info:
  ID:        xxx
  Path:      bucket/instances/ec2-basic/terraform.tfstate
  Operation: OperationTypeApply
```

**Solution**: Someone else is modifying this instance. Wait or:

```bash
# Force unlock (use carefully!)
terraform force-unlock <LOCK_ID>
```

### Issue: "Key not found in Parameter Store"

**Solution**: Upload the key:

```bash
# Via WebUI: Settings → SSH Keys → Upload
# Or via CLI:
aws ssm put-parameter \
  --name /ec2/keypairs/your-key-name \
  --value file://path/to/key.pem \
  --type SecureString
```

### Issue: "Parameter Store tier limit exceeded"

If your PEM key is > 4KB:

```bash
# Use Advanced tier (costs $0.05/month per parameter)
aws ssm put-parameter \
  --name /ec2/keypairs/large-key \
  --value file://large-key.pem \
  --type SecureString \
  --tier Advanced
```

## API Documentation

### Backend Setup

```bash
# Check backend status
curl http://localhost:8000/api/backend/status

# Setup backend infrastructure
curl -X POST http://localhost:8000/api/backend/setup \
  -H "Content-Type: application/json" \
  -d '{
    "bucket_name": "my-terraform-states",
    "region": "ap-northeast-2"
  }'
```

### Key Management

```bash
# List keys
curl http://localhost:8000/api/keys/list

# Upload key
curl -X POST http://localhost:8000/api/keys/upload \
  -H "Content-Type: application/json" \
  -d '{
    "key_name": "mykey",
    "private_key_content": "-----BEGIN RSA PRIVATE KEY-----\n...",
    "description": "My SSH key"
  }'

# Delete key
curl -X DELETE http://localhost:8000/api/keys/mykey
```

## Next Steps

1. ✅ Backend infrastructure created
2. ✅ State files migrated to S3
3. ✅ SSH keys in Parameter Store
4. ✅ Test parallel operations
5. 📝 Document your bucket name for team
6. 🔒 Set up IAM roles for team members
7. 🗑️ Clean up local state/key files

## References

- [Terraform S3 Backend](https://www.terraform.io/language/settings/backends/s3)
- [AWS Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- [DynamoDB State Locking](https://www.terraform.io/language/settings/backends/s3#dynamodb-state-locking)
