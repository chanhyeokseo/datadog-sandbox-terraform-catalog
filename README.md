<div align="center">

<img src="webui/frontend/public/logo.png" alt="DogSTAC" width="240" />

# DogSTAC

**Datadog Sandbox with Terraform AWS Catalog**

Terraform infrastructure management through a visual web interface.

---

</div>

## Prerequisites

| Requirement | Description |
|:-----------:|-------------|
| **Docker** | Container runtime & Docker Compose |
| **Git** | Used internally to clone instance templates |
| **AWS CLI** | Configured with SSO or credentials (`~/.aws`) |

> [!NOTE]
> The container mounts `~/.aws` from your host, so any credentials configured via AWS CLI — including SSO, profiles, and temporary credentials — work automatically.


If you are trying to use SSO but haven't configured an AWS SSO profile yet:
```bash
aws configure sso
```
Follow the prompts to set SSO start URL, region, account, role, and profile name. Use the profile name when configuring `.env` file.

## Quick Start

### 1. Download configuration files

```bash
mkdir dogstac && cd dogstac
curl -O https://raw.githubusercontent.com/chanhyeokseo/datadog-sandbox-terraform-catalog/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/chanhyeokseo/datadog-sandbox-terraform-catalog/main/.env.example
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set the required values:

```env
# AWS authentication (choose one)
AWS_PROFILE=my-sso-profile

# Identity salt — unique per user, used for naming AWS resources (S3, DynamoDB, Parameter Store)
# Once set, do not change it.
DOGSTAC_SALT=my-unique-salt
```

<details>
<summary>Alternative: explicit credentials (not recommended)</summary>

```env
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
```
</details>

> [!IMPORTANT]
> `DOGSTAC_SALT` is **required**. It must be unique per user and remain unchanged after initial setup. Changing it will disconnect you from previously created backend resources.

### 3. Start services

```bash
docker compose up -d
```

### 4. Open the UI

```
http://localhost:3000
```

## Environment Variables

| Variable | Required | Description |
|----------|:--------:|-------------|
| `AWS_PROFILE` | * | AWS CLI profile name (SSO or static credentials) |
| `AWS_ACCESS_KEY_ID` | * | Explicit access key (alternative to profile) |
| `AWS_SECRET_ACCESS_KEY` | * | Explicit secret key (alternative to profile) |
| `AWS_SESSION_TOKEN` | | For temporary credentials |
| `DOGSTAC_SALT` | **Yes** | Stable identifier for naming backend resources. Must be unique per user. |
| `TERRAFORM_DATA_PATH` | | Persistent storage path (default: `./terraform-data`) |

\* One of `AWS_PROFILE` or `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` is required.

<div align="center">

---

Backend API docs available at `http://localhost:8000/docs`

</div>
