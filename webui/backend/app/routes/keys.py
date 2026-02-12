"""
SSH Key Management API
Endpoints for managing SSH private keys in AWS Parameter Store
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
import logging
import os

from app.services.key_manager import ParameterStoreKeyManager, LocalKeyManager

router = APIRouter(prefix="/api/keys", tags=["keys"])
logger = logging.getLogger(__name__)

# Initialize key manager
USE_PARAMETER_STORE = os.environ.get("USE_PARAMETER_STORE", "true").lower() == "true"
key_manager = ParameterStoreKeyManager() if USE_PARAMETER_STORE else LocalKeyManager()


class KeyUploadRequest(BaseModel):
    key_name: str
    private_key_content: str
    description: Optional[str] = ""


class KeyInfo(BaseModel):
    name: str
    description: Optional[str] = ""
    last_modified: Optional[str] = None
    version: Optional[int] = None
    tier: Optional[str] = None


@router.post("/upload")
async def upload_key(request: KeyUploadRequest):
    """
    Upload an SSH private key to Parameter Store

    The key will be stored encrypted using AWS KMS
    """
    try:
        # Validate PEM format
        if "BEGIN" not in request.private_key_content or "PRIVATE KEY" not in request.private_key_content:
            raise HTTPException(
                status_code=400,
                detail="Invalid PEM format. Must contain BEGIN/END PRIVATE KEY markers"
            )

        success = key_manager.upload_key(
            key_name=request.key_name,
            private_key_content=request.private_key_content,
            description=request.description
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to upload key")

        return {
            "success": True,
            "message": f"Key '{request.key_name}' uploaded successfully",
            "storage": "parameter-store" if USE_PARAMETER_STORE else "local"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-file")
async def upload_key_file(
    key_name: str,
    file: UploadFile = File(...),
    description: str = ""
):
    """
    Upload an SSH private key from a PEM file

    Accepts .pem files and stores them in Parameter Store
    """
    try:
        # Validate file extension
        if not file.filename.endswith('.pem'):
            raise HTTPException(
                status_code=400,
                detail="Only .pem files are accepted"
            )

        # Read file content
        content = await file.read()
        pem_content = content.decode('utf-8')

        # Validate PEM format
        if "BEGIN" not in pem_content or "PRIVATE KEY" not in pem_content:
            raise HTTPException(
                status_code=400,
                detail="Invalid PEM format"
            )

        success = key_manager.upload_key(
            key_name=key_name,
            private_key_content=pem_content,
            description=description or f"Uploaded from {file.filename}"
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to upload key")

        return {
            "success": True,
            "message": f"Key '{key_name}' uploaded successfully from {file.filename}",
            "storage": "parameter-store" if USE_PARAMETER_STORE else "local"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload key file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_keys():
    """
    List all SSH keys stored in Parameter Store

    Returns metadata only (not the actual key values)
    """
    try:
        keys = key_manager.list_keys()
        return {
            "keys": keys,
            "count": len(keys),
            "storage": "parameter-store" if USE_PARAMETER_STORE else "local"
        }
    except Exception as e:
        logger.error(f"Failed to list keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{key_name}")
async def get_key_info(key_name: str):
    """
    Get metadata about a specific key

    Does NOT return the actual private key value
    """
    try:
        if isinstance(key_manager, ParameterStoreKeyManager):
            info = key_manager.get_key_info(key_name)
            if not info:
                raise HTTPException(status_code=404, detail=f"Key '{key_name}' not found")
            return info
        else:
            # Local key manager
            keys = key_manager.list_keys()
            matching = [k for k in keys if k["name"] == key_name]
            if not matching:
                raise HTTPException(status_code=404, detail=f"Key '{key_name}' not found")
            return matching[0]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get key info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{key_name}")
async def delete_key(key_name: str):
    """
    Delete an SSH private key from Parameter Store

    ⚠️ This action cannot be undone!
    """
    try:
        success = key_manager.delete_key(key_name)

        if not success:
            raise HTTPException(status_code=404, detail=f"Key '{key_name}' not found")

        return {
            "success": True,
            "message": f"Key '{key_name}' deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{key_name}/description")
async def update_key_description(key_name: str, description: str):
    """Update the description of an existing key"""
    try:
        if not isinstance(key_manager, ParameterStoreKeyManager):
            raise HTTPException(
                status_code=501,
                detail="Description update only supported for Parameter Store"
            )

        success = key_manager.update_key_description(key_name, description)

        if not success:
            raise HTTPException(status_code=404, detail=f"Key '{key_name}' not found")

        return {
            "success": True,
            "message": f"Description updated for key '{key_name}'"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update description: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/storage/info")
async def get_storage_info():
    """Get information about the current key storage backend"""
    return {
        "storage_type": "parameter-store" if USE_PARAMETER_STORE else "local",
        "enabled": True,
        "description": (
            "Keys are stored encrypted in AWS Systems Manager Parameter Store"
            if USE_PARAMETER_STORE
            else "Keys are stored in local file system (development mode)"
        ),
        "features": {
            "encryption": USE_PARAMETER_STORE,
            "versioning": USE_PARAMETER_STORE,
            "audit_logs": USE_PARAMETER_STORE
        }
    }
