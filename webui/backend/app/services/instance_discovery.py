import re
from pathlib import Path
from typing import Dict

from app.models.schemas import ResourceType


def get_resource_id_for_instance(instance_dir: Path) -> str:
    rid_file = instance_dir / ".resource_id"
    if rid_file.exists():
        return rid_file.read_text().strip()
    main_tf = instance_dir / "main.tf"
    if not main_tf.exists():
        return instance_dir.name.replace("-", "_")
    with open(main_tf, "r", encoding="utf-8") as f:
        for line in f:
            match = re.match(r'^module\s+"([^"]+)"\s*\{', line.strip())
            if match:
                return match.group(1)
    return instance_dir.name.replace("-", "_")


def get_resource_type_from_dir(dir_name: str) -> ResourceType:
    if dir_name == "shared":
        return ResourceType.SECURITY_GROUP
    if dir_name.startswith("ec2-"):
        return ResourceType.EC2
    if dir_name.startswith("eks-"):
        return ResourceType.EKS
    if dir_name.startswith("ecs-"):
        return ResourceType.ECS
    if dir_name.startswith("lambda-"):
        return ResourceType.LAMBDA
    if dir_name.startswith("dbm-"):
        return ResourceType.DBM
    if dir_name.startswith("ecr-") or dir_name == "deploy-spring-boot":
        return ResourceType.ECR
    if dir_name.startswith("test-file-"):
        return ResourceType.TEST
    return ResourceType.EC2


def get_resource_directory_map(instances_dir: Path) -> Dict[str, str]:
    result = {}
    if not instances_dir.exists():
        return result
    for d in sorted(instances_dir.iterdir()):
        if not d.is_dir() or not (d / "main.tf").exists():
            continue
        resource_id = get_resource_id_for_instance(d)
        result[resource_id] = d.name
    return result
