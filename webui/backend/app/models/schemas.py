from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum


class ResourceType(str, Enum):
    EC2 = "ec2"
    RDS = "rds"
    EKS = "eks"
    ECS = "ecs"
    ECR = "ecr"
    LAMBDA = "lambda"
    DBM = "dbm"
    TEST = "test"
    SECURITY_GROUP = "security_group"


class ResourceStatus(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class TerraformResource(BaseModel):
    id: str
    name: str
    type: ResourceType
    file_path: str
    line_start: int
    line_end: int
    status: ResourceStatus
    description: Optional[str] = None


class TerraformVariable(BaseModel):
    name: str
    value: Optional[str] = None
    description: Optional[str] = None
    sensitive: bool = False
    is_common: bool = False  # True for global config variables


class TerraformApplyRequest(BaseModel):
    resources: List[str]  # List of resource IDs to enable
    auto_approve: bool = False


class TerraformPlanResponse(BaseModel):
    success: bool
    output: str
    changes: Optional[Dict[str, Any]] = None


class TerraformApplyResponse(BaseModel):
    success: bool
    output: str
    error: Optional[str] = None


class TerraformStateResponse(BaseModel):
    resources: List[TerraformResource]
    variables: List[TerraformVariable]
