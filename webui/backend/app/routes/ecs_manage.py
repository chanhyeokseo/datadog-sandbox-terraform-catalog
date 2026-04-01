import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse

from app.models.schemas import ResourceType
from app.services.ecs_preset_manager import ECSPresetManager
from app.services.terraform_parser import TerraformParser
from app.services.terraform_runner import TerraformRunner
from app.services.instance_discovery import get_resource_id_for_instance, get_resource_type_from_dir

router = APIRouter(prefix="/api/terraform/ecs/manage", tags=["ecs-manage"])
logger = logging.getLogger(__name__)

TERRAFORM_DIR = os.environ.get("TERRAFORM_DIR", "/terraform")
EXIT_SENTINEL_PREFIX = "__TF_EXIT__:"

preset_manager = ECSPresetManager(TERRAFORM_DIR)
parser = TerraformParser(TERRAFORM_DIR)
runner = TerraformRunner(TERRAFORM_DIR)

_deploy_lock = asyncio.Lock()
_TEMPLATE_RE = re.compile(r'\{\{(\w+)\}\}')
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')


def _get_ecs_resource_info() -> tuple[Optional[str], Optional[Path]]:
    instances_dir = Path(TERRAFORM_DIR) / "instances"
    if not instances_dir.exists():
        return None, None
    for instance_dir in sorted(instances_dir.iterdir()):
        if not instance_dir.is_dir() or not (instance_dir / "main.tf").exists():
            continue
        if get_resource_type_from_dir(instance_dir.name) != ResourceType.ECS:
            continue
        resource_id = get_resource_id_for_instance(instance_dir)
        return resource_id, instance_dir
    return None, None


def _parse_cluster_info(outputs: Dict) -> Dict:
    result = {}
    for key, val in outputs.items():
        value = val.get("value", "") if isinstance(val, dict) else str(val)
        if not value:
            continue
        result[key.lower()] = str(value)

    subnet_ids = []
    sg_ids = []
    for key, val in outputs.items():
        raw = val.get("value", "") if isinstance(val, dict) else val
        if key.lower() == "subnet_ids" and isinstance(raw, list):
            subnet_ids = [str(s) for s in raw]
        elif key.lower() == "security_group_ids" and isinstance(raw, list):
            sg_ids = [str(s) for s in raw]

    return {
        "cluster_name": result.get("cluster_name"),
        "cluster_arn": result.get("cluster_arn"),
        "region": result.get("region") or os.environ.get("AWS_REGION", "ap-northeast-2"),
        "task_execution_role_arn": result.get("task_execution_role_arn"),
        "task_role_arn": result.get("task_role_arn"),
        "subnet_ids": subnet_ids,
        "security_group_ids": sg_ids,
    }


async def _get_cluster_info_async(resource_id: str, resource_dir: Path) -> Dict:
    try:
        aws_env = parser.get_aws_env()
        await runner.ensure_terraform_init(resource_dir, env_extra=aws_env)
        success, raw_output = await runner.output(resource_id, env_extra=aws_env)
        if success and raw_output:
            outputs = json.loads(raw_output)
            return _parse_cluster_info(outputs)
    except Exception as e:
        logger.warning(f"Failed to get ECS cluster info: {e}")
    return {}


def _resolve_template_vars(command: str, extra_vars: Dict = None) -> str:
    root_tfvars = parser._read_tfvars_to_map(Path(TERRAFORM_DIR) / "terraform.tfvars")
    sensitive_vars = parser.config_manager.load_all_sensitive_variables()
    merged = {**root_tfvars, **sensitive_vars, **(extra_vars or {})}

    def _replacer(m):
        var_name = m.group(1)
        val = merged.get(var_name)
        if val is None:
            logger.warning(f"Template variable '{var_name}' not found")
            return m.group(0)
        return val.strip('"').strip("'")
    return _TEMPLATE_RE.sub(_replacer, command)


async def _stream_shell(cmd_str: str, cwd: str = None, env_extra: Dict = None) -> AsyncIterator[str]:
    try:
        env = {**os.environ, **(env_extra or {})}
        process = await asyncio.create_subprocess_shell(
            cmd_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
            env=env,
        )
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            yield _ANSI_RE.sub('', line.decode())
        code = (await process.wait()) or 0
        yield f"{EXIT_SENTINEL_PREFIX}{0 if code == 0 else 1}\n"
    except Exception as e:
        yield f"Error: {str(e)}\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"



async def _setup_ecs_env(resource_id: Optional[str],
                         resource_dir: Optional[Path]) -> tuple[Dict, list[str]]:
    lines = []
    extra_vars = {}

    root_tfvars = parser._read_tfvars_to_map(Path(TERRAFORM_DIR) / "terraform.tfvars")
    for key, val in root_tfvars.items():
        clean_val = val.strip('"').strip("'")
        extra_vars[key] = clean_val

    sensitive_vars = parser.config_manager.load_all_sensitive_variables()
    extra_vars.update(sensitive_vars)

    if resource_dir and resource_id:
        lines.append("Resolving ECS cluster info from Terraform outputs...\n")
        cluster_info = await _get_cluster_info_async(resource_id, resource_dir)
        cluster_name = cluster_info.get("cluster_name")
        region = cluster_info.get("region")

        if cluster_name:
            lines.append(f"Cluster: {cluster_name} (region: {region})\n")
            extra_vars["cluster_name"] = cluster_name
            extra_vars["ecs_cluster_name"] = cluster_name
            if region:
                extra_vars["ecs_region"] = region
            for k in ("task_execution_role_arn", "task_role_arn"):
                if cluster_info.get(k):
                    extra_vars[k] = cluster_info[k]
        else:
            lines.append("Warning: Could not resolve cluster name from outputs.\n")
    else:
        lines.append("Warning: ECS resource not found.\n")

    return extra_vars, lines


def _read_td_json(preset_dir: Path, extra_vars: Dict) -> Dict:
    td_path = preset_dir / "task-definition.json"
    raw = td_path.read_text()
    for placeholder in ("__DATADOG_API_KEY__",):
        var_name = placeholder.strip("_").lower()
        val = extra_vars.get(var_name, "")
        if val:
            raw = raw.replace(placeholder, val)
    return json.loads(raw)


def _boto3_register_td(td: Dict, cluster_name: str, cluster_info: Dict, region: str) -> Dict:
    import boto3
    client = boto3.client("ecs", region_name=region)

    params = {
        "family": f"{cluster_name}-{td['family']}",
        "containerDefinitions": td["containerDefinitions"],
    }

    if td.get("networkMode"):
        params["networkMode"] = td["networkMode"]
    if td.get("requiresCompatibilities"):
        params["requiresCompatibilities"] = td["requiresCompatibilities"]
    if td.get("cpu"):
        params["cpu"] = str(td["cpu"])
    if td.get("memory"):
        params["memory"] = str(td["memory"])
    if td.get("pidMode"):
        params["pidMode"] = td["pidMode"]
    if td.get("volumes"):
        params["volumes"] = td["volumes"]

    exec_role = cluster_info.get("task_execution_role_arn")
    if exec_role:
        params["executionRoleArn"] = exec_role
    task_role = cluster_info.get("task_role_arn")
    if task_role:
        params["taskRoleArn"] = task_role

    resp = client.register_task_definition(**params)
    return resp["taskDefinition"]


def _boto3_create_service(td_arn: str, td: Dict, cluster_name: str,
                          cluster_info: Dict, region: str, preset_name: str) -> Dict:
    import boto3
    client = boto3.client("ecs", region_name=region)

    is_fargate = "FARGATE" in td.get("requiresCompatibilities", [])
    service_name = f"{cluster_name}-{td['family']}"

    params = {
        "cluster": cluster_name,
        "serviceName": service_name,
        "taskDefinition": td_arn,
        "launchType": "FARGATE" if is_fargate else "EC2",
        "tags": [{"key": "preset", "value": preset_name}],
    }

    if is_fargate:
        params["desiredCount"] = 1
        subnet_ids = cluster_info.get("subnet_ids", [])
        sg_ids = cluster_info.get("security_group_ids", [])
        params["networkConfiguration"] = {
            "awsvpcConfiguration": {
                "subnets": subnet_ids,
                "securityGroups": sg_ids,
                "assignPublicIp": "ENABLED",
            }
        }
    else:
        params["schedulingStrategy"] = "DAEMON"

    return client.create_service(**params)


def _boto3_update_service(td_arn: str, td: Dict, cluster_name: str,
                          cluster_info: Dict, region: str) -> Dict:
    import boto3
    client = boto3.client("ecs", region_name=region)

    service_name = f"{cluster_name}-{td['family']}"
    is_fargate = "FARGATE" in td.get("requiresCompatibilities", [])

    params = {
        "cluster": cluster_name,
        "service": service_name,
        "taskDefinition": td_arn,
    }
    if is_fargate:
        subnet_ids = cluster_info.get("subnet_ids", [])
        sg_ids = cluster_info.get("security_group_ids", [])
        params["networkConfiguration"] = {
            "awsvpcConfiguration": {
                "subnets": subnet_ids,
                "securityGroups": sg_ids,
                "assignPublicIp": "ENABLED",
            }
        }
    return client.update_service(**params)


def _boto3_delete_service(td_family: str, cluster_name: str, region: str) -> None:
    import boto3
    client = boto3.client("ecs", region_name=region)
    service_name = f"{cluster_name}-{td_family}"

    try:
        client.update_service(cluster=cluster_name, service=service_name, desiredCount=0)
    except Exception:
        pass
    try:
        client.delete_service(cluster=cluster_name, service=service_name, force=True)
    except Exception as e:
        logger.warning(f"delete_service failed: {e}")

    paginator = client.get_paginator("list_task_definitions")
    for page in paginator.paginate(familyPrefix=f"{cluster_name}-{td_family}", status="ACTIVE"):
        for arn in page.get("taskDefinitionArns", []):
            try:
                client.deregister_task_definition(taskDefinition=arn)
            except Exception:
                pass


async def _stream_boto3_deploy(name: str, resource_id: Optional[str],
                               resource_dir: Optional[Path]) -> AsyncIterator[str]:
    yield f"=== ECS Preset Deploy ===\n"
    yield f"Preset: {name}\n\n"

    from app.init_config import ensure_terraform_data
    try:
        result = await asyncio.to_thread(ensure_terraform_data)
        if result.get("recovered"):
            yield "Configuration restored from S3.\n"
    except Exception as e:
        logger.warning(f"ensure_terraform_data failed: {e}")

    if not preset_manager._cache_initialized:
        yield "Syncing preset cache from S3...\n"
        await asyncio.to_thread(preset_manager.initialize_local_cache)

    extra_vars, lines = await _setup_ecs_env(resource_id, resource_dir)
    for line in lines:
        yield line

    cluster_name = extra_vars.get("cluster_name")
    region = extra_vars.get("ecs_region") or extra_vars.get("region")
    if not cluster_name or not region:
        yield "Error: Could not resolve cluster name or region\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    preset_dir = preset_manager.sync_preset_to_local(name)
    if not preset_dir:
        yield "Error: Failed to sync preset files\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    try:
        td = _read_td_json(preset_dir, extra_vars)
    except Exception as e:
        yield f"Error reading task-definition.json: {e}\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    cluster_info = await _get_cluster_info_async(resource_id, resource_dir)
    is_fargate = "FARGATE" in td.get("requiresCompatibilities", [])
    yield f"\nFamily: {td['family']} ({'Fargate' if is_fargate else 'EC2'})\n"

    yield "\nRegistering task definition...\n"
    try:
        td_result = await asyncio.to_thread(
            _boto3_register_td, td, cluster_name, cluster_info, region)
        td_arn = td_result["taskDefinitionArn"]
        yield f"  -> {td_arn}\n"
    except Exception as e:
        yield f"Error registering task definition: {e}\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    yield "\nCreating service...\n"
    try:
        await asyncio.to_thread(
            _boto3_create_service, td_arn, td, cluster_name, cluster_info, region, name)
        yield f"  -> Service: {cluster_name}-{td['family']}\n"
    except Exception as e:
        yield f"Error creating service: {e}\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    yield "\nDeploy complete.\n"
    try:
        preset_manager.mark_deployed(name)
    except Exception as e:
        logger.warning(f"mark_deployed failed: {e}")
    yield f"{EXIT_SENTINEL_PREFIX}0\n"


async def _stream_boto3_update(name: str, resource_id: Optional[str],
                               resource_dir: Optional[Path]) -> AsyncIterator[str]:
    yield f"=== ECS Preset Update ===\n"
    yield f"Preset: {name}\n\n"

    from app.init_config import ensure_terraform_data
    try:
        await asyncio.to_thread(ensure_terraform_data)
    except Exception:
        pass

    if not preset_manager._cache_initialized:
        await asyncio.to_thread(preset_manager.initialize_local_cache)

    extra_vars, lines = await _setup_ecs_env(resource_id, resource_dir)
    for line in lines:
        yield line

    cluster_name = extra_vars.get("cluster_name")
    region = extra_vars.get("ecs_region") or extra_vars.get("region")
    if not cluster_name or not region:
        yield "Error: Could not resolve cluster name or region\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    preset_dir = preset_manager.sync_preset_to_local(name)
    if not preset_dir:
        yield "Error: Failed to sync preset files\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    try:
        td = _read_td_json(preset_dir, extra_vars)
    except Exception as e:
        yield f"Error reading task-definition.json: {e}\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    cluster_info = await _get_cluster_info_async(resource_id, resource_dir)

    yield "\nRegistering new task definition revision...\n"
    try:
        td_result = await asyncio.to_thread(
            _boto3_register_td, td, cluster_name, cluster_info, region)
        td_arn = td_result["taskDefinitionArn"]
        yield f"  -> {td_arn}\n"
    except Exception as e:
        yield f"Error registering task definition: {e}\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    yield "\nUpdating service...\n"
    try:
        await asyncio.to_thread(
            _boto3_update_service, td_arn, td, cluster_name, cluster_info, region)
        yield f"  -> Service updated: {cluster_name}-{td['family']}\n"
    except Exception as e:
        yield f"Error updating service: {e}\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    yield "\nUpdate complete.\n"
    yield f"{EXIT_SENTINEL_PREFIX}0\n"


async def _stream_boto3_undeploy(name: str, resource_id: Optional[str],
                                 resource_dir: Optional[Path]) -> AsyncIterator[str]:
    yield f"=== ECS Preset Undeploy ===\n"
    yield f"Preset: {name}\n\n"

    from app.init_config import ensure_terraform_data
    try:
        await asyncio.to_thread(ensure_terraform_data)
    except Exception:
        pass

    if not preset_manager._cache_initialized:
        await asyncio.to_thread(preset_manager.initialize_local_cache)

    extra_vars, lines = await _setup_ecs_env(resource_id, resource_dir)
    for line in lines:
        yield line

    cluster_name = extra_vars.get("cluster_name")
    region = extra_vars.get("ecs_region") or extra_vars.get("region")
    if not cluster_name or not region:
        yield "Error: Could not resolve cluster name or region\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    preset_dir = preset_manager.sync_preset_to_local(name)
    if not preset_dir:
        yield "Error: Failed to sync preset files\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    try:
        td = _read_td_json(preset_dir, extra_vars)
    except Exception as e:
        yield f"Error reading task-definition.json: {e}\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    td_family = td["family"]
    yield f"\nRemoving service: {cluster_name}-{td_family}\n"
    try:
        await asyncio.to_thread(
            _boto3_delete_service, td_family, cluster_name, region)
        yield "  -> Service deleted\n"
    except Exception as e:
        yield f"Error deleting service: {e}\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    yield "\nUndeploy complete.\n"
    try:
        preset_manager.mark_undeployed(name)
    except Exception as e:
        logger.warning(f"mark_undeployed failed: {e}")
    yield f"{EXIT_SENTINEL_PREFIX}0\n"


@router.post("/presets/refresh")
async def refresh_presets():
    try:
        preset_manager.refresh_from_s3()
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to refresh presets from S3: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/layout")
async def get_layout():
    try:
        layout = preset_manager.get_layout()
        return {"layout": layout}
    except Exception as e:
        logger.error(f"Failed to get layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/layout")
async def save_layout(body: dict = Body(...)):
    layout = body.get("layout")
    if layout is None:
        raise HTTPException(status_code=400, detail="layout is required")
    success = preset_manager.save_layout(layout)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save layout")
    return {"success": True}


@router.get("/presets")
async def list_presets():
    try:
        presets = preset_manager.list_presets()
        return {"presets": presets}
    except Exception as e:
        logger.error(f"Failed to list presets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/presets/{name}")
async def get_preset(name: str):
    preset = preset_manager.get_preset(name)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")
    return preset


@router.get("/presets/{name}/files/{filename:path}")
async def get_preset_file(name: str, filename: str):
    content = preset_manager.get_preset_file(name, filename)
    if content is None:
        raise HTTPException(status_code=404, detail=f"File not found: {name}/{filename}")
    return {"filename": filename, "content": content}


@router.post("/presets")
async def create_preset(body: dict = Body(...)):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset name is required")
    if not all(c.isalnum() or c in "-_." for c in name):
        raise HTTPException(status_code=400, detail="Preset name must be alphanumeric with hyphens, underscores, or dots only")

    existing = preset_manager.get_preset(name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Preset already exists: {name}")

    success = preset_manager.create_preset(
        name=name,
        description=body.get("description", ""),
        preset_type=body.get("type", "aws-ecs"),
        deploy_commands=body.get("deploy_commands", []),
        update_commands=body.get("update_commands", []),
        undeploy_commands=body.get("undeploy_commands", []),
        files=body.get("files", {}),
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create preset")
    return {"success": True, "name": name}


@router.put("/presets/{name}/files/{filename:path}")
async def update_preset_file(name: str, filename: str, body: dict = Body(...)):
    content = body.get("content")
    if content is None:
        raise HTTPException(status_code=400, detail="Content is required")

    preset = preset_manager.get_preset(name)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")
    if preset.get("built_in"):
        raise HTTPException(status_code=403, detail="OOTB presets are read-only. Clone it first.")

    success = preset_manager.save_preset_file(name, filename, content)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save file")

    if filename not in preset.get("files", []):
        preset["files"] = sorted(set(preset.get("files", []) + [filename]))
        preset_manager.save_preset(name, preset)

    return {"success": True}


@router.put("/presets/{name}")
async def update_preset_manifest(name: str, body: dict = Body(...)):
    preset = preset_manager.get_preset(name)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")
    if preset.get("built_in"):
        raise HTTPException(status_code=403, detail="OOTB presets are read-only. Clone it first.")

    for key in ("description", "type", "deploy_commands", "update_commands", "undeploy_commands"):
        if key in body:
            preset[key] = body[key]

    success = preset_manager.save_preset(name, preset)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update preset")
    return {"success": True}


@router.post("/presets/{name}/clone")
async def clone_preset(name: str, body: dict = Body(...)):
    target_name = body.get("target_name", "").strip()
    if not target_name:
        raise HTTPException(status_code=400, detail="target_name is required")
    if not all(c.isalnum() or c in "-_." for c in target_name):
        raise HTTPException(status_code=400, detail="target_name must be alphanumeric with hyphens, underscores, or dots only")

    existing = preset_manager.get_preset(target_name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Preset already exists: {target_name}")

    success = preset_manager.clone_preset(name, target_name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clone preset")
    return {"success": True, "name": target_name}


@router.delete("/presets/{name}")
async def delete_preset(name: str):
    preset = preset_manager.get_preset(name)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")
    if preset.get("built_in"):
        raise HTTPException(status_code=403, detail="Cannot delete OOTB preset")

    success = preset_manager.delete_preset(name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete preset")
    return {"success": True}


@router.get("/deployments")
async def get_deployments():
    try:
        return {"deployments": preset_manager.get_deployments()}
    except Exception as e:
        logger.error(f"Failed to get deployments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/presets/{name}/deploy")
async def deploy_preset(name: str):
    preset = preset_manager.get_preset(name)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")

    resource_id, resource_dir = _get_ecs_resource_info()
    return StreamingResponse(
        _stream_boto3_deploy(name, resource_id, resource_dir),
        media_type="text/plain",
    )


@router.post("/presets/{name}/update")
async def update_preset_deploy(name: str):
    preset = preset_manager.get_preset(name)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")

    resource_id, resource_dir = _get_ecs_resource_info()
    return StreamingResponse(
        _stream_boto3_update(name, resource_id, resource_dir),
        media_type="text/plain",
    )


@router.post("/presets/{name}/undeploy")
async def undeploy_preset(name: str):
    preset = preset_manager.get_preset(name)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")

    resource_id, resource_dir = _get_ecs_resource_info()
    return StreamingResponse(
        _stream_boto3_undeploy(name, resource_id, resource_dir),
        media_type="text/plain",
    )


@router.post("/presets/{name}/force-delete")
async def force_delete_preset(name: str):
    preset_manager.mark_undeployed(name)
    return {"success": True, "message": f"Preset '{name}' removed from deployed list"}


ECS_API_ACTIONS = {
    "list-services": lambda c, p: c.list_services(**p),
    "list-tasks": lambda c, p: c.list_tasks(**p),
    "describe-clusters": lambda c, p: c.describe_clusters(**p),
    "describe-services": lambda c, p: c.describe_services(**p),
    "describe-tasks": lambda c, p: c.describe_tasks(**p),
    "list-task-definitions": lambda c, p: c.list_task_definitions(**p),
    "list-container-instances": lambda c, p: c.list_container_instances(**p),
    "describe-container-instances": lambda c, p: c.describe_container_instances(**p),
    "describe-task-definition": lambda c, p: c.describe_task_definition(**p),
    "list-clusters": lambda c, p: c.list_clusters(**p),
}


def _parse_ecs_command(command: str) -> tuple[str, Dict]:
    tokens = command.split()
    if len(tokens) < 3 or tokens[0] != "aws" or tokens[1] != "ecs":
        raise ValueError("Command must start with 'aws ecs <action>'")

    action = tokens[2]
    if action not in ECS_API_ACTIONS:
        raise ValueError(f"Unsupported action: {action}. Supported: {', '.join(sorted(ECS_API_ACTIONS))}")

    params: Dict = {}
    i = 3
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("--"):
            key = token[2:]
            parts = key.split("-")
            camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                i += 1
                val = tokens[i]
                if camel in params:
                    existing = params[camel]
                    if isinstance(existing, list):
                        existing.append(val)
                    else:
                        params[camel] = [existing, val]
                else:
                    params[camel] = val
            else:
                params[camel] = True
        i += 1

    for key in ("services", "tasks", "clusters", "containerInstances"):
        if key in params and isinstance(params[key], str):
            params[key] = [params[key]]

    return action, params


def _run_ecs_boto3(action: str, params: Dict, region: str) -> str:
    import boto3
    client = boto3.client("ecs", region_name=region)
    handler = ECS_API_ACTIONS[action]
    response = handler(client, params)
    response.pop("ResponseMetadata", None)
    return json.dumps(response, indent=2, default=str)


@router.post("/run")
async def run_command(body: dict = Body(...)):
    command = body.get("command", "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="command is required")

    resource_id, resource_dir = _get_ecs_resource_info()

    async def _stream():
        extra_vars, lines = await _setup_ecs_env(resource_id, resource_dir)
        for line in lines:
            yield line

        resolved = _resolve_template_vars(command, extra_vars)
        yield f"$ {command}\n\n"

        if resolved.startswith("aws ecs "):
            try:
                action, params = _parse_ecs_command(resolved)
                region = extra_vars.get("region", extra_vars.get("ecs_region", "ap-northeast-2"))
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, _run_ecs_boto3, action, params, region)
                yield result + "\n"
                yield f"{EXIT_SENTINEL_PREFIX}0\n"
            except Exception as e:
                yield f"Error: {e}\n"
                yield f"{EXIT_SENTINEL_PREFIX}1\n"
        elif resolved.split()[0] == "terraform":
            async for line in _stream_shell(resolved, env_extra=extra_vars):
                yield line
        else:
            yield f"Error: Only 'aws ecs' and 'terraform' commands are supported.\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"

    return StreamingResponse(_stream(), media_type="text/plain")


@router.get("/cluster-status")
async def cluster_status():
    resource_id, resource_dir = _get_ecs_resource_info()
    if not resource_dir:
        return {"configured": False, "cluster_name": None, "message": "ECS resource not found"}

    cluster_info = await _get_cluster_info_async(resource_id, resource_dir)
    cluster_name = cluster_info.get("cluster_name")
    if not cluster_name:
        return {"configured": False, "cluster_name": None, "message": "Cluster not deployed or outputs unavailable"}

    return {
        "configured": True,
        "cluster_name": cluster_name,
        "cluster_arn": cluster_info.get("cluster_arn"),
        "region": cluster_info.get("region"),
    }


def _list_ecs_container_instances(cluster_name: str, region: str) -> List[Dict]:
    import boto3
    session = boto3.Session(region_name=region)
    ecs = session.client("ecs")
    ec2 = session.client("ec2")

    ci_arns = []
    paginator = ecs.get_paginator("list_container_instances")
    for page in paginator.paginate(cluster=cluster_name):
        ci_arns.extend(page.get("containerInstanceArns", []))

    if not ci_arns:
        return []

    ci_resp = ecs.describe_container_instances(cluster=cluster_name, containerInstances=ci_arns)
    ec2_ids = [ci["ec2InstanceId"] for ci in ci_resp.get("containerInstances", []) if ci.get("ec2InstanceId")]

    if not ec2_ids:
        return []

    ec2_resp = ec2.describe_instances(InstanceIds=ec2_ids)
    instances = []
    for reservation in ec2_resp.get("Reservations", []):
        for inst in reservation.get("Instances", []):
            name_tag = ""
            for tag in inst.get("Tags", []):
                if tag["Key"] == "Name":
                    name_tag = tag["Value"]
                    break
            instances.append({
                "instance_id": inst["InstanceId"],
                "name": name_tag,
                "private_ip": inst.get("PrivateIpAddress", ""),
                "public_ip": inst.get("PublicIpAddress", ""),
                "state": inst.get("State", {}).get("Name", "unknown"),
                "instance_type": inst.get("InstanceType", ""),
            })

    return instances


def _check_active_workloads(cluster_name: str, region: str) -> Dict:
    import boto3
    client = boto3.client("ecs", region_name=region)

    active_services = []
    try:
        paginator = client.get_paginator("list_services")
        service_arns = []
        for page in paginator.paginate(cluster=cluster_name):
            service_arns.extend(page.get("serviceArns", []))
        for i in range(0, len(service_arns), 10):
            batch = service_arns[i:i+10]
            desc = client.describe_services(cluster=cluster_name, services=batch)
            for svc in desc.get("services", []):
                if svc.get("status") != "ACTIVE":
                    continue
                active_services.append({
                    "name": svc.get("serviceName", ""),
                    "status": svc.get("status", ""),
                    "running": svc.get("runningCount", 0),
                    "desired": svc.get("desiredCount", 0),
                })
    except Exception as e:
        logger.warning(f"Failed to list services: {e}")

    running_tasks = 0
    try:
        resp = client.list_tasks(cluster=cluster_name, desiredStatus="RUNNING")
        running_tasks = len(resp.get("taskArns", []))
    except Exception as e:
        logger.warning(f"Failed to list tasks: {e}")

    deployed_presets = []
    try:
        deployments = preset_manager.get_deployments()
        deployed_presets = [name for name, info in deployments.items()
                           if info.get("status") == "deployed"]
    except Exception:
        pass

    has_active = len(active_services) > 0 or running_tasks > 0

    return {
        "has_active": has_active,
        "services": active_services,
        "running_tasks": running_tasks,
        "deployed_presets": deployed_presets,
    }


@router.get("/has-active-workloads")
async def has_active_workloads():
    resource_id, resource_dir = _get_ecs_resource_info()
    if not resource_dir:
        return {"has_active": False, "services": [], "running_tasks": 0, "deployed_presets": []}

    cluster_info = await _get_cluster_info_async(resource_id, resource_dir)
    cluster_name = cluster_info.get("cluster_name")
    region = cluster_info.get("region")
    if not cluster_name:
        return {"has_active": False, "services": [], "running_tasks": 0, "deployed_presets": []}

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _check_active_workloads, cluster_name, region)
        return result
    except Exception as e:
        logger.error(f"Failed to check active workloads: {e}")
        return {"has_active": False, "services": [], "running_tasks": 0, "deployed_presets": [], "error": str(e)}


@router.get("/container-instances")
async def get_container_instances():
    resource_id, resource_dir = _get_ecs_resource_info()
    if not resource_dir:
        raise HTTPException(status_code=404, detail="ECS resource not found")

    cluster_info = await _get_cluster_info_async(resource_id, resource_dir)
    cluster_name = cluster_info.get("cluster_name")
    region = cluster_info.get("region")
    if not cluster_name:
        raise HTTPException(status_code=404, detail="Cluster not deployed or outputs unavailable")

    try:
        loop = asyncio.get_event_loop()
        instances = await loop.run_in_executor(
            None, _list_ecs_container_instances, cluster_name, region
        )
        return {"cluster_name": cluster_name, "region": region, "instances": instances}
    except Exception as e:
        logger.error(f"Failed to list container instances: {e}")
        raise HTTPException(status_code=500, detail=str(e))
