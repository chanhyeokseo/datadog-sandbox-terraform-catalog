# DogSTAC MCP Server

MCP (Model Context Protocol) server that exposes DogSTAC infrastructure management capabilities to AI clients such as Claude Desktop, Cursor, and other MCP-compatible tools.

## Prerequisites

- Python 3.11+
- DogSTAC backend running on `http://localhost:8000` (via `docker-compose up`)

## Setup

```bash
cd mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Connecting to Cursor

Add the following to your Cursor MCP settings (`.cursor/mcp.json` in your project root or global settings):

```json
{
  "mcpServers": {
    "dogstac": {
      "command": "/path/to/Catalog/mcp-server/.venv/bin/python",
      "args": ["/path/to/Catalog/mcp-server/server.py"],
      "env": {
        "DOGSTAC_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

Replace `/path/to/Catalog` with the actual path to the repository.

## Connecting to Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "dogstac": {
      "command": "/path/to/Catalog/mcp-server/.venv/bin/python",
      "args": ["/path/to/Catalog/mcp-server/server.py"],
      "env": {
        "DOGSTAC_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DOGSTAC_API_URL` | `http://localhost:8000` | DogSTAC backend API URL |

## Available Tools (26)

### Credentials

| Tool | Description |
|------|-------------|
| `check_credentials` | Check if AWS credentials are valid |
| `sso_login` | Start AWS SSO login flow (returns URL + code for the user) |
| `poll_sso_status` | Poll for SSO login completion |

### Resource Management

| Tool | Description |
|------|-------------|
| `list_resources` | List all Terraform resources with deployment status |
| `get_resource_details` | Get resource variables and description |
| `get_common_variables` | Get root-level common variables |
| `set_variable` | Set a root or resource-level variable |

### Terraform Operations

| Tool | Description |
|------|-------------|
| `terraform_plan` | Run terraform plan |
| `terraform_apply` | Run terraform apply (auto-approve) |
| `terraform_destroy` | Run terraform destroy (auto-approve) |
| `terraform_output` | Get terraform outputs (IPs, IDs, etc.) |

### Security Group

| Tool | Description |
|------|-------------|
| `get_security_group_rules` | Get current ingress/egress rules |
| `add_my_ip_ssh_rule` | Allow SSH from current IP and apply |

### EC2 + SSH

| Tool | Description |
|------|-------------|
| `ssh_execute` | Run a command on an EC2 instance via SSH |

### EKS Management

| Tool | Description |
|------|-------------|
| `list_eks_presets` | List available EKS presets |
| `get_eks_preset_details` | Get preset manifest details |
| `deploy_eks_preset` | Deploy a preset to the EKS cluster |
| `undeploy_eks_preset` | Undeploy a preset from the cluster |
| `run_kubectl` | Execute kubectl/helm commands |
| `get_eks_deployments` | List currently deployed presets |

### ECS Management

| Tool | Description |
|------|-------------|
| `list_ecs_presets` | List available ECS presets |
| `deploy_ecs_preset` | Deploy a preset to the ECS cluster |
| `undeploy_ecs_preset` | Undeploy a preset from the cluster |
| `get_ecs_cluster_status` | Get ECS cluster status |
| `get_ecs_active_workloads` | Get active services and tasks |
| `get_ecs_container_instances` | Get EC2 container instances |
| `run_ecs_command` | Run read-only ECS API queries |

## Guardrails

The following constraints are enforced by the DogSTAC backend for all MCP requests (WebUI users are not affected):

| Constraint | Detail |
|------------|--------|
| Security group | Only `add_my_ip_ssh_rule` is allowed; direct rule modification is blocked |
| Instance type | Only `t3.micro` and `t3.medium` are permitted |
| Node count | EKS/ECS node count variables cannot exceed 3 |

## Running Tests

```bash
cd mcp-server
source .venv/bin/activate
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

## Architecture

```
AI Client (Cursor / Claude Desktop)
    │
    │  MCP (stdio)
    ▼
server.py ── dogstac_client.py ──HTTP──▶ DogSTAC Backend (:8000)
    │                                         │
    ├── tools/credentials.py                  ├── Terraform Runner
    ├── tools/resource.py                     ├── SSH Service
    ├── tools/terraform.py                    ├── EKS Manager
    ├── tools/security_group.py               ├── ECS Manager
    ├── tools/ec2_ssh.py                      └── Guardrail Middleware
    ├── tools/eks.py
    └── tools/ecs.py
```

All HTTP requests from the MCP server include the `X-DogSTAC-Source: mcp` header, which activates the guardrail middleware on the backend.
