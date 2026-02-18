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
| **AWS Credentials** | `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` |

> [!NOTE]
> Terraform is pre-installed inside the backend container — no local installation needed.

## Quick Start

### 1. Download configuration files

Download these two files into the same directory:

- [`docker-compose.yml`](docker-compose.yml)
- [`.env.example`](.env.example)

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in the required values:

```env
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_REGION=ap-northeast-2

INSTANCES_REPO_URL=https://github.com/your-org/your-repo.git
```

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
