from typing import Dict, List, Optional, Set
from enum import Enum


class VariableType(str, Enum):
    BOOLEAN = "boolean"
    STRING = "string"
    NUMBER = "number"
    LIST = "list"


class ResourceVariableConfig:
    def __init__(self, name: str, var_type: VariableType, default_value=None, description: str = ""):
        self.name = name
        self.var_type = var_type
        self.default_value = default_value
        self.description = description


COMMON_VARIABLES = {
    'vpc_id', 'public_subnet_id', 'public_subnet2_id', 'private_subnet_id',
    'creator', 'team', 'datadog_api_key', 'region',
    'ec2_key_name',
}

ONBOARDING_PHASES = [
    (1, "Creator & team", [
        ("creator", "Creator"),
        ("team", "Team"),
        ("region", "AWS Region"),
    ]),
    (2, "EC2 key pair", [
        ("ec2_key_name", "EC2 Key Pair"),
    ]),
    (3, "VPC configuration", [
        ("vpc_id", "VPC"),
        ("public_subnet_id", "Public Subnet 1"),
        ("public_subnet2_id", "Public Subnet 2"),
        ("private_subnet_id", "Private Subnet"),
    ]),
    (4, "Datadog API Key", [
        ("datadog_api_key", "Datadog API Key"),
    ]),
]

EXCLUDED_VARIABLES = {
    'ec2_key_name',
    'aws_access_key_id',      # Managed via environment variables
    'aws_secret_access_key',  # Managed via environment variables
}

REQUIRED_CONFIG_VARIABLES = [
    ('aws_access_key_id', 'AWS Access Key ID'),
    ('aws_secret_access_key', 'AWS Secret Access Key'),
    ('region', 'AWS Region'),
]

def get_ordered_common_variables() -> List[str]:
    required_names = [name for name, _ in REQUIRED_CONFIG_VARIABLES]
    rest = sorted(COMMON_VARIABLES - set(required_names))
    return required_names + rest


EC2_VARIABLE_CONFIGS = [
    ResourceVariableConfig("ec2_instance_type", VariableType.STRING, "t3.micro", "EC2 instance type (e.g. t3.micro, t3.small, t3.medium)"),
    ResourceVariableConfig("ec2_associate_public_ip", VariableType.BOOLEAN, True, "Associate a public IP address to the instance"),
    ResourceVariableConfig("ec2_root_volume_size", VariableType.NUMBER, 20, "Root EBS volume size in GB"),
    ResourceVariableConfig("ec2_root_volume_type", VariableType.STRING, "gp3", "Root EBS volume type (gp2, gp3, io1, io2)"),
    ResourceVariableConfig("ec2_enable_detailed_monitoring", VariableType.BOOLEAN, False, "Enable detailed (1-minute) CloudWatch monitoring"),
]

EC2_WINDOWS_EXTRA_CONFIGS = [
    ResourceVariableConfig("ec2_get_password_data", VariableType.BOOLEAN, False, "Retrieve Windows password data (for Windows AMIs only)"),
]

DATADOG_DOCKER_AGENT_CONFIGS = [
    ResourceVariableConfig("datadog_agent_image", VariableType.STRING, "gcr.io/datadoghq/agent:latest", "Datadog Agent Docker image (e.g. gcr.io/datadoghq/agent:7.72.1)"),
]

DATADOG_HOST_AGENT_CONFIGS = [
    ResourceVariableConfig("datadog_agent_version", VariableType.STRING, "latest", "Datadog Agent minor version (e.g. 65.0 for 7.65.0)"),
]

RESOURCE_VARIABLE_CONFIGS: Dict[str, List[ResourceVariableConfig]] = {
    "ec2": EC2_VARIABLE_CONFIGS,
    "ec2_windows": EC2_VARIABLE_CONFIGS + EC2_WINDOWS_EXTRA_CONFIGS,
    "ec2_datadog_docker": EC2_VARIABLE_CONFIGS + DATADOG_DOCKER_AGENT_CONFIGS,
    "ec2_datadog_host": EC2_VARIABLE_CONFIGS + DATADOG_HOST_AGENT_CONFIGS,
    "ec2_forwardog": EC2_VARIABLE_CONFIGS + DATADOG_DOCKER_AGENT_CONFIGS,
    
    "eks": [
        ResourceVariableConfig("eks_enable_node_group", VariableType.BOOLEAN, True, "Enable Linux node group for EKS cluster"),
        ResourceVariableConfig("eks_node_instance_type", VariableType.STRING, "t3.medium", "Instance type for EKS Linux nodes"),
        ResourceVariableConfig("eks_node_desired_size", VariableType.NUMBER, 2, "Desired number of EKS Linux nodes"),
        ResourceVariableConfig("eks_node_min_size", VariableType.NUMBER, 1, "Minimum number of EKS Linux nodes"),
        ResourceVariableConfig("eks_node_max_size", VariableType.NUMBER, 4, "Maximum number of EKS Linux nodes"),
        ResourceVariableConfig("eks_enable_windows_node_group", VariableType.BOOLEAN, False, "Enable Windows node group for EKS cluster"),
        ResourceVariableConfig("eks_windows_node_instance_type", VariableType.STRING, "t3.medium", "Instance type for EKS Windows nodes"),
        ResourceVariableConfig("eks_windows_node_desired_size", VariableType.NUMBER, 2, "Desired number of EKS Windows nodes"),
        ResourceVariableConfig("eks_enable_fargate", VariableType.BOOLEAN, False, "Enable Fargate for EKS cluster"),
    ],
    
    "ecs": [
        ResourceVariableConfig("ecs_enable_fargate", VariableType.BOOLEAN, True, "Enable Fargate launch type for ECS"),
        ResourceVariableConfig("ecs_enable_ec2", VariableType.BOOLEAN, False, "Enable EC2 launch type for ECS"),
        ResourceVariableConfig("ecs_task_cpu", VariableType.STRING, "256", "CPU units for ECS task (256, 512, 1024, 2048, 4096)"),
        ResourceVariableConfig("ecs_task_memory", VariableType.STRING, "512", "Memory for ECS task in MB (512, 1024, 2048, etc)"),
    ],
    
    "rds": [
        ResourceVariableConfig("rds_instance_class", VariableType.STRING, "db.t3.micro", "RDS instance class"),
        ResourceVariableConfig("rds_username", VariableType.STRING, "dbadmin", "Master username for RDS instance"),
        ResourceVariableConfig("rds_password", VariableType.STRING, "", "Master password for RDS instance"),
        ResourceVariableConfig("rds_allocated_storage", VariableType.NUMBER, 20, "Allocated storage in GB"),
    ],
    
    "lambda": [
        ResourceVariableConfig("lambda_runtime", VariableType.STRING, "python3.11", "Lambda function runtime"),
        ResourceVariableConfig("lambda_memory_size", VariableType.NUMBER, 128, "Lambda function memory in MB"),
        ResourceVariableConfig("lambda_timeout", VariableType.NUMBER, 30, "Lambda function timeout in seconds"),
    ],
    
    "dbm": [
        ResourceVariableConfig("dbm_postgres_datadog_password", VariableType.STRING, "", "Datadog password for DBM Postgres monitoring"),
    ] + DATADOG_HOST_AGENT_CONFIGS,
}


def get_resource_type_for_variables(resource_type: str, resource_id: str) -> str:
    if resource_type == "ec2" and resource_id.startswith("ec2_windows"):
        return "ec2_windows"
    if resource_type == "ec2" and resource_id == "ec2_forwardog":
        return "ec2_forwardog"
    if resource_type == "ec2" and resource_id == "ec2_datadog_docker":
        return "ec2_datadog_docker"
    if resource_type == "ec2" and resource_id == "ec2_datadog_host":
        return "ec2_datadog_host"
    return resource_type


def get_resource_variables(resource_type: str, resource_id: Optional[str] = None) -> List[ResourceVariableConfig]:
    effective_type = get_resource_type_for_variables(resource_type, resource_id or "") if resource_id else resource_type
    return RESOURCE_VARIABLE_CONFIGS.get(effective_type, [])


def get_variable_names_for_resource(resource_type: str, resource_id: Optional[str] = None) -> Set[str]:
    configs = get_resource_variables(resource_type, resource_id)
    return {config.name for config in configs}


def get_resource_only_variable_names() -> Set[str]:
    out: Set[str] = set()
    for configs in RESOURCE_VARIABLE_CONFIGS.values():
        for c in configs:
            if c.name not in COMMON_VARIABLES:
                out.add(c.name)
    return out


def get_root_allowed_variable_names() -> Set[str]:
    return set(COMMON_VARIABLES)


def is_common_variable(var_name: str) -> bool:
    return var_name in COMMON_VARIABLES


def is_excluded_variable(var_name: str) -> bool:
    return var_name in EXCLUDED_VARIABLES
