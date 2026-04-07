import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import ClusterShareRequestCreate
from app.services.cluster_share_manager import ClusterShareManager

router = APIRouter(prefix="/api/cluster-share", tags=["cluster-share"])
logger = logging.getLogger(__name__)

TERRAFORM_DIR = os.environ.get("TERRAFORM_DIR", "/terraform")
share_manager = ClusterShareManager(TERRAFORM_DIR)


@router.get("/clusters")
async def list_eks_clusters():
    clusters = share_manager.list_eks_clusters()
    return {
        "clusters": [c.model_dump() for c in clusters],
        "my_prefix": share_manager._get_my_prefix(),
    }


@router.post("/requests")
async def create_share_request(body: ClusterShareRequestCreate):
    request = share_manager.create_request(
        cluster_name=body.cluster_name,
        cluster_arn=body.cluster_arn,
        owner_prefix=body.owner_prefix,
    )
    if not request:
        raise HTTPException(
            status_code=400,
            detail="Failed to create share request. Check that name_prefix is configured, "
                   "you are not sharing with yourself, and no duplicate pending request exists.",
        )
    return request.model_dump()


@router.get("/requests/incoming")
async def get_incoming_requests():
    requests = share_manager.get_incoming_requests()
    return {"requests": [r.model_dump() for r in requests]}


@router.get("/requests/outgoing")
async def get_outgoing_requests():
    requests = share_manager.get_outgoing_requests()
    return {"requests": [r.model_dump() for r in requests]}


@router.post("/requests/{request_id}/approve")
async def approve_request(request_id: str):
    result = share_manager.approve_request(request_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to approve request")
    return result.model_dump()


@router.post("/requests/{request_id}/deny")
async def deny_request(request_id: str):
    result = share_manager.deny_request(request_id)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to deny request")
    return result.model_dump()


@router.get("/shared")
async def get_shared_clusters():
    shared = share_manager.get_shared_clusters()
    return {"clusters": [s.model_dump() for s in shared]}


@router.get("/connected-users")
async def get_connected_users():
    users = share_manager.get_connected_users()
    return {"users": users}


@router.delete("/requests/{request_id}")
async def delete_request(request_id: str):
    success = share_manager.delete_request(request_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to delete request")
    return {"success": True}
