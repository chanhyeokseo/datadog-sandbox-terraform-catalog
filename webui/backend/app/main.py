import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import logging

if not os.environ.get("AWS_PROFILE", "").strip():
    os.environ.pop("AWS_PROFILE", None)

from app.routes import terraform, ssh, backend, keys, danger_zone, eks_manage, ecs_manage, cluster_share
from app.services.credential_manager import credential_manager
from app.middleware.guardrails import GuardrailMiddleware

log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
for _noisy in ('botocore', 'boto3', 'urllib3', 's3transfer'):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    terraform.parser.ensure_tfvars_for_new_instances()
    terraform.parser.build_s3_status_cache()
    eks_manage.preset_manager.initialize_local_cache()
    ecs_manage.preset_manager.initialize_local_cache()
    asyncio.create_task(terraform.runner.warmup_provider_cache())
    asyncio.create_task(credential_manager.background_refresh_loop())
    yield


app = FastAPI(
    title="Terraform Web UI",
    description="Web UI for managing Terraform infrastructure",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(GuardrailMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(terraform.router)
app.include_router(ssh.router)
app.include_router(backend.router)
app.include_router(keys.router)
app.include_router(danger_zone.router)
app.include_router(eks_manage.router)
app.include_router(ecs_manage.router)
app.include_router(cluster_share.router)


@app.get("/health")
async def health():
    return {"status": "healthy"}

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
logger = logging.getLogger(__name__)

if STATIC_DIR.is_dir():
    logger.info("Serving frontend from %s", STATIC_DIR)
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(STATIC_DIR / "index.html"))
else:
    logger.info("No static directory found at %s, running API-only mode", STATIC_DIR)

    @app.get("/")
    async def root():
        return {"message": "Terraform Web UI API", "version": "1.0.0", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("TFRUNNER_PORT", "7621")))
