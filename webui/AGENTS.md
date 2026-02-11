# Terraform Web UI - Project Overview for AI coding assistant

## Project Summary
Terraform Web UI is a web-based management tool for Terraform infrastructure. It provides a visual interface to enable/disable Terraform resources and provision infrastructure with button clicks. The application consists of a FastAPI backend and React frontend, running together in Docker Compose.

## Project Structure

### Core Directories
- `/backend/` - FastAPI backend application
  - `app/` - Main application code
    - `main.py` - FastAPI application entry point
    - `config/` - Resource configuration management
      - `resource_config.py` - Centralized resource variable definitions
    - `models/` - Pydantic data models
      - `schemas.py` - API request/response schemas
    - `routes/` - API endpoint handlers
      - `terraform.py` - Terraform operations endpoints
      - `ssh.py` - SSH connection endpoints
    - `services/` - Business logic layer
      - `terraform_parser.py` - Parse Terraform files and extract resources
      - `terraform_runner.py` - Execute Terraform CLI commands
  - `requirements.txt` - Python dependencies
  - `Dockerfile` - Backend container image
  - `entrypoint.sh` - Container startup script

- `/frontend/` - React TypeScript frontend
  - `src/` - Source code
    - `App.tsx` - Main application component
    - `components/` - React components
      - `ResourceSidebar.tsx` - Resource list sidebar
      - `ActionPanel.tsx` - Terraform action buttons and controls
      - `ResultsPanel.tsx` - Execution results display
      - `ConfigModal.tsx` - Configuration editor
      - `ConnectionsModal.tsx` - SSH connections manager
      - `OnboardingModal.tsx` - First-time setup guide
      - `Terminal.tsx` - Terminal emulator using xterm.js
      - `EKSEditor.tsx` - EKS-specific configuration editor
      - `SecurityGroupEditor.tsx` - Security group editor
      - `OutputModal.tsx` - Output display modal
      - `DebugModal.tsx` - Debug information display
    - `services/` - API client layer
      - `api.ts` - Axios-based API client
    - `types/` - TypeScript type definitions
      - `index.ts` - Shared types and enums
    - `styles/` - CSS stylesheets
      - `App.css` - Main application styles
      - `Unified.css` - Unified styling system
      - `Terminal.css` - Terminal component styles
      - `EKSEditor.css` - EKS editor styles
      - `SecurityGroupEditor.css` - Security group editor styles
      - `OnboardingModal.css` - Onboarding modal styles
      - `DebugModal.css` - Debug modal styles
  - `package.json` - npm dependencies
  - `Dockerfile` - Frontend container image
  - `nginx.conf` - Nginx configuration for serving React app
  - `vite.config.ts` - Vite build configuration
  - `tsconfig.json` - TypeScript configuration

- Root configuration files
  - `docker-compose.yml` - Multi-container orchestration
  - `.env.example` - Environment variables template
  - `README.md` - User documentation
  - `DEVELOPMENT.md` - Developer guide
  - `REFACTORING.md` - Code refactoring history and patterns

## Development Workflow

### Common Commands

#### Backend Development

```bash
cd backend

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

export AWS_REGION=ap-northeast-2
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export DD_API_KEY=your-datadog-key

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API documentation available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

#### Frontend Development

```bash
cd frontend

npm install

npm run dev

npm run build

npm run preview
```

Development server runs at: http://localhost:5173

#### Docker Compose

```bash
cd webui

cp .env.example .env

docker-compose up -d

docker-compose logs -f backend

docker-compose logs -f frontend

docker-compose down
```

Web UI available at: http://localhost:3000

### Development Configuration

Environment variables should be configured in `.env` file at webui root:

```bash
AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
DD_API_KEY=your-datadog-api-key
DD_SITE=datadoghq.com
```

## Key Components

### Backend Architecture

#### TerraformParser
Located in `app/services/terraform_parser.py`

Parses Terraform files and manages resource state.

**Key Methods:**
- `parse_all_resources()` - Extract all resources from Terraform files
- `parse_variables()` - Extract variables from terraform.tfvars
- `toggle_resource()` - Comment/uncomment resource blocks
- `get_resource_variables()` - Get variables for specific resource
- `update_variable()` - Update variable value in terraform.tfvars

**Resource Discovery:**
1. Scans configured Terraform instance files
2. Uses regex to find `module "name" { ... }` blocks
3. Determines status by checking comment markers
4. Extracts metadata (name, type, file path, line numbers)
5. Maps to ResourceType enum

#### TerraformRunner
Located in `app/services/terraform_runner.py`

Executes Terraform CLI commands asynchronously.

**Key Methods:**
- `init()` - Run terraform init
- `validate()` - Run terraform validate
- `plan()` - Run terraform plan
- `apply()` - Run terraform apply
- `destroy()` - Run terraform destroy
- `stream_plan()` - Stream plan output in real-time
- `stream_apply()` - Stream apply output in real-time
- `get_output()` - Get terraform output values

**Features:**
- Async execution using asyncio
- Real-time stdout/stderr streaming
- Configurable timeout (default 5 minutes)
- Working directory management
- Environment variable passing

#### Resource Configuration System
Located in `app/config/resource_config.py`

Centralized configuration for resource-specific variables.

**Pattern:**
```python
RESOURCE_VARIABLE_CONFIGS = {
    "eks": [
        ResourceVariableConfig(
            "eks_enable_node_group",
            VariableType.BOOLEAN,
            True,
            "Enable Linux node group for EKS cluster"
        ),
    ],
}
```

**Benefits:**
- Single source of truth for resource variables
- Automatic UI generation from configuration
- Type-safe variable definitions
- Easy to add new resources

### Frontend Architecture

#### Component Hierarchy

```
App (main.tsx)
├── ResourceSidebar
│   └── Individual resource cards with toggle switches
├── ActionPanel
│   ├── Terraform action buttons (Init/Plan/Apply/Destroy)
│   └── Resource-specific controls
└── ResultsPanel
    └── Execution logs and results
```

#### State Management

Uses React built-in state management with useState and useEffect hooks.

**Main State:**
- `resources` - List of Terraform resources
- `selectedResource` - Currently selected resource
- `results` - Execution results and logs
- `isDarkMode` - Theme preference
- `runningResources` - Map of resource IDs to running actions
- `onboardingStatus` - First-time setup status

#### API Client
Located in `src/services/api.ts`

Axios-based API client with typed methods:
- `getResources()` - Fetch all resources
- `getResourceVariables()` - Fetch variables for resource
- `toggleResource()` - Enable/disable resource
- `runTerraformCommand()` - Execute Terraform commands
- `streamPlan()` - Stream plan output
- `streamApply()` - Stream apply output
- `updateVariable()` - Update variable value
- `getConnections()` - Fetch SSH connections
- `getOnboardingStatus()` - Check onboarding status

#### TypeScript Types
Located in `src/types/index.ts`

**Core Types:**
- `ResourceType` - Enum of supported resource types
- `ResourceStatus` - enabled/disabled/unknown
- `TerraformResource` - Resource metadata
- `TerraformVariable` - Variable definition
- `ApiResponse` - Standard API response format

## API Endpoints

### Resource Management
- `GET /api/terraform/resources` - List all resources
- `POST /api/terraform/resource/{resource_id}/toggle` - Toggle resource
- `GET /api/terraform/resource/{resource_id}/variables` - Get resource variables
- `GET /api/terraform/variables` - Get all variables
- `POST /api/terraform/variable/{var_name}` - Update variable value

### Terraform Operations
- `POST /api/terraform/init` - Initialize Terraform
- `POST /api/terraform/validate` - Validate configuration
- `GET /api/terraform/plan` - Run plan
- `GET /api/terraform/plan/stream` - Stream plan output (Server-Sent Events)
- `POST /api/terraform/apply` - Apply changes
- `GET /api/terraform/apply/stream` - Stream apply output (Server-Sent Events)
- `POST /api/terraform/destroy` - Destroy all resources
- `GET /api/terraform/output` - Get output values
- `GET /api/terraform/state` - Get complete state

### SSH Operations
- `GET /api/ssh/connections` - List SSH connections
- `GET /api/ssh/connections/{connection_id}` - Get specific connection

### System
- `GET /` - API information
- `GET /health` - Health check

## Testing Strategy

### Backend Testing

Run tests with pytest:
```bash
cd backend
pytest
pytest --cov=app tests/
```

### Frontend Testing

Run tests with npm:
```bash
cd frontend
npm test
npm run lint
```

### Manual Testing

1. Start services with docker-compose
2. Access http://localhost:3000
3. Complete onboarding if first time
4. Toggle resources on/off
5. Run Init → Plan → Apply workflow
6. Check logs for output
7. Verify infrastructure in AWS Console

## Docker Configuration

### Backend Container

**Base Image:** python:3.11-slim

**Key Features:**
- Installs Terraform CLI
- Mounts parent Catalog directory as /terraform
- Mounts AWS credentials from ~/.aws
- Passes environment variables for AWS and Datadog
- Exposes port 8000

### Frontend Container

**Base Image:** node:18 (build stage), nginx:alpine (runtime stage)

**Multi-stage Build:**
1. Build React app with Vite
2. Serve static files with Nginx
3. Proxy /api requests to backend

**Exposes port 3000**

### Networking

Both services connected via `terraform-network` bridge network.

## Important Files

### Configuration
- `.env` - Environment variables (do not commit)
- `.env.example` - Environment variables template
- `docker-compose.yml` - Container orchestration
- `backend/app/config/resource_config.py` - Resource configurations

### Documentation
- `README.md` - User guide and installation
- `DEVELOPMENT.md` - Developer documentation
- `REFACTORING.md` - Refactoring history and patterns
- `AGENTS.md` - This file

## Security Considerations

### Credentials Management
- AWS credentials via environment variables or ~/.aws mount
- Datadog API key via environment variables
- Never commit secrets to git
- `.env` file included in .gitignore

### Access Control
- This tool designed for local laptop use only
- No authentication/authorization built-in
- Direct Terraform state file access
- SSH key management for connections

### Production Deployment
If deploying to production, add:
- Authentication and authorization
- Encrypted secrets management
- Network security controls
- Audit logging
- State file encryption and remote backend

## Resource Type System

### Supported Resource Types
- **EC2** - Virtual machines
- **RDS** - Relational databases (Postgres, MySQL)
- **EKS** - Kubernetes clusters
- **ECS** - Container services
- **ECR** - Container registries
- **Lambda** - Serverless functions
- **DBM** - Database monitoring
- **Security Group** - Network security rules

### Adding New Resource Types

1. Add to ResourceType enum in `frontend/src/types/index.ts`
2. Add configuration in `backend/app/config/resource_config.py`
3. Create module block in Terraform files
4. Add variables to `variables.tf`
5. Set defaults in `terraform.tfvars`
6. Test toggle and apply workflow

## Best Practices

### Backend Development
1. Use type hints for all functions
2. Write docstrings for public methods
3. Handle exceptions gracefully
4. Log important operations
5. Validate inputs with Pydantic models
6. Use async/await for I/O operations

### Frontend Development
1. Use TypeScript strict mode
2. Create reusable components
3. Keep components focused and small
4. Use semantic HTML
5. Handle loading and error states
6. Type all props and state

### Terraform Integration
1. Always run Init before other commands
2. Review Plan output before Apply
3. Use auto-approve carefully
4. Keep state file backed up
5. Test with small resources first
6. Document resource dependencies

### Code Style
- **Python**: Follow PEP 8, use type hints
- **TypeScript**: Follow ESLint rules, use strict mode
- **React**: Functional components with hooks
- **CSS**: Use BEM naming convention

## Troubleshooting Common Issues

### Port Conflicts
Change ports in `docker-compose.yml`:
```yaml
ports:
  - "3001:3000"  # Frontend
  - "8001:8000"  # Backend
```

### AWS Credentials Error
Verify credentials:
```bash
aws sts get-caller-identity
echo $AWS_ACCESS_KEY_ID
```

### Terraform State Lock
If state is locked, manually unlock:
```bash
terraform force-unlock <lock-id>
```

### Container Build Failures
Clean rebuild:
```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Backend Not Responding
Check logs:
```bash
docker-compose logs backend
docker exec -it terraform-webui-backend bash
ps aux | grep uvicorn
```

### Frontend Build Errors
Clean dependencies:
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

## Architecture Patterns

### Config-Driven Development
Resource configurations centralized in `resource_config.py`:
- Variables auto-discovered from config
- UI elements auto-generated
- Type validation automatic
- Easy to extend with new resources

### Streaming Response Pattern
For long-running Terraform commands:
- Backend uses Server-Sent Events (SSE)
- Frontend consumes with EventSource API
- Real-time output display
- Non-blocking user experience

### Toggle Pattern
Resource enable/disable via comment markers:
- Enabled: `module "name" { ... }`
- Disabled: `# module "name" { ... }`
- Parser detects state via regex
- Safe toggling preserves formatting

## Future Enhancements

Potential improvements documented in DEVELOPMENT.md:
- Authentication and authorization
- Multi-user support with role-based access
- Resource dependency visualization
- Cost estimation integration
- Terraform workspace support
- State file history and rollback
- Notification webhooks
- Scheduled operations
- CI/CD pipeline integration
- Test coverage improvements

## Reference Links

- [Terraform Documentation](https://www.terraform.io/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [xterm.js Documentation](https://xtermjs.org/)
