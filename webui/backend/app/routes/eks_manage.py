import asyncio
import base64
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

import boto3
from botocore.signers import RequestSigner
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse

from app.models.schemas import ResourceType
from app.services.eks_preset_manager import EKSPresetManager
from app.services.terraform_parser import TerraformParser
from app.services.terraform_runner import TerraformRunner
from app.services.instance_discovery import get_resource_id_for_instance, get_resource_type_from_dir

router = APIRouter(prefix="/api/terraform/eks/manage", tags=["eks-manage"])
logger = logging.getLogger(__name__)

TERRAFORM_DIR = os.environ.get("TERRAFORM_DIR", "/terraform")
EXIT_SENTINEL_PREFIX = "__TF_EXIT__:"
KUBECONFIG_PATH = Path.home() / ".kube" / "config"
TOKEN_EXPIRY_SECONDS = 900

preset_manager = EKSPresetManager(TERRAFORM_DIR)
parser = TerraformParser(TERRAFORM_DIR)
runner = TerraformRunner(TERRAFORM_DIR)

_deploy_lock = asyncio.Lock()

_TEMPLATE_RE = re.compile(r'\{\{(\w+)\}\}')


def _resolve_template_vars(command: str) -> str:
    root_tfvars = parser._read_tfvars_to_map(Path(TERRAFORM_DIR) / "terraform.tfvars")
    def _replacer(m):
        var_name = m.group(1)
        val = root_tfvars.get(var_name)
        if val is None:
            logger.warning(f"Template variable '{var_name}' not found in terraform.tfvars")
            return m.group(0)
        return val.strip('"').strip("'")
    return _TEMPLATE_RE.sub(_replacer, command)


def _get_eks_resource_info() -> tuple[Optional[str], Optional[Path]]:
    instances_dir = Path(TERRAFORM_DIR) / "instances"
    if not instances_dir.exists():
        return None, None
    for instance_dir in sorted(instances_dir.iterdir()):
        if not instance_dir.is_dir() or not (instance_dir / "main.tf").exists():
            continue
        if get_resource_type_from_dir(instance_dir.name) != ResourceType.EKS:
            continue
        resource_id = get_resource_id_for_instance(instance_dir)
        return resource_id, instance_dir
    return None, None


def _parse_cluster_info(outputs: Dict) -> Dict:
    cluster_name = None
    region = None
    kubeconfig_cmd = None

    for key, val in outputs.items():
        value = val.get("value", "") if isinstance(val, dict) else str(val)
        if not value:
            continue
        kl = key.lower()
        if kl == "cluster_name":
            cluster_name = str(value)
        elif kl == "kubeconfig_command":
            kubeconfig_cmd = str(value)

    if kubeconfig_cmd and not region:
        m = re.search(r'--region\s+(\S+)', kubeconfig_cmd)
        if m:
            region = m.group(1)

    return {
        "cluster_name": cluster_name,
        "region": region or os.environ.get("AWS_REGION", "ap-northeast-2"),
        "kubeconfig_command": kubeconfig_cmd,
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
        logger.warning(f"Failed to get cluster info: {e}")
    return {}


def _get_eks_token(cluster_name: str, region: str) -> str:
    session = boto3.Session(region_name=region)
    sts_client = session.client("sts", region_name=region)
    service_id = sts_client.meta.service_model.service_id

    signer = RequestSigner(
        service_id, region, "sts", "v4",
        session.get_credentials(),
        session._session.get_component("event_emitter"),
    )

    params = {
        "method": "GET",
        "url": f"https://sts.{region}.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15",
        "body": {},
        "headers": {"x-k8s-aws-id": cluster_name},
        "context": {},
    }

    signed_url = signer.generate_presigned_url(
        params, region_name=region, expires_in=TOKEN_EXPIRY_SECONDS, operation_name="",
    )
    return "k8s-aws-v1." + base64.urlsafe_b64encode(signed_url.encode("utf-8")).decode("utf-8").rstrip("=")


def _configure_kubeconfig(cluster_name: str, region: str) -> tuple[bool, str]:
    try:
        eks_client = boto3.client("eks", region_name=region)
        cluster = eks_client.describe_cluster(name=cluster_name)["cluster"]

        endpoint = cluster["endpoint"]
        ca_data = cluster["certificateAuthority"]["data"]
        token = _get_eks_token(cluster_name, region)

        kubeconfig = {
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [{"name": cluster_name, "cluster": {"server": endpoint, "certificate-authority-data": ca_data}}],
            "contexts": [{"name": cluster_name, "context": {"cluster": cluster_name, "user": cluster_name}}],
            "current-context": cluster_name,
            "users": [{"name": cluster_name, "user": {"token": token}}],
        }

        KUBECONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        KUBECONFIG_PATH.write_text(json.dumps(kubeconfig, indent=2))
        logger.debug(f"Kubeconfig written to {KUBECONFIG_PATH} for cluster {cluster_name}")
        return True, f"Kubeconfig configured for {cluster_name} at {endpoint}"
    except Exception as e:
        logger.warning(f"Failed to configure kubeconfig: {e}")
        return False, str(e)


async def _setup_kubeconfig(resource_id: Optional[str], resource_dir: Optional[Path],
                            force: bool = False) -> tuple[bool, list[str]]:
    lines = []

    if not force and KUBECONFIG_PATH.exists() and KUBECONFIG_PATH.stat().st_size > 0:
        age = time.time() - KUBECONFIG_PATH.stat().st_mtime
        if age < TOKEN_EXPIRY_SECONDS:
            return True, lines
        logger.debug("Kubeconfig token expired (age=%.0fs), refreshing", age)

    if resource_dir and resource_id:
        lines.append("Resolving EKS cluster info from Terraform outputs...\n")
        cluster_info = await _get_cluster_info_async(resource_id, resource_dir)
        cluster_name = cluster_info.get("cluster_name")
        region = cluster_info.get("region")

        if cluster_name:
            lines.append(f"Cluster: {cluster_name} (region: {region})\n")
            lines.append("Configuring kubeconfig...\n")
            success, output = _configure_kubeconfig(cluster_name, region)
            lines.append(output + "\n")
            if not success:
                lines.append("Error: Failed to configure kubeconfig\n")
                lines.append(f"{EXIT_SENTINEL_PREFIX}1\n")
                return False, lines
        else:
            lines.append("Warning: Could not resolve cluster name from outputs. Using existing kubeconfig.\n")
    else:
        lines.append("Warning: EKS resource not found. Using existing kubeconfig.\n")
    return True, lines


async def _stream_shell(cmd_str: str, cwd: str = None) -> AsyncIterator[str]:
    try:
        process = await asyncio.create_subprocess_shell(
            cmd_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            yield line.decode()
        code = (await process.wait()) or 0
        yield f"{EXIT_SENTINEL_PREFIX}{0 if code == 0 else 1}\n"
    except Exception as e:
        yield f"Error: {str(e)}\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"


async def _execute_commands(commands: List[str], preset_dir: str) -> AsyncIterator[str]:
    for cmd_str in commands:
        cmd_str = cmd_str.strip()
        if not cmd_str or cmd_str.startswith("#"):
            continue

        cmd_str = _resolve_template_vars(cmd_str)
        yield f"\n$ {cmd_str}\n"

        async for line in _stream_shell(cmd_str, cwd=preset_dir):
            if line.startswith(EXIT_SENTINEL_PREFIX):
                if "1" in line:
                    yield f"Error: command failed (exit 1)\n"
                    yield line
                    return
                continue
            yield line

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
        preset_type=body.get("type", "kubectl"),
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


async def _stream_action(action_label: str, name: str, commands: List[str],
                         resource_id: Optional[str], resource_dir: Optional[Path],
                         on_success=None) -> AsyncIterator[str]:
    yield f"=== EKS Preset {action_label} ===\n"
    yield f"Preset: {name}\n\n"

    ok, lines = await _setup_kubeconfig(resource_id, resource_dir)
    for line in lines:
        yield line
    if not ok:
        return

    preset_dir = preset_manager.sync_preset_to_local(name)
    if not preset_dir:
        yield "Error: Failed to sync preset files to local\n"
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    yield f"\n{action_label} from: {preset_dir}\n"

    success = True
    async for line in _execute_commands(commands, str(preset_dir)):
        if line.startswith(EXIT_SENTINEL_PREFIX) and "1" in line:
            success = False
        yield line

    if success and on_success:
        try:
            on_success()
        except Exception as e:
            logger.warning(f"on_success callback failed: {e}")


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

    resource_id, resource_dir = _get_eks_resource_info()

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

    resource_id, resource_dir = _get_eks_resource_info()

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

    resource_id, resource_dir = _get_eks_resource_info()

    return StreamingResponse(
        _stream_action("Undeploy", name, commands, resource_id, resource_dir,
                        on_success=lambda: preset_manager.mark_undeployed(name)),
        media_type="text/plain",
    )


@router.post("/kubectl")
async def run_kubectl(body: dict = Body(...)):
    command = body.get("command", "").strip()
    if not command:
        raise HTTPException(status_code=400, detail="command is required")

    ALLOWED_BINARIES = {"kubectl", "helm", "istioctl", "kustomize"}
    BINARY_ALIASES = {"k": "kubectl"}
    SHELL_META = {"|", "&&", "||", ";", "`", "$(", ">", "<", "&"}
    for meta in SHELL_META:
        if meta in command:
            raise HTTPException(
                status_code=400,
                detail=f"Shell operator '{meta}' is not allowed",
            )
    tokens = command.split()
    first_token = tokens[0] if tokens else ""
    if first_token in BINARY_ALIASES:
        tokens[0] = BINARY_ALIASES[first_token]
        command = " ".join(tokens)
        first_token = tokens[0]
    if first_token not in ALLOWED_BINARIES:
        raise HTTPException(
            status_code=400,
            detail=f"Only {', '.join(sorted(ALLOWED_BINARIES))} commands are allowed",
        )

    resource_id, resource_dir = _get_eks_resource_info()

    async def _stream():
        ok, lines = await _setup_kubeconfig(resource_id, resource_dir)
        for line in lines:
            yield line
        if not ok:
            return

        yield f"$ {command}\n"
        async for line in _stream_shell(command):
            yield line

    return StreamingResponse(_stream(), media_type="text/plain")


@router.get("/kubeconfig-status")
async def kubeconfig_status():
    resource_id, resource_dir = _get_eks_resource_info()
    if not resource_dir:
        return {"configured": False, "cluster_name": None, "message": "EKS resource not found"}

    cluster_info = await _get_cluster_info_async(resource_id, resource_dir)
    cluster_name = cluster_info.get("cluster_name")
    if not cluster_name:
        return {"configured": False, "cluster_name": None, "message": "Cluster not deployed or outputs unavailable"}

    return {
        "configured": True,
        "cluster_name": cluster_name,
        "region": cluster_info.get("region"),
        "kubeconfig_command": cluster_info.get("kubeconfig_command"),
    }
