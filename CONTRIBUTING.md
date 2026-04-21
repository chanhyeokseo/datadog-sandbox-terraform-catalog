# Contributing to DogSTAC

Thank you for your interest in contributing. This guide covers the development workflow, conventions, and expectations for all changes.

## Prerequisites

| Tool | Purpose |
|:----:|---------|
| **Docker or Podman** | Container runtime |
| **Git** | Version control |
| **Python 3.11+** | Backend development |
| **Node 18+** | Frontend development |
| **AWS CLI** | Configured with SSO or static credentials (`~/.aws`) |

## Development Setup

### Full Stack (dogstac-build)

First-time setup:

```bash
./dogstac-build.sh init
```

The interactive wizard configures `.env` (AWS credentials, salt), builds the image from local source, and starts the container.

Subsequent runs:

```bash
./dogstac-build.sh start          # rebuild and start
./dogstac-build.sh start-no-build # start without rebuilding
```

Set up a shell alias for convenience:

```bash
./dogstac-build.sh alias          # adds 'dogstac-build' alias
```

- UI + API docs: http://localhost:7621 (API docs at `/docs`)

### Backend Only

```bash
cd webui/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 7621
```

### Frontend Only

```bash
cd webui/frontend
npm install
npm run dev
```

Dev server proxies `/api` to `localhost:7621` (backend).

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

## CLI Reference (dogstac-build)

| Command | Description |
|---------|-------------|
| `./dogstac-build.sh init` | Interactive setup (.env) and start the container |
| `./dogstac-build.sh start` | Build from local source and start |
| `./dogstac-build.sh start-no-build` | Start without rebuilding |
| `./dogstac-build.sh build` | Build the local image only |
| `./dogstac-build.sh publish` | Tag and push to trigger release build **(admin only)** |
| `./dogstac-build.sh stop` | Stop the running container |
| `./dogstac-build.sh delete` | Stop and remove the container |
| `./dogstac-build.sh status` | Show container status |
| `./dogstac-build.sh logs` | Follow container logs |
| `./dogstac-build.sh alias` | Add `dogstac-build` alias to your shell config |

## Releases

> **Admin only.** The `publish` command requires push access to the repository. If you don't have write permission, `git push` will fail with a permission error — no tags will be published remotely.

```bash
./dogstac-build.sh publish
```

This prompts for a version number, creates a git tag `v{version}`, and pushes it to origin. The [docker-publish](.github/workflows/docker-publish.yml) workflow then builds multi-platform images (`linux/amd64` + `linux/arm64`) and pushes to Docker Hub as `dogstac/dogstac:{version}` and `dogstac/dogstac:latest`.
