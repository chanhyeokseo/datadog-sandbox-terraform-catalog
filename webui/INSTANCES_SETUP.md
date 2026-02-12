# Instances Repository Setup Guide

## Overview

The WebUI now loads Terraform instance templates from a separate Git repository instead of bundling them in the Docker image. This approach:

✅ Keeps Docker image small and fast to build
✅ Allows dynamic updates to instances without rebuilding
✅ Enables version control for instance templates
✅ Works with S3 backend architecture

## Setup Steps

### 1. Create Instances Repository

Create a new Git repository with your Terraform instances:

```bash
# Create new repo
mkdir terraform-instances
cd terraform-instances
git init

# Copy instances from Catalog
cp -r /path/to/Catalog/instances/* .

# Clean up .terraform directories (not needed in repo)
find . -name ".terraform" -type d -exec rm -rf {} +
find . -name "*.tfstate*" -exec rm -f {} +
find . -name ".terraform.lock.hcl" -exec rm -f {} +

# Commit
git add .
git commit -m "Initial commit: Terraform instances"

# Push to GitHub (or any Git hosting)
git remote add origin https://github.com/yourusername/terraform-instances.git
git push -u origin main
```

### 2. Update Environment Variables

Edit `.env` file:

```bash
# Add your instances repository URL
INSTANCES_REPO_URL=https://github.com/yourusername/terraform-instances.git

# AWS credentials (required)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=ap-northeast-2
```

### 3. Start the WebUI

```bash
cd webui

# First time or rebuild
docker-compose -f docker-compose.build.yml up -d --build

# Subsequent starts (uses existing image)
docker-compose up -d
```

## How It Works

1. **Container Startup**:
   - Entrypoint script checks for `INSTANCES_REPO_URL`
   - Clones the repository to `/tmp/instances-repo`
   - Copies instances to `/app/terraform/instances/`
   - Cleans up temporary files

2. **Onboarding Flow**:
   - First run → Onboarding page appears
   - Complete onboarding → Config saved to Parameter Store
   - Restart with same AWS credentials → Auto-redirects to main page

3. **Configuration Persistence**:
   - Variables saved to AWS Parameter Store: `/dogstac-{creator}-{team}/config/variables`
   - S3 backend created: `dogstac-{creator}-{team}-tf-states-{timestamp}`
   - DynamoDB table for state locking: `terraform-state-locks`

## Directory Structure

```
terraform-instances/          # Your Git repository
├── ec2-basic/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── eks-cluster/
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
└── ...
```

**Note**: Do NOT commit `.terraform/` directories or `*.tfstate` files to your instances repository.

## Updating Instances

To add or update instances:

```bash
# In your instances repository
git pull
# Make changes...
git add .
git commit -m "Add new EC2 instance template"
git push

# Restart WebUI to pull latest
docker-compose restart backend
```

## Troubleshooting

### Instances not appearing

Check backend logs:
```bash
docker-compose logs backend | grep "instances"
```

Should see:
```
📦 Cloning instances from: https://github.com/...
✅ Successfully cloned instances repository
✅ Instances ready: 15 directories
```

### Git clone fails

- Verify `INSTANCES_REPO_URL` is correct
- For private repos, use SSH or personal access token
- Check repository is accessible

### Onboarding appears on every restart

- AWS credentials must be set in `.env` file
- Parameter Store must contain configuration
- Check API: `curl http://localhost:8000/api/backend/onboarding/status`

## Private Repository Access

For private repositories:

**Option 1: SSH Key (Recommended)**

```bash
# Generate SSH key in container or mount host key
INSTANCES_REPO_URL=git@github.com:yourusername/terraform-instances.git
```

**Option 2: Personal Access Token**

```bash
# GitHub PAT
INSTANCES_REPO_URL=https://YOUR_TOKEN@github.com/yourusername/terraform-instances.git
```

## Security Notes

- 🔐 Never commit AWS credentials to Git
- 🔐 Never commit `.tfstate` files with sensitive data
- 🔐 Use `.gitignore` in instances repository:
  ```
  .terraform/
  *.tfstate
  *.tfstate.backup
  .terraform.lock.hcl
  *.tfvars
  ```

## Benefits of This Approach

1. **Fast Builds**: Docker image is ~500MB instead of 8GB
2. **Dynamic Updates**: Change instances without rebuilding image
3. **Team Collaboration**: Share instance templates via Git
4. **Version Control**: Track changes to Terraform configurations
5. **Multiple Environments**: Use different repos for dev/prod

## Next Steps

Once instances are set up, the WebUI will:

1. Auto-create S3 backend during onboarding
2. Generate `backend.tf` for each instance
3. Support Terraform operations (plan/apply/destroy)
4. Persist configuration across container restarts
