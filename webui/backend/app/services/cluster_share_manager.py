import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from app.models.schemas import (
    ClusterShareRequest,
    ClusterShareRequestStatus,
    EKSClusterInfo,
    SharedCluster,
)

logger = logging.getLogger(__name__)

SSM_SHARE_PREFIX = "/dogstac-cluster-share/requests"


class ClusterShareManager:
    def __init__(self, terraform_dir: str):
        self.terraform_dir = Path(terraform_dir)
        self._ssm_client = None
        self._eks_client = None

    def _read_tfvar(self, key: str, default: str = "") -> str:
        tfvars_path = self.terraform_dir / "terraform.tfvars"
        if not tfvars_path.exists():
            return default
        try:
            with open(tfvars_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        match = re.match(r'^(\w+)\s*=\s*(?:"([^"]*)"|(\S+))', line)
                        if match and match.group(1) == key:
                            return (match.group(2) or match.group(3) or "").strip() or default
        except Exception as e:
            logger.warning(f"Failed to read {key} from tfvars: {e}")
        return default

    def _get_region(self) -> str:
        return self._read_tfvar("region", "ap-northeast-2")

    def _get_my_prefix(self) -> str:
        return self._read_tfvar("name_prefix", "")

    @property
    def ssm_client(self):
        if self._ssm_client is None:
            try:
                from app.services.config_manager import SSM_GLOBAL_REGION
                self._ssm_client = boto3.client("ssm", region_name=SSM_GLOBAL_REGION)
            except Exception as e:
                logger.warning(f"Failed to create SSM client: {e}")
        return self._ssm_client

    @property
    def eks_client(self):
        if self._eks_client is None:
            try:
                self._eks_client = boto3.client("eks", region_name=self._get_region())
            except Exception as e:
                logger.warning(f"Failed to create EKS client: {e}")
        return self._eks_client

    def list_eks_clusters(self) -> List[EKSClusterInfo]:
        if not self.eks_client:
            return []
        try:
            clusters: List[EKSClusterInfo] = []
            paginator = self.eks_client.get_paginator("list_clusters")
            for page in paginator.paginate():
                for name in page.get("clusters", []):
                    try:
                        desc = self.eks_client.describe_cluster(name=name)
                        cluster = desc.get("cluster", {})
                        tags = cluster.get("tags", {})
                        is_managed = tags.get("ManagedBy") == "Terraform"
                        owner_prefix = None
                        if is_managed:
                            cluster_name_tag = tags.get("Name", "")
                            if cluster_name_tag.endswith("-eks-cluster"):
                                owner_prefix = cluster_name_tag[: -len("-eks-cluster")]
                            elif cluster_name_tag:
                                owner_prefix = cluster_name_tag.split("-")[0]
                        clusters.append(EKSClusterInfo(
                            name=name,
                            arn=cluster.get("arn", ""),
                            status=cluster.get("status", "UNKNOWN"),
                            owner_prefix=owner_prefix,
                        ))
                    except ClientError as e:
                        logger.warning(f"Failed to describe cluster {name}: {e}")
            logger.debug(f"Found {len(clusters)} EKS clusters")
            return clusters
        except ClientError as e:
            logger.error(f"Failed to list EKS clusters: {e}")
            return []

    def _put_request(self, request: ClusterShareRequest) -> bool:
        if not self.ssm_client:
            return False
        try:
            param_name = f"{SSM_SHARE_PREFIX}/{request.id}"
            self.ssm_client.put_parameter(
                Name=param_name,
                Value=request.model_dump_json(),
                Type="String",
                Overwrite=True,
                Description=f"Cluster share request from {request.requester_prefix} to {request.owner_prefix}",
            )
            logger.debug(f"Saved share request {request.id} to SSM")
            return True
        except ClientError as e:
            logger.error(f"Failed to save share request: {e}")
            return False

    def _get_all_requests(self) -> List[ClusterShareRequest]:
        if not self.ssm_client:
            return []
        try:
            requests: List[ClusterShareRequest] = []
            paginator = self.ssm_client.get_paginator("get_parameters_by_path")
            for page in paginator.paginate(Path=SSM_SHARE_PREFIX, Recursive=True, MaxResults=10):
                for param in page.get("Parameters", []):
                    try:
                        data = json.loads(param["Value"])
                        requests.append(ClusterShareRequest(**data))
                    except Exception as e:
                        logger.warning(f"Failed to parse share request {param['Name']}: {e}")
            return requests
        except ClientError as e:
            logger.error(f"Failed to list share requests: {e}")
            return []

    def _get_request_by_id(self, request_id: str) -> Optional[ClusterShareRequest]:
        if not self.ssm_client:
            return None
        try:
            param_name = f"{SSM_SHARE_PREFIX}/{request_id}"
            response = self.ssm_client.get_parameter(Name=param_name)
            data = json.loads(response["Parameter"]["Value"])
            return ClusterShareRequest(**data)
        except ClientError:
            return None

    def create_request(self, cluster_name: str, cluster_arn: str, owner_prefix: str) -> Optional[ClusterShareRequest]:
        my_prefix = self._get_my_prefix()
        if not my_prefix:
            logger.error("Cannot create share request: name_prefix not configured")
            return None

        if my_prefix == owner_prefix:
            logger.warning("Cannot share cluster with yourself")
            return None

        existing = self._get_all_requests()
        for req in existing:
            if (
                req.requester_prefix == my_prefix
                and req.cluster_arn == cluster_arn
                and req.status == ClusterShareRequestStatus.PENDING
            ):
                logger.warning(f"Duplicate pending request for cluster {cluster_name}")
                return None

        now = datetime.now(timezone.utc).isoformat()
        request = ClusterShareRequest(
            id=str(uuid.uuid4()),
            requester_prefix=my_prefix,
            cluster_name=cluster_name,
            cluster_arn=cluster_arn,
            owner_prefix=owner_prefix,
            status=ClusterShareRequestStatus.PENDING,
            created_at=now,
            updated_at=now,
        )

        if self._put_request(request):
            logger.info(f"Created share request {request.id}: {my_prefix} -> {owner_prefix} for {cluster_name}")
            return request
        return None

    def get_incoming_requests(self) -> List[ClusterShareRequest]:
        my_prefix = self._get_my_prefix()
        if not my_prefix:
            return []
        all_requests = self._get_all_requests()
        return [r for r in all_requests if r.owner_prefix == my_prefix]

    def get_outgoing_requests(self) -> List[ClusterShareRequest]:
        my_prefix = self._get_my_prefix()
        if not my_prefix:
            return []
        all_requests = self._get_all_requests()
        return [r for r in all_requests if r.requester_prefix == my_prefix]

    def approve_request(self, request_id: str) -> Optional[ClusterShareRequest]:
        request = self._get_request_by_id(request_id)
        if not request:
            logger.warning(f"Share request {request_id} not found")
            return None

        my_prefix = self._get_my_prefix()
        if request.owner_prefix != my_prefix:
            logger.warning(f"Cannot approve request {request_id}: not the owner")
            return None

        if request.status != ClusterShareRequestStatus.PENDING:
            logger.warning(f"Request {request_id} is not pending (status={request.status})")
            return None

        request.status = ClusterShareRequestStatus.APPROVED
        request.updated_at = datetime.now(timezone.utc).isoformat()
        if self._put_request(request):
            logger.info(f"Approved share request {request_id}")
            return request
        return None

    def deny_request(self, request_id: str) -> Optional[ClusterShareRequest]:
        request = self._get_request_by_id(request_id)
        if not request:
            logger.warning(f"Share request {request_id} not found")
            return None

        my_prefix = self._get_my_prefix()
        if request.owner_prefix != my_prefix:
            logger.warning(f"Cannot deny request {request_id}: not the owner")
            return None

        if request.status != ClusterShareRequestStatus.PENDING:
            logger.warning(f"Request {request_id} is not pending (status={request.status})")
            return None

        request.status = ClusterShareRequestStatus.DENIED
        request.updated_at = datetime.now(timezone.utc).isoformat()
        if self._put_request(request):
            logger.info(f"Denied share request {request_id}")
            return request
        return None

    def get_shared_clusters(self) -> List[SharedCluster]:
        my_prefix = self._get_my_prefix()
        if not my_prefix:
            return []
        all_requests = self._get_all_requests()
        shared: List[SharedCluster] = []
        for r in all_requests:
            if r.requester_prefix == my_prefix and r.status == ClusterShareRequestStatus.APPROVED:
                shared.append(SharedCluster(
                    cluster_name=r.cluster_name,
                    cluster_arn=r.cluster_arn,
                    owner_prefix=r.owner_prefix,
                    shared_at=r.updated_at,
                ))
        return shared

    def get_connected_users(self) -> List[str]:
        my_prefix = self._get_my_prefix()
        if not my_prefix:
            return []
        all_requests = self._get_all_requests()
        users = set()
        for r in all_requests:
            if r.owner_prefix == my_prefix and r.status == ClusterShareRequestStatus.APPROVED:
                users.add(r.requester_prefix)
        return sorted(users)

    def delete_request(self, request_id: str) -> bool:
        request = self._get_request_by_id(request_id)
        if not request:
            return False

        my_prefix = self._get_my_prefix()
        if request.requester_prefix != my_prefix and request.owner_prefix != my_prefix:
            logger.warning(f"Cannot delete request {request_id}: not involved")
            return False

        try:
            param_name = f"{SSM_SHARE_PREFIX}/{request_id}"
            self.ssm_client.delete_parameter(Name=param_name)
            logger.info(f"Deleted share request {request_id}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete share request: {e}")
            return False
