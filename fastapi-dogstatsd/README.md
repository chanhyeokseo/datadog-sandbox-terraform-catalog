# FastAPI with DogStatsD for ECS Fargate

This application runs alongside the Datadog agent in the same ECS Task and sends custom metrics via DogStatsD.

## Files
- `dogstatsd.py` - FastAPI application with DogStatsD metrics
- `Dockerfile` - Container image definition

## Setup Instructions

### 1. Create ECR Repository
```bash
aws ecr create-repository \
  --repository-name fastapi-dogstatsd \
  --region ap-northeast-2
```

### 2. Build and Push Docker Image


**Easy way (recommended):**
```bash
cd fastapi-dogstatsd
./build-and-push.sh
```

### 3. Deploy with Terraform

```bash
terraform apply
```
Then test the endpoints:

```bash

# Health check
curl http://<PUBLIC_IP>:8000/

# Send test metric
curl -X POST http://<PUBLIC_IP>:8000/test_increment_metric
```