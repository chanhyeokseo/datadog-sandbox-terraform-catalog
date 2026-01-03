# DogSTAC: Datadog Sandbox with Terraform AWS Catalog


## Prerequisites

- Terraform
- AWS Account & AWS CLI configured
- Docker (only required when building container images)

## Install Terraform

### macOS (Homebrew)

```bash
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

### Linux (Ubuntu/Debian)

```bash
sudo apt-get update && sudo apt-get install -y gnupg software-properties-common

wget -O- https://apt.releases.hashicorp.com/gpg | \
  gpg --dearmor | \
  sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg > /dev/null

echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
  https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
  sudo tee /etc/apt/sources.list.d/hashicorp.list

sudo apt update && sudo apt install terraform
```

### Windows (Chocolatey)

```powershell
choco install terraform
```

### Verify Installation

```bash
terraform -version
```

## AWS Credentials Setup

This project uses AWS credentials through one of the following methods:

### Option 1: Environment Variables

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
