# APM Sandbox Apps

Sample applications for APM testing with Datadog tracing.

## 3-Step Deployment

### Step 1: Modify Source Code

Customize application code in `apps/<app>/` directory as you want.

### Step 2: Build with Terraform

> ⚠️ **Docker must be running** before terraform apply.

1. Uncomment ECR module in `ecr.tf`
2. Uncomment desired app in `apps.tf`
3. Apply

```bash
terraform apply
```

### Step 3: Deploy to EKS

See `eks/apps/<app>/README.md` for deployment instructions.

## Available Apps

| App | Source | EKS Manifest | Description |
|-----|--------|--------------|-------------|
| Spring Boot 3.5.8 | `apps/spring-boot-3.5.8` | `eks/apps/spring-boot-3.5.8` | Java APM with custom spans, errors, latency |