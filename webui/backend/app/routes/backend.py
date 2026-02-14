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
from app.services.instance_discovery import get_resource_directory_map

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


class BucketNameRequest(BaseModel):
    creator: str
    team: str


@router.post("/suggest-bucket-name")
async def suggest_bucket_name(request: BucketNameRequest):
    """
    Generate suggested S3 bucket and DynamoDB table names using AWS credential hash
    This ensures names match Parameter Store naming convention
    """
    try:
        config_manager = ConfigManager(terraform_dir=TERRAFORM_DIR)
        bucket_name = config_manager.generate_bucket_name(
            creator=request.creator,
            team=request.team
        )
        table_name = config_manager.generate_dynamodb_table_name(
            creator=request.creator,
            team=request.team
        )

        return {
            "bucket_name": bucket_name,
            "table_name": table_name,
            "bucket_pattern": "dogstac-<creator>-<hash>",
            "table_pattern": "dogstac-<hash>-locks"
        }

    except Exception as e:
        logger.error(f"Failed to generate backend names: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

        # Upload terraform.tfvars files to S3
        try:
            from app.services.terraform_parser import TerraformParser
            parser = TerraformParser(TERRAFORM_DIR)

            copied = parser.copy_root_tfvars_to_instances()

            result["tfvars_synced"] = {
                "root_copied_to_instances": copied,
                "message": "Root terraform.tfvars copied to all instances and synced to S3"
            }

            if copied:
                logger.info("Successfully copied root tfvars to all instances and synced to S3")
            else:
                logger.warning("Root terraform.tfvars not found or failed to copy")
        except Exception as e:
            logger.warning(f"Failed to sync tfvars to S3: {e}")
            result["tfvars_sync_error"] = str(e)

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


@router.post("/generate/{resource_id}")
async def generate_backend_for_instance(
    resource_id: str,
    request: BackendSetupRequest
):
    """Generate backend.tf for a specific instance"""
    try:
        instances_dir = Path(TERRAFORM_DIR) / "instances"

        # Map resource_id to actual directory name
        resource_dir_map = get_resource_directory_map(instances_dir)
        dir_name = resource_dir_map.get(resource_id)

        if not dir_name:
            raise HTTPException(status_code=404, detail=f"Resource {resource_id} not found")

        instance_dir = instances_dir / dir_name

        if not instance_dir.exists():
            raise HTTPException(status_code=404, detail=f"Instance directory {dir_name} not found")

        if not (instance_dir / "main.tf").exists():
            raise HTTPException(status_code=400, detail=f"{dir_name} is not a valid instance")

        manager = BackendManager(region=request.region)
        backend_content = manager.generate_backend_config(
            bucket_name=request.bucket_name,
            instance_name=resource_id,
            table_name=request.table_name
        )

        backend_file = instance_dir / "backend.tf"
        backend_file.write_text(backend_content, encoding="utf-8")

        return {
            "success": True,
            "instance": resource_id,
            "backend_file": str(backend_file)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate backend for {resource_id}: {e}")
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
