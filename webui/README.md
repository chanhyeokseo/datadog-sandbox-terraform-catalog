# Terraform WebUI

Docker-based web interface for managing Terraform infrastructure with S3 backend and Parameter Store integration.

## ✨ Features

- 🚀 **No git clone needed** - Run directly from Docker image
- 🔐 **Secure key management** - SSH keys in AWS Parameter Store
- 💾 **S3 backend** - State files with versioning & locking
- 🔄 **Parallel operations** - Independent state locks per resource
- 🎨 **Modern UI** - React-based interface

## 🚀 Quick Start

### 1. Setup AWS Credentials (Required)

**⚠️ IMPORTANT**: AWS credentials **must** be set via environment variables. The container loads configuration from AWS Parameter Store on startup, which requires credentials to be available before the application starts.

```bash
# Copy example env file
cp .env.example .env

# Edit and set AWS credentials
nano .env
```

`.env` file:
```bash
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_REGION=ap-northeast-2
```

### 2. Run with Docker Compose

```bash
# Start services
docker-compose up -d --build

# Check logs
docker-compose logs -f
```

### 3. Access WebUI

Open browser: **http://localhost:3000**

### 4. Complete Onboarding

1. **Project Info** - Enter project name, environment, region
2. **SSH Key** - Auto-generate EC2 key pair
3. **VPC/Subnets** - Select from AWS
4. **Datadog** - (Optional) Enter Datadog API key
5. **Complete** - Auto-setup S3 backend & save to Parameter Store!

## 🏗️ Architecture

```
┌─────────────┐
│   WebUI     │  (No volumes needed!)
│  Container  │
└──────┬──────┘
       │
       ├─────────────────────────┐
       │                         │
       ▼                         ▼
┌─────────────────┐    ┌───────────────────┐
│  S3 Bucket      │    │ Parameter Store   │
│  - State Files  │    │  - SSH Keys       │
│  - Versioned    │    │  - Encrypted      │
└─────────────────┘    └───────────────────┘
       │
       ▼
┌─────────────────┐
│  DynamoDB       │
│  - State Locks  │
└─────────────────┘
```

## 🎯 What Gets Auto-Created

On first onboarding:

✅ **S3 Bucket** - `{project_name}-tf-states-{timestamp}`
- Versioning enabled
- AES256 encryption
- Public access blocked

✅ **DynamoDB Table** - `terraform-state-locks`
- Pay-per-request billing
- Distributed state locking

✅ **Parameter Store Keys** - `/ec2/keypairs/{key_name}`
- KMS encrypted
- Version controlled

## 📦 Services

### Backend (FastAPI)
- **Port**: 8000
- **API Docs**: http://localhost:8000/docs

### Frontend (React)
- **Port**: 3000
- **UI**: http://localhost:3000

## 🛠️ Development

### Local Development (without Docker)

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## 🔐 Security

- ✅ AWS credentials via environment variables
- ✅ SSH keys encrypted in Parameter Store
- ✅ State files encrypted in S3
- ✅ DynamoDB lock prevents concurrent modifications
- ✅ No secrets in git repository

## 💰 Cost Estimation

**Monthly cost: ~$0.05 - $0.10**

| Service | Cost |
|---------|------|
| S3 (< 1GB) | $0.02 |
| DynamoDB (pay-per-request) | $0.01 |
| Parameter Store (Standard < 4KB) | Free |

## 🧹 Cleanup

```bash
# Stop services
docker-compose down

# Remove volumes (if any)
docker-compose down -v

# Remove AWS resources (manual)
# - Delete S3 bucket
# - Delete DynamoDB table
# - Delete Parameter Store keys
```

## 🆘 Troubleshooting

### Backend can't connect to AWS
```bash
# Check credentials
docker-compose exec backend env | grep AWS

# Test AWS connection
docker-compose exec backend aws sts get-caller-identity
```

### Frontend can't reach backend
```bash
# Check backend logs
docker-compose logs backend

# Verify backend is running
curl http://localhost:8000/health
```

### State lock error
```
Error: Error acquiring the state lock
```
Someone else is modifying the same resource. Wait or:
```bash
# Inside the resource directory (advanced)
terraform force-unlock <LOCK_ID>
```

## 📚 Documentation

- [S3 Backend Migration Guide](../docs/S3_BACKEND_MIGRATION.md)
- [Backend Setup Quick Start](../docs/BACKEND_SETUP.md)

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Test with docker-compose
5. Submit pull request

## 📝 License

[Your License Here]

## 🙏 Credits

Built with Claude Sonnet 4.5
