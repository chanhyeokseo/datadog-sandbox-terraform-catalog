"""
Backend Setup API
Endpoints for automatic S3 backend configuration
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import os
from pathlib import Path

from app.services.backend_manager import BackendManager
from app.services.config_manager import ConfigManager

router = APIRouter(prefix="/api/backend", tags=["backend"])
logger = logging.getLogger(__name__)

TERRAFORM_DIR = os.environ.get("TERRAFORM_DIR", "/terraform")


class BackendSetupRequest(BaseModel):
    bucket_name: str
    table_name: Optional[str] = "terraform-state-locks"
    region: Optional[str] = "ap-northeast-2"


class BackendCheckRequest(BaseModel):
    bucket_name: str
    table_name: Optional[str] = "terraform-state-locks"
    region: Optional[str] = "ap-northeast-2"


@router.post("/setup")
async def setup_backend(request: BackendSetupRequest):
    """
    Create S3 bucket and DynamoDB table for Terraform backend
    Also generates backend.tf files for all instances
    """
    try:
        manager = BackendManager(region=request.region)

        # Create infrastructure
        result = manager.setup_backend_infrastructure(
            bucket_name=request.bucket_name,
            table_name=request.table_name
        )

        if not result["success"]:
            raise HTTPException(status_code=500, detail={
                "message": "Failed to setup backend infrastructure",
                "errors": result["errors"]
            })

        # Generate backend.tf for all instances
        instances_dir = Path(TERRAFORM_DIR) / "instances"
        if instances_dir.exists():
            generated = _generate_backend_files(
                instances_dir,
                request.bucket_name,
                request.table_name,
                request.region
            )
            result["backend_files_generated"] = generated

        return {
            "success": True,
            "message": "Backend infrastructure created successfully",
            "details": result
        }

    except Exception as e:
        logger.error(f"Failed to setup backend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check")
async def check_backend(request: BackendCheckRequest):
    """Check if backend infrastructure exists"""
    try:
        manager = BackendManager(region=request.region)
        status = manager.get_backend_status(
            bucket_name=request.bucket_name,
            table_name=request.table_name
        )
        return status
    except Exception as e:
        logger.error(f"Failed to check backend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/onboarding/status")
async def get_onboarding_status():
    """
    Check if onboarding is complete
    Returns True if configuration exists in Parameter Store
    """
    try:
        config_manager = ConfigManager(terraform_dir=TERRAFORM_DIR)
        is_complete = config_manager.config_exists()

        return {
            "onboarding_complete": is_complete,
            "message": "Onboarding completed" if is_complete else "Onboarding not completed"
        }
    except Exception as e:
        logger.error(f"Failed to check onboarding status: {e}")
        return {
            "onboarding_complete": False,
            "message": "Unable to check onboarding status"
        }


@router.get("/status")
async def get_backend_status():
    """
    Get backend configuration status
    Checks if instances are using S3 backend
    """
    instances_dir = Path(TERRAFORM_DIR) / "instances"
    if not instances_dir.exists():
        return {
            "configured": False,
            "message": "No instances directory found"
        }

    total = 0
    with_backend = 0
    instances = []

    for instance_dir in instances_dir.iterdir():
        if not instance_dir.is_dir():
            continue
        if not (instance_dir / "main.tf").exists():
            continue

        total += 1
        backend_file = instance_dir / "backend.tf"
        has_backend = backend_file.exists()

        if has_backend:
            with_backend += 1

        instances.append({
            "name": instance_dir.name,
            "has_backend": has_backend
        })

    return {
        "configured": with_backend > 0,
        "total_instances": total,
        "instances_with_backend": with_backend,
        "instances": instances
    }


@router.post("/generate/{instance_name}")
async def generate_backend_for_instance(
    instance_name: str,
    request: BackendSetupRequest
):
    """Generate backend.tf for a specific instance"""
    try:
        instances_dir = Path(TERRAFORM_DIR) / "instances"
        instance_dir = instances_dir / instance_name

        if not instance_dir.exists():
            raise HTTPException(status_code=404, detail=f"Instance {instance_name} not found")

        if not (instance_dir / "main.tf").exists():
            raise HTTPException(status_code=400, detail=f"{instance_name} is not a valid instance")

        manager = BackendManager(region=request.region)
        backend_content = manager.generate_backend_config(
            bucket_name=request.bucket_name,
            instance_name=instance_name,
            table_name=request.table_name
        )

        backend_file = instance_dir / "backend.tf"
        backend_file.write_text(backend_content, encoding="utf-8")

        return {
            "success": True,
            "instance": instance_name,
            "backend_file": str(backend_file)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate backend for {instance_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _generate_backend_files(
    instances_dir: Path,
    bucket_name: str,
    table_name: str,
    region: str
) -> int:
    """Generate backend.tf files for all instances"""
    manager = BackendManager(region=region)
    count = 0

    for instance_dir in instances_dir.iterdir():
        if not instance_dir.is_dir():
            continue
        if not (instance_dir / "main.tf").exists():
            continue

        backend_file = instance_dir / "backend.tf"
        if backend_file.exists():
            logger.info(f"Skipping {instance_dir.name} - backend.tf already exists")
            continue

        backend_content = manager.generate_backend_config(
            bucket_name=bucket_name,
            instance_name=instance_dir.name,
            table_name=table_name
        )

        backend_file.write_text(backend_content, encoding="utf-8")
        logger.info(f"Generated backend.tf for {instance_dir.name}")
        count += 1

    return count
