# Contributing to DogSTAC

Thank you for your interest in contributing. This guide covers the development workflow, conventions, and expectations for all changes.

## Prerequisites

| Tool | Purpose |
|:----:|---------|
| **Docker** | Container runtime & Docker Compose |
| **Git** | Version control |
| **Python 3.11+** | Backend development |
| **Node 18+** | Frontend development |
| **AWS CLI** | Configured with SSO or static credentials (`~/.aws`) |

## Development Setup

### Full Stack (Docker Compose)

```bash
cp .env.example .env        # configure AWS_PROFILE and DOGSTAC_SALT
docker compose -f docker-compose.build.yml up --build
```

- UI: http://localhost:3000
- API docs: http://localhost:8000/docs

### Backend Only

```bash
cd webui/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Only

```bash
cd webui/frontend
npm install
npm run dev
```

Dev server runs on port 3000 and proxies `/api` to `localhost:8000`.

## Project Structure

```
├── instances/          # Terraform instance templates
├── modules/            # Reusable Terraform modules
├── apps/               # Deployable application source (Spring Boot, Lambda)
├── eks/                # EKS preset manifests
├── ecs/                # ECS preset task definitions
└── webui/
    ├── backend/        # FastAPI (Python)
    │   ├── app/
    │   │   ├── routes/     # API route handlers
    │   │   ├── services/   # Business logic
    │   │   ├── models/     # Pydantic schemas
    │   │   └── config/     # Resource variable definitions
    │   └── tests/
    └── frontend/       # React + TypeScript (Vite)
        └── src/
            ├── components/
            ├── services/   # API client
            ├── types/
            └── styles/
```

## Code Style

### Python (Backend)

- Follow PEP 8. Use type hints on function signatures.
- No comments in code — names and structure should be self-explanatory.
- No unused imports, functions, or variables.
- Include `logging.debug()` calls for non-trivial operations to aid future troubleshooting.
- Each module creates its own logger: `logger = logging.getLogger(__name__)`.

### TypeScript (Frontend)

- Strict mode is enabled (`strict: true` in `tsconfig.json`).
- Functional components with hooks only — no class components.
- Avoid `any` type; prefer explicit interfaces defined in `src/types/index.ts`.

### CSS

- Use CSS custom properties defined in `Unified.css` for colors and effects.
- Support both dark and light mode via `body.light-mode` class overrides.

### General

- Keep code concise, readable, and minimal.
- Prefer editing existing files over creating new ones.
- Do not introduce ad-hoc workarounds — favor unified, well-structured solutions.

## Testing

### Running Backend Tests

```bash
cd webui/backend
source .venv/bin/activate
pip install -r requirements-test.txt

python -m pytest tests/ -v              # all tests
python -m pytest tests/ -v -k "keyword" # filtered
```

### Test Conventions

| Item | Convention |
|------|-----------|
| Framework | pytest |
| Directory | `webui/backend/tests/` |
| File naming | `test_{module}_{topic}.py` |
| Class naming | `Test{MethodOrFeature}` |
| Function naming | `test_{expected_behavior}` |
| Fixtures | Shared in `conftest.py`; test-local in the test file |
| Environment | Use `unittest.mock.patch.dict(os.environ, ...)` — never leak state |
| Filesystem | Use pytest `tmp_path` — never write to real project directories |
| External services | Mock all AWS calls — tests must run offline |

### Adding a New Test

1. Create `tests/test_{module}_{topic}.py`.
2. Import the unit under test from `app.*`.
3. Use shared fixtures from `conftest.py` or define local ones.
4. Group related tests in a class: `class Test{Feature}:`.
5. Run with `python -m pytest tests/test_{module}_{topic}.py -v`.

## Branching and Commits

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/short-description
   ```
2. Use concise commit messages that explain **why**, not just what.
3. Keep commits atomic — one logical change per commit.

### Branch Naming

| Prefix | Purpose |
|--------|---------|
| `feat/` | New feature |
| `fix/` | Bug fix |
| `refactor/` | Code restructuring (no behavior change) |
| `docs/` | Documentation only |
| `chore/` | Build, CI, dependencies |

## Pull Requests

1. Fill out the [PR template](.github/pull_request_template.md) completely.
2. Keep changes focused — one concern per PR.
3. Verify behavior manually and describe how to reproduce in **How to test**.
4. Ensure no secrets, credentials, or customer data appear in commits, logs, or screenshots.

## Reporting Issues

Use the provided [issue templates](.github/ISSUE_TEMPLATE/):

- **Bug report** — for unexpected behavior or defects.
- **Feature request** — for ideas or improvements.

## Security

- Never commit `.env`, `.pem`, `.key`, or credential files.
- Sensitive Terraform variables (`datadog_api_key`, `rds_password`) are stored in AWS Parameter Store, not in tfvars.
- Redact tokens, keys, and account IDs in any logs or screenshots shared in issues or PRs.

## Releases

Docker images are published automatically when a semver tag is pushed:

```bash
git tag v1.2.3
git push origin v1.2.3
```

This triggers the [docker-publish](.github/workflows/docker-publish.yml) workflow, building multi-platform images (`linux/amd64` + `linux/arm64`) and pushing to Docker Hub as `dogstac/tfrunner` and `dogstac/webui`.
