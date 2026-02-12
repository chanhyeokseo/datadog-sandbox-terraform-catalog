# Backend Setup Quick Start

## TL;DR

1. **Start WebUI**: `cd webui && ./run.sh`
2. **Navigate to**: http://localhost:3000/settings/backend
3. **Click**: "Setup Backend Infrastructure"
4. **Enter**: Unique S3 bucket name
5. **Done!** WebUI handles everything automatically

## What Gets Created

- **S3 Bucket**: Stores Terraform state files (versioned & encrypted)
- **DynamoDB Table**: Provides state locking for parallel operations
- **backend.tf files**: Auto-generated for each instance

## Why This Matters

### Before (Local State)
- ❌ 15GB repository to clone
- ❌ No team collaboration (race conditions)
- ❌ No state backup/versioning
- ❌ PEM keys in repository

### After (S3 Backend + Parameter Store)
- ✅ Lightweight WebUI (< 2MB)
- ✅ Team-friendly with locking
- ✅ Automatic state backups
- ✅ Encrypted key storage

## Environment Variables

```bash
# Enable/disable Parameter Store for keys
export USE_PARAMETER_STORE=true  # default

# Terraform working directory
export TERRAFORM_DIR=/path/to/terraform  # default: /terraform
```

## Parallel Operations Verified

Each instance gets its own state file and lock:

```
Instance              S3 Key                                      DynamoDB Lock
---------------------------------------------------------------------------
ec2-basic           instances/ec2-basic/terraform.tfstate       Lock-ABC-123
eks-cluster         instances/eks-cluster/terraform.tfstate     Lock-DEF-456
rds-postgres        instances/rds-postgres/terraform.tfstate    Lock-GHI-789
```

**Result**: All 3 can `terraform apply` simultaneously! 🚀

## API Endpoints

### Backend Management

```bash
GET  /api/backend/status          # Check backend configuration status
POST /api/backend/setup           # Create S3 + DynamoDB infrastructure
POST /api/backend/check           # Verify infrastructure exists
POST /api/backend/generate/{id}   # Generate backend.tf for instance
```

### SSH Key Management

```bash
GET    /api/keys/list              # List all keys
POST   /api/keys/upload            # Upload key (JSON)
POST   /api/keys/upload-file       # Upload key (file)
GET    /api/keys/{name}            # Get key metadata
DELETE /api/keys/{name}            # Delete key
GET    /api/keys/storage/info      # Storage backend info
```

## Cost

~$0.05 - $0.10 per month total:
- S3: $0.02 (< 1GB storage)
- DynamoDB: $0.01 (pay-per-request)
- Parameter Store: Free (Standard tier < 4KB)

## Security

- **S3**: Server-side encryption (AES256)
- **DynamoDB**: Encrypted at rest
- **Parameter Store**: KMS encryption (SecureString)
- **Access**: IAM role-based

## Next Steps

See [S3_BACKEND_MIGRATION.md](./S3_BACKEND_MIGRATION.md) for detailed migration guide.
