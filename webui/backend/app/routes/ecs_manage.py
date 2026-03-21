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

    return {
        "cluster_name": result.get("cluster_name"),
        "cluster_arn": result.get("cluster_arn"),
        "region": result.get("region") or os.environ.get("AWS_REGION", "ap-northeast-2"),
        "task_execution_role_arn": result.get("task_execution_role_arn"),
        "task_role_arn": result.get("task_role_arn"),
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
    merged = {**root_tfvars, **(extra_vars or {})}

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


async def _execute_commands(commands: List[str], preset_dir: str,
                            extra_vars: Dict = None) -> AsyncIterator[str]:
    for cmd_str in commands:
        cmd_str = cmd_str.strip()
        if not cmd_str or cmd_str.startswith("#"):
            continue

        display_cmd = cmd_str
        resolved_cmd = _resolve_template_vars(cmd_str, extra_vars)
        yield f"\n$ {display_cmd}\n"

        async for line in _stream_shell(resolved_cmd, cwd=preset_dir, env_extra=extra_vars):
            if line.startswith(EXIT_SENTINEL_PREFIX):
                if "1" in line:
                    yield f"Error: command failed (exit 1)\n"
                    yield line
                    return
                continue
            yield line

    yield f"{EXIT_SENTINEL_PREFIX}0\n"


async def _setup_ecs_env(resource_id: Optional[str],
                         resource_dir: Optional[Path]) -> tuple[Dict, list[str]]:
    lines = []
    extra_vars = {}

    root_tfvars = parser._read_tfvars_to_map(Path(TERRAFORM_DIR) / "terraform.tfvars")
    for key, val in root_tfvars.items():
        clean_val = val.strip('"').strip("'")
        extra_vars[key] = clean_val

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

    for key, val in list(extra_vars.items()):
        extra_vars[f"TF_VAR_{key}"] = val

    return extra_vars, lines


async def _stream_action(action_label: str, name: str, commands: List[str],
                         resource_id: Optional[str], resource_dir: Optional[Path],
                         on_success=None) -> AsyncIterator[str]:
    yield f"=== ECS Preset {action_label} ===\n"
    yield f"Preset: {name}\n\n"

    extra_vars, lines = await _setup_ecs_env(resource_id, resource_dir)
    for line in lines:
        yield line

    preset_dir = preset_manager.sync_preset_to_local(name)
    if not preset_dir:
        yield "Error: Failed to sync preset files to local\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    yield f"\n{action_label} from: {preset_dir}\n"

    success = True
    async for line in _execute_commands(commands, str(preset_dir), extra_vars):
        if line.startswith(EXIT_SENTINEL_PREFIX) and "1" in line:
            success = False
        yield line

    if success and on_success:
        try:
            on_success()
        except Exception as e:
            logger.warning(f"on_success callback failed: {e}")


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

    commands = preset.get("deploy_commands", [])
    if not commands:
        raise HTTPException(status_code=400, detail="No deploy commands defined for this preset")

    resource_id, resource_dir = _get_ecs_resource_info()

    return StreamingResponse(
        _stream_action("Deploy", name, commands, resource_id, resource_dir,
                        on_success=lambda: preset_manager.mark_deployed(name)),
        media_type="text/plain",
    )


@router.post("/presets/{name}/update")
async def update_preset_deploy(name: str):
    preset = preset_manager.get_preset(name)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")

    commands = preset.get("update_commands", [])
    if not commands:
        raise HTTPException(status_code=400, detail="No update commands defined for this preset")

    resource_id, resource_dir = _get_ecs_resource_info()

    return StreamingResponse(
        _stream_action("Update", name, commands, resource_id, resource_dir),
        media_type="text/plain",
    )


@router.post("/presets/{name}/undeploy")
async def undeploy_preset(name: str):
    preset = preset_manager.get_preset(name)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")

    commands = preset.get("undeploy_commands", [])
    if not commands:
        raise HTTPException(status_code=400, detail="No undeploy commands defined for this preset")

    resource_id, resource_dir = _get_ecs_resource_info()

    return StreamingResponse(
        _stream_action("Undeploy", name, commands, resource_id, resource_dir,
                        on_success=lambda: preset_manager.mark_undeployed(name)),
        media_type="text/plain",
    )


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
    services = []
    paginator = client.get_paginator("list_services")
    for page in paginator.paginate(cluster=cluster_name):
        services.extend(page.get("serviceArns", []))

    active_services = []
    if services:
        for i in range(0, len(services), 10):
            batch = services[i:i+10]
            desc = client.describe_services(cluster=cluster_name, services=batch)
            for svc in desc.get("services", []):
                if svc.get("desiredCount", 0) > 0 or svc.get("runningCount", 0) > 0:
                    active_services.append({
                        "name": svc.get("serviceName", ""),
                        "status": svc.get("status", ""),
                        "running": svc.get("runningCount", 0),
                        "desired": svc.get("desiredCount", 0),
                    })

    return {
        "has_active": len(active_services) > 0,
        "services": active_services,
    }


@router.get("/has-active-workloads")
async def has_active_workloads():
    resource_id, resource_dir = _get_ecs_resource_info()
    if not resource_dir:
        return {"has_active": False, "services": []}

    cluster_info = await _get_cluster_info_async(resource_id, resource_dir)
    cluster_name = cluster_info.get("cluster_name")
    region = cluster_info.get("region")
    if not cluster_name:
        return {"has_active": False, "services": []}

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _check_active_workloads, cluster_name, region)
        return result
    except Exception as e:
        logger.error(f"Failed to check active workloads: {e}")
        return {"has_active": False, "services": [], "error": str(e)}


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
