import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

if not os.environ.get("AWS_PROFILE", "").strip():
    os.environ.pop("AWS_PROFILE", None)

from app.routes import terraform, ssh, backend, keys, danger_zone

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(terraform.runner.warmup_provider_cache())
    yield


app = FastAPI(
    title="Terraform Web UI",
    description="Web UI for managing Terraform infrastructure",
    version="1.0.0",
    lifespan=lifespan,
)

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


@app.get("/")
async def root():
    return {
        "message": "Terraform Web UI API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
