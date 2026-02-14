# DogSTAC - Terraform Web UI

## Project Summary

DogSTAC is a web-based Terraform infrastructure management tool. It provides a visual interface to discover, configure, and provision Terraform resources per-instance. Each Terraform instance (e.g., `ec2-basic`, `eks-cluster`) lives in its own directory with independent state, variables, and backend configuration. The application consists of a FastAPI backend and React frontend, orchestrated via Docker Compose.

## Tech Stack

- **Backend**: Python 3.11, FastAPI, Uvicorn, Pydantic, boto3, paramiko, python-hcl2
- **Frontend**: React 18, TypeScript, Vite 5, React Router 6, Axios, xterm.js
- **Infrastructure**: Docker Compose, Terraform 1.7.0, nginx:alpine
- **AWS Services**: S3 (state + config), DynamoDB (state lock), Parameter Store (config), EC2 API (VPC/subnet/key discovery)

## Project Structure

```
webui/
├── AGENTS.md
├── README.md
├── INSTANCES_SETUP.md
├── .env.example
├── .gitignore
├── setup.sh                           # Persistent storage setup script
├── docker-compose.yml                 # End-user: pre-built backend image
├── docker-compose.build.yml           # Developer: build images locally
│
├── backend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── requirements.txt
│   ├── entrypoint.sh                  # Git sparse checkout + config init
│   └── app/
│       ├── main.py                    # FastAPI entry point, router mounts
│       ├── init_config.py             # Startup config sync (S3 → Parameter Store → local)
│       ├── config/
│       │   ├── resource_config.py     # Resource variables, onboarding phases, common vars
│       │   └── README.md
│       ├── models/
│       │   └── schemas.py             # Pydantic models (Resource, Variable, enums)
│       ├── routes/
│       │   ├── terraform.py           # Terraform + resource + onboarding endpoints
│       │   ├── backend.py             # S3/DynamoDB backend setup endpoints
│       │   ├── ssh.py                 # SSH WebSocket terminal
│       │   └── keys.py               # SSH key management (upload/list/delete)
│       └── services/
│           ├── terraform_parser.py    # Parse instances, manage variables, sync config
│           ├── terraform_runner.py    # Async Terraform CLI execution (plan/apply/destroy)
│           ├── instance_discovery.py  # Map instance dirs → resource IDs and types
│           ├── config_manager.py      # AWS Parameter Store config persistence
│           ├── s3_config_manager.py   # S3-based tfvars sync (root + per-instance)
│           ├── backend_manager.py     # S3 bucket + DynamoDB table provisioning
│           └── key_manager.py         # SSH key storage (Parameter Store + local fallback)
│
├── frontend/
│   ├── Dockerfile                     # Multi-stage: node:18-alpine → nginx:alpine
│   ├── nginx.conf                     # SPA fallback + /api proxy to backend
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── index.html
│   └── src/
│       ├── main.tsx                   # React DOM root
│       ├── AppRouter.tsx              # Routes + OnboardingGuard
│       ├── App.tsx                    # Main layout: sidebar + action + results
│       ├── vite-env.d.ts
│       ├── types/
│       │   └── index.ts              # ResourceType, ResourceStatus, interfaces
│       ├── services/
│       │   └── api.ts                # terraformApi, backendApi, keysApi
│       ├── components/
│       │   ├── ResourceSidebar.tsx    # Resource list grouped by type
│       │   ├── ActionPanel.tsx        # Deploy/Plan/Destroy + variable editor
│       │   ├── ResultsPanel.tsx       # Execution results display
│       │   ├── OnboardingPage.tsx     # Multi-phase setup wizard
│       │   ├── OnboardingModal.tsx    # Security Group deployment guide
│       │   ├── ConfigModal.tsx        # Global variable editor
│       │   ├── ConnectionsModal.tsx   # SSH connection manager
│       │   ├── Terminal.tsx           # xterm.js SSH terminal via WebSocket
│       │   ├── EKSEditor.tsx          # EKS cluster configuration editor
│       │   ├── SecurityGroupEditor.tsx# Security Group rules editor
│       │   ├── DescriptionModal.tsx   # Resource DESCRIPTION.md viewer
│       │   ├── DebugModal.tsx         # Debug/maintenance panel per resource
│       │   ├── ConfirmModal.tsx       # Reusable confirm dialog
│       │   └── OutputModal.tsx        # Terraform output display
│       └── styles/
│           ├── App.css
│           ├── Unified.css            # CSS variables, glassmorphism, shared
│           ├── OnboardingPage.css
│           ├── OnboardingModal.css
│           ├── Terminal.css
│           ├── EKSEditor.css
│           ├── SecurityGroupEditor.css
│           ├── DescriptionModal.css
│           ├── DebugModal.css
│           └── ConfirmModal.css
│
└── terraform-data/                    # Persistent volume (gitignored)
    ├── instances/                     # Terraform instance directories
    │   ├── ec2-basic/
    │   ├── ec2-datadog-docker/
    │   ├── ec2-datadog-host/
    │   ├── ec2-windows-2016/
    │   ├── ec2-windows-2022/
    │   ├── ec2-windows-2025/
    │   ├── ec2-forwardog/
    │   ├── eks-cluster/
    │   ├── ecs-ec2/
    │   ├── ecs-fargate/
    │   ├── ecr-apps/
    │   ├── deploy-spring-boot/
    │   ├── lambda-python-example/
    │   ├── lambda-python-tracing-example/
    │   ├── dbm-autoconfig-postgres/
    │   ├── dbm-postgres-postgres/
    │   ├── security-group/
    │   └── test-file-*/
    └── apps/                          # Application source for deployments
        ├── spring-boot-3.5.8/
        └── lambda/python/
```

## Architecture

### Data Flow

```
User → Frontend (React SPA)
         ↓ HTTP/SSE
       Nginx (/api proxy)
         ↓
       Backend (FastAPI)
         ├── instance_discovery → scan terraform-data/instances/
         ├── terraform_parser   → read/write tfvars, parse resources
         ├── terraform_runner   → async terraform CLI per instance
         ├── config_manager     → Parameter Store persistence
         ├── s3_config_manager  → S3 tfvars sync
         ├── backend_manager    → S3 bucket + DynamoDB setup
         └── key_manager        → SSH key storage
         ↓
       terraform-data/ (Docker volume)
         ├── instances/{name}/  → main.tf, variables.tf, terraform.tfvars, backend.tf
         └── .terraform/        → provider plugins, state
```

### Instance Discovery

Each directory under `terraform-data/instances/` is an independent Terraform workspace.

1. Scan `instances/` for directories containing `main.tf`
2. Extract resource ID from `.resource_id` file or first `module` block name in `main.tf`
3. Infer resource type from directory name prefix (`ec2-*` → EC2, `eks-*` → EKS, etc.)
4. Build `resource_id → directory_name` mapping used by parser and runner

### Configuration Persistence

Config is persisted across container restarts via a 3-tier strategy:

1. **S3** (primary) - root and per-instance `terraform.tfvars` synced to S3 bucket
2. **Parameter Store** (secondary) - root config stored as JSON at `/dogstac-{hash}/{creator}-{team}/config/variables`
3. **Local tfvars** (fallback) - `terraform-data/instances/*/terraform.tfvars`

**Startup flow** (`entrypoint.sh` → `init_config.py`):
1. Git sparse checkout of `instances/` and `apps/` from `INSTANCES_REPO_URL`
2. Sync tfvars from S3 (root + all instances)
3. Fall back to Parameter Store if S3 fails
4. Start uvicorn

### Per-Instance Terraform Execution

Each instance runs Terraform independently:
- Working directory: `terraform-data/instances/{dir_name}/`
- Variable file: `-var-file=terraform.tfvars` (instance-specific)
- Backend: `backend.tf` with S3 state + DynamoDB lock (per-instance key)
- Streaming: SSE for plan/apply/destroy output, `__TF_EXIT__:{code}` sentinel at completion
- Concurrency: Per-resource locks prevent simultaneous apply/destroy on same instance

### Frontend Routing

```
AppRouter (BrowserRouter)
└── OnboardingGuard (checks /api/backend/onboarding/status)
    ├── /onboarding  → OnboardingPage (multi-phase wizard)
    ├── /            → App (main three-panel layout)
    └── /terminal/:connectionId → Terminal (SSH via WebSocket)
```

**OnboardingGuard** redirects: incomplete config → `/onboarding`, complete config on `/onboarding` → `/`.

### Frontend Component Hierarchy

```
App
├── Header (logo, Connections, Security Group, Config, theme toggle)
├── ResourceSidebar (grouped resource list, selection, running state)
├── ActionPanel
│   ├── Deploy/Update, Plan, Destroy buttons
│   ├── Connect (SSH terminal or RDP info)
│   ├── Variable editor (per-instance)
│   ├── SecurityGroupEditor (inline)
│   ├── EKSEditor (inline)
│   ├── DescriptionModal, DebugModal, ConfirmModal
│   └── Output display (collapsible)
└── ResultsPanel (execution log with status indicators)
```

## API Endpoints

### Terraform Router (`/api/terraform`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/resources` | List all discovered resources |
| GET | `/resources/{resource_id}/variables` | Get instance variables |
| GET | `/resources/{resource_id}/description` | Get DESCRIPTION.md content |
| PUT | `/resources/{resource_id}/variables/{var_name}` | Update instance variable |
| POST | `/resources/{resource_id}/variables/restore` | Restore instance vars from root |
| GET | `/variables` | Get root variables |
| PUT | `/variables/{var_name}` | Update root variable |
| GET | `/state` | Full state (resources + variables) |
| GET | `/init/{resource_id}/status` | Check terraform init status |
| POST | `/init/{resource_id}` | Run terraform init |
| GET | `/plan/stream/{resource_id}` | Stream terraform plan (SSE) |
| GET | `/apply/stream/{resource_id}` | Stream terraform apply (SSE) |
| GET | `/destroy/stream/{resource_id}` | Stream terraform destroy (SSE) |
| GET | `/output` | Get terraform output values |
| GET | `/onboarding/status` | Check shared resource status |
| GET | `/onboarding/config-status` | Check config onboarding status |
| POST | `/onboarding/sync-tfvars-to-instances` | Copy root tfvars to all instances |
| POST | `/onboarding/sync-to-parameter-store` | Persist config to Parameter Store |
| GET | `/aws/vpcs` | List AWS VPCs |
| GET | `/aws/subnets` | List subnets for a VPC |
| POST | `/aws/key-pair` | Create EC2 key pair |
| GET/POST | `/eks/config` | Get/update EKS configuration |
| GET/POST | `/security-group/rules` | Get/update Security Group rules |

### Backend Router (`/api/backend`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/suggest-bucket-name` | Generate S3 bucket/DynamoDB table names |
| POST | `/setup` | Create S3 bucket + DynamoDB table + backend.tf |
| POST | `/check` | Check backend infrastructure status |
| GET | `/status` | Backend config status per instance |
| GET | `/onboarding/status` | Check if onboarding config exists |
| POST | `/generate/{resource_id}` | Regenerate backend.tf for one instance |

### SSH Router (`/api/ssh`)

| Method | Path | Description |
|--------|------|-------------|
| WS | `/connect/{connection_id}` | WebSocket SSH terminal (paramiko) |
| GET | `/connections` | List active SSH sessions |
| DELETE | `/connections/{connection_id}` | Close SSH session |

### Keys Router (`/api/keys`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/upload` | Upload SSH key (JSON body) |
| POST | `/upload-file` | Upload SSH key (.pem file) |
| GET | `/list` | List stored keys |
| GET | `/{key_name}` | Get key metadata |
| DELETE | `/{key_name}` | Delete key |
| POST | `/{key_name}/description` | Update key description |
| GET | `/storage/info` | Storage backend info |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API info |
| GET | `/health` | Health check |

## Data Models

### Backend (Pydantic)

- `ResourceType` - EC2, RDS, EKS, ECS, ECR, LAMBDA, DBM, TEST, SECURITY_GROUP
- `ResourceStatus` - ENABLED, DISABLED, UNKNOWN
- `TerraformResource` - id, name, type, file_path, line_start, line_end, status, description
- `TerraformVariable` - name, value, description, sensitive, is_common

### Frontend (TypeScript)

Mirrors backend models in `src/types/index.ts` with matching enums and interfaces.

### Resource Config System (`resource_config.py`)

- `COMMON_VARIABLES` - Shared across all instances (vpc_id, subnets, creator, team, region)
- `EXCLUDED_VARIABLES` - Hidden from UI (ec2_key_name, AWS credentials)
- `ONBOARDING_PHASES` - 4 phases (project/tagging, EC2 key, VPC/subnet, Datadog)
- `RESOURCE_VARIABLE_CONFIGS` - Per-resource variable definitions with types and defaults

## Docker Configuration

### `docker-compose.yml` (end-user)

- **backend**: Pre-built image `terraform-webui-backend:latest`, port 8000
- **frontend**: Built from `./frontend/Dockerfile`, port 3000
- **Volume**: `${TERRAFORM_DATA_PATH:-./terraform-data}` → `/app/terraform`
- **Network**: `terraform-network` bridge

### `docker-compose.build.yml` (developer)

- Same as above but builds backend image locally from `./backend/Dockerfile`
- Default branch: `webui-dev`

### Environment Variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_ACCESS_KEY_ID` | Yes | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Yes | AWS secret key |
| `AWS_SESSION_TOKEN` | No | For temporary credentials |
| `AWS_REGION` | No | Default: `ap-northeast-2` |
| `INSTANCES_REPO_URL` | Yes | Git repo with instance templates |
| `INSTANCES_REPO_BRANCH` | No | Default: `webui` |
| `TERRAFORM_DATA_PATH` | No | Default: `./terraform-data` |
| `FORCE_REINIT` | No | Re-clone instances on startup |

### Container Startup (`entrypoint.sh`)

1. Create `/app/terraform` if missing
2. If `FORCE_REINIT=true`, remove existing instances
3. If `INSTANCES_REPO_URL` set and no instances: Git sparse checkout (`instances/`, `apps/`)
4. Run `python3 -m app.init_config` (S3/Parameter Store sync)
5. Start uvicorn with `--reload`

## Development

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dev server: http://localhost:3000 (proxies `/api` to backend via vite.config.ts)

### Docker Compose

```bash
cp .env.example .env   # configure AWS credentials + INSTANCES_REPO_URL
docker-compose -f docker-compose.build.yml up -d   # developer build
docker-compose up -d                                 # end-user (pre-built image)
```

Web UI: http://localhost:3000

## Resource Type System

### Supported Types

| Type | Directory Prefix | Examples |
|------|-----------------|----------|
| EC2 | `ec2-*` | ec2-basic, ec2-datadog-docker, ec2-windows-2025 |
| EKS | `eks-*` | eks-cluster |
| ECS | `ecs-*` | ecs-ec2, ecs-fargate |
| ECR | `ecr-*`, `deploy-*` | ecr-apps, deploy-spring-boot |
| Lambda | `lambda-*` | lambda-python-example |
| DBM | `dbm-*` | dbm-autoconfig-postgres |
| RDS | `rds-*` | (prefix-based) |
| Security Group | `security-group` | security-group |
| Test | `test-*` | test-file-1 |

### Instance Directory Structure

Each instance directory contains:
- `main.tf` - Resource definitions (module blocks)
- `variables.tf` - Variable declarations
- `terraform.tfvars` - Variable values (synced from root + per-instance overrides)
- `backend.tf` - S3 backend configuration (auto-generated)
- `outputs.tf` - Output definitions
- `DESCRIPTION.md` - Human-readable description (shown in UI)

## Security

- AWS credentials via environment variables only (no `.aws` mount)
- SSH keys stored in Parameter Store (encrypted) with local fallback
- Config persisted in Parameter Store and S3
- `.env` file gitignored
- No built-in authentication (designed for local/personal use)
- Per-resource operation locks prevent concurrent modifications

## Code Style

- **Python**: PEP 8, type hints, no comments in code, no unused code
- **TypeScript**: Strict mode, functional components with hooks
- **CSS**: Dark/light mode via `body.light-mode`, glassmorphism design system
- **General**: Keep code concise, readable, and minimal; include debug-level logging
