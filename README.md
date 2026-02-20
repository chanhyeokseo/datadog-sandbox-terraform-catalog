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
> Terraform is pre-installed inside the backend container — no local installation needed.
>
> The container mounts `~/.aws` from your host (read-only), so any credentials configured via AWS CLI — including SSO, profiles, and temporary credentials — work automatically.

## Quick Start

### 1. Download configuration files

Download these two files into the same directory:

- [`docker-compose.yml`](docker-compose.yml)
- [`.env.example`](.env.example)

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set your AWS profile and region:

```env
AWS_PROFILE=my-sso-profile
AWS_REGION=ap-northeast-2
```

> [!TIP]
> If your profile uses AWS SSO, make sure to log in before starting the services:
> ```bash
> aws sso login --profile my-sso-profile
> ```

<details>
<summary>Alternative: explicit credentials (not recommended)</summary>

```env
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
```

</details>

### 3. Start services

```bash
docker compose up -d
```

### 4. Open the UI

```
http://localhost:3000
```

<div align="center">

---

Backend API docs available at `http://localhost:8000/docs`

</div>
