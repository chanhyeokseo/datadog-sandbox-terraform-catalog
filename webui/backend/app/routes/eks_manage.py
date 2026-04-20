import asyncio
import base64
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

import boto3
from botocore.signers import RequestSigner
from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import StreamingResponse

from app.models.schemas import ResourceType
from app.services.credential_manager import credential_manager
from app.services.eks_preset_manager import EKSPresetManager, S3_PRESET_PREFIX
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


def _credential_health_usable(health: Dict) -> bool:
    return health.get("status") in ("valid", "expiring_soon")


def _sso_cache_file_exists() -> bool:
    sso_config = credential_manager.get_sso_config()
    if not sso_config:
        return True
    return credential_manager._get_sso_cache_path(sso_config).exists()


async def _eks_aws_credentials_error_message() -> Optional[str]:
    health = await asyncio.to_thread(credential_manager.get_credential_health)
    logger.debug("EKS credential check: status=%s", health.get("status"))

    if not _credential_health_usable(health):
        refreshed = await asyncio.to_thread(credential_manager.try_refresh_credentials)
        if not refreshed:
            logger.warning("EKS action blocked: credentials unusable and refresh failed (status=%s)", health.get("status"))
            return _build_credential_error(health)
        health = await asyncio.to_thread(credential_manager.get_credential_health)
        if not _credential_health_usable(health):
            logger.warning("EKS action blocked: credentials still unusable after refresh (status=%s)", health.get("status"))
            return _build_credential_error(health)
        logger.info("EKS credentials refreshed successfully via SSO")

    if health.get("sso_configured"):
        cache_exists = await asyncio.to_thread(_sso_cache_file_exists)
        if not cache_exists:
            logger.warning("EKS action blocked: SSO cache file missing (logged out)")
            aws_profile = credential_manager.get_aws_profile()
            sso_cmd = f"aws sso login --profile={aws_profile}" if aws_profile else "aws sso login"
            return (
                "Error: SSO session has been logged out. "
                f"Run '{sso_cmd}' or complete SSO login in DogSTAC before running EKS operations.\n"
            )

    return None


def _build_credential_error(health: Dict) -> str:
    aws_profile = credential_manager.get_aws_profile()
    sso_command = f"aws sso login --profile={aws_profile}" if aws_profile else "aws sso login"
    logger.warning(
        "EKS action blocked: AWS credentials unusable (status=%s)",
        health.get("status"),
    )
    return (
        f"Error: AWS credentials are missing or expired. Run '{sso_command}' and retry, "
        "or complete SSO login in DogSTAC.\n"
    )


def _get_my_prefix() -> str:
    tfvars = parser._read_tfvars_to_map(Path(TERRAFORM_DIR) / "terraform.tfvars")
    return tfvars.get("name_prefix", "").strip('"').strip("'")


def _resolve_template_vars(command: str) -> str:
    root_tfvars = parser._read_tfvars_to_map(Path(TERRAFORM_DIR) / "terraform.tfvars")
    sensitive_vars = parser.config_manager.load_all_sensitive_variables()
    merged = {**root_tfvars, **sensitive_vars}
    def _replacer(m):
        var_name = m.group(1)
        val = merged.get(var_name)
        if val is None:
            logger.warning(f"Template variable '{var_name}' not found")
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


def _build_boto3_session(region: str) -> boto3.Session:
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    session_token = os.environ.get("AWS_SESSION_TOKEN")
    if access_key and secret_key:
        return boto3.Session(
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token,
        )
    return boto3.Session(region_name=region)


def _get_eks_token(cluster_name: str, region: str) -> str:
    session = _build_boto3_session(region)
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


def _write_kubeconfig(cluster_name: str, region: str) -> tuple[bool, str]:
    session = _build_boto3_session(region)
    eks_client = session.client("eks", region_name=region)
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


def _configure_kubeconfig(cluster_name: str, region: str) -> tuple[bool, str]:
    try:
        return _write_kubeconfig(cluster_name, region)
    except Exception as e:
        logger.warning(f"Kubeconfig failed: {e}, attempting SSO credential refresh")
        refreshed = credential_manager.try_refresh_credentials()
        if refreshed:
            try:
                return _write_kubeconfig(cluster_name, region)
            except Exception as retry_err:
                logger.warning(f"Kubeconfig failed after credential refresh: {retry_err}")
                return False, str(retry_err)
        logger.warning(f"Failed to configure kubeconfig: {e}")
        return False, str(e)


def _read_kubeconfig_context() -> Optional[str]:
    try:
        if KUBECONFIG_PATH.exists() and KUBECONFIG_PATH.stat().st_size > 0:
            data = json.loads(KUBECONFIG_PATH.read_text())
            return data.get("current-context")
    except Exception:
        pass
    return None


async def _setup_kubeconfig(resource_id: Optional[str], resource_dir: Optional[Path],
                            force: bool = False,
                            explicit_cluster_name: Optional[str] = None) -> tuple[bool, list[str]]:
    lines = []

    if not force and KUBECONFIG_PATH.exists() and KUBECONFIG_PATH.stat().st_size > 0:
        age = time.time() - KUBECONFIG_PATH.stat().st_mtime
        if age < TOKEN_EXPIRY_SECONDS:
            cached_context = _read_kubeconfig_context()
            if explicit_cluster_name:
                if cached_context == explicit_cluster_name:
                    logger.debug("Reusing cached kubeconfig for shared cluster %s", explicit_cluster_name)
                    return True, lines
            elif cached_context:
                return True, lines
        else:
            logger.debug("Kubeconfig token expired (age=%.0fs), refreshing", age)

    if explicit_cluster_name:
        region = os.environ.get("AWS_REGION", "ap-northeast-2")
        lines.append(f"Shared cluster: {explicit_cluster_name} (region: {region})\n")
        lines.append("Configuring kubeconfig...\n")
        success, output = _configure_kubeconfig(explicit_cluster_name, region)
        lines.append(output + "\n")
        if not success:
            lines.append("Error: Failed to configure kubeconfig\n")
            lines.append(f"{EXIT_SENTINEL_PREFIX}1\n")
            return False, lines
        return True, lines

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
            return True, lines
        else:
            lines.append(
                "Error: Could not resolve EKS cluster name from Terraform outputs. "
                "Ensure the eks_cluster instance applied successfully and outputs exist, then retry.\n"
            )
            lines.append(f"{EXIT_SENTINEL_PREFIX}1\n")
            logger.warning("EKS kubeconfig setup aborted: missing cluster_name in terraform outputs")
            return False, lines
    else:
        lines.append(
            "Error: No EKS Terraform instance directory found. Cannot configure kubectl for this workspace.\n"
        )
        lines.append(f"{EXIT_SENTINEL_PREFIX}1\n")
        logger.warning("EKS kubeconfig setup aborted: no EKS resource directory")
        return False, lines


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


_owner_bucket_cache: Dict[str, str] = {}


def _discover_owner_bucket(owner_prefix: str) -> str:
    cached = _owner_bucket_cache.get(owner_prefix)
    if cached:
        logger.debug(f"Owner bucket cache hit: {cached} (prefix={owner_prefix})")
        return cached

    from app.services.config_manager import ConfigManager
    cm = ConfigManager()
    safe_prefix = ''.join(c if c.isalnum() or c in '-_' else '-' for c in owner_prefix)[:64]
    ssm_path = f"/dogstac-{safe_prefix}/"
    try:
        from app.services.config_manager import SSM_GLOBAL_REGION
        ssm = boto3.client("ssm", region_name=SSM_GLOBAL_REGION)
        response = ssm.get_parameters_by_path(Path=ssm_path, Recursive=True, MaxResults=1)
        for param in response.get("Parameters", []):
            parts = param["Name"].split("/")
            if len(parts) >= 3:
                owner_hash = parts[2]
                safe = owner_prefix.lower().replace('_', '-')
                safe = ''.join(c if c.isalnum() or c == '-' else '-' for c in safe)[:32]
                bucket = f"dogstac-{safe}-{owner_hash}"
                logger.debug(f"Discovered owner bucket via SSM: {bucket} (prefix={owner_prefix})")
                _owner_bucket_cache[owner_prefix] = bucket
                return bucket
    except Exception as e:
        logger.warning(f"SSM discovery failed for {owner_prefix}: {e}")
    bucket = cm.generate_bucket_name(owner_prefix)
    logger.debug(f"Falling back to local hash for owner bucket: {bucket}")
    _owner_bucket_cache[owner_prefix] = bucket
    return bucket


def _get_owner_s3(owner_prefix: str):
    from app.services.s3_config_manager import S3ConfigManager
    bucket_name = _discover_owner_bucket(owner_prefix)
    return S3ConfigManager(bucket_name)


@router.get("/shared-presets")
async def list_shared_presets(owner_prefix: str = Query(...)):
    try:
        s3 = _get_owner_s3(owner_prefix)
        presets = []
        files = s3.list_files(S3_PRESET_PREFIX + "/")
        manifest_keys = [f for f in files if f.endswith("/manifest.json")]
        for key in manifest_keys:
            content = s3.download_text(key)
            if content:
                try:
                    manifest = json.loads(content)
                    manifest["built_in"] = manifest.get("built_in", False)
                    presets.append(manifest)
                except Exception:
                    pass
        return {"presets": presets}
    except Exception as e:
        logger.warning(f"Failed to list shared presets for {owner_prefix}: {e}")
        return {"presets": []}


@router.get("/shared-presets/{name}")
async def get_shared_preset(name: str, owner_prefix: str = Query(...)):
    try:
        s3 = _get_owner_s3(owner_prefix)
        content = s3.download_text(f"{S3_PRESET_PREFIX}/{name}/manifest.json")
        if not content:
            raise HTTPException(status_code=404, detail=f"Shared preset not found: {name}")
        manifest = json.loads(content)
        manifest["built_in"] = manifest.get("built_in", False)
        if "files" not in manifest or not manifest["files"]:
            all_keys = s3.list_files(f"{S3_PRESET_PREFIX}/{name}/")
            manifest["files"] = sorted(
                k.rsplit("/", 1)[-1] for k in all_keys
                if not k.endswith("/") and not k.endswith("/manifest.json")
            )
        return manifest
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to get shared preset {name} for {owner_prefix}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shared-presets/{name}/files/{filename:path}")
async def get_shared_preset_file(name: str, filename: str, owner_prefix: str = Query(...)):
    try:
        s3 = _get_owner_s3(owner_prefix)
        content = s3.download_text(f"{S3_PRESET_PREFIX}/{name}/{filename}")
        if not content and content != "":
            raise HTTPException(status_code=404, detail=f"File not found: {name}/{filename}")
        return {"filename": filename, "content": content}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to get shared preset file {name}/{filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _build_ownership_warnings(deployments: Dict, my_prefix: str) -> List[str]:
    foreign: List[str] = []
    for name, info in deployments.items():
        deployer = info.get("deployed_by", "") or "unknown"
        if deployer != my_prefix:
            foreign.append(f"{name} (by {deployer})")
    if not foreign:
        return []
    return [
        f"Ownership mismatch: {', '.join(foreign)} deployed by another user. "
        "These deployments use the deployer's Datadog API key, not yours."
    ]


_shared_deployments_cache: Dict[str, tuple] = {}
SHARED_DEPLOYMENTS_TTL = 30


@router.get("/shared-deployments")
async def list_shared_deployments(owner_prefix: str = Query(...), force: bool = Query(False)):
    try:
        my_prefix = _get_my_prefix()
        now = time.time()
        cached = _shared_deployments_cache.get(owner_prefix)
        if not force and cached and (now - cached[0]) < SHARED_DEPLOYMENTS_TTL:
            logger.debug(f"Shared deployments cache hit for {owner_prefix}")
            deployments = cached[1]
        else:
            s3 = _get_owner_s3(owner_prefix)
            content = s3.download_text(S3_PRESET_PREFIX + "/_deployments.json")
            deployments = json.loads(content) if content else {}
            _shared_deployments_cache[owner_prefix] = (now, deployments)

        result: Dict = {"deployments": deployments}
        warnings = _build_ownership_warnings(deployments, my_prefix)
        if warnings:
            result["warnings"] = warnings
        return result
    except Exception as e:
        logger.warning(f"Failed to list shared deployments for {owner_prefix}: {e}")
        return {"deployments": {}}


S3_DEPLOYMENTS_KEY = S3_PRESET_PREFIX + "/_deployments.json"


def _owner_mark_deployed(name: str, owner_prefix: str, deployed_by: str = ""):
    s3 = _get_owner_s3(owner_prefix)
    content = s3.download_text(S3_DEPLOYMENTS_KEY)
    deployments = json.loads(content) if content else {}
    entry = {"deployed_at": datetime.now(timezone.utc).isoformat()}
    if deployed_by:
        entry["deployed_by"] = deployed_by
    deployments[name] = entry
    s3.upload_text(S3_DEPLOYMENTS_KEY, json.dumps(deployments, indent=2) + "\n")
    logger.debug(f"Marked preset as deployed in owner({owner_prefix}) S3: {name} (by={deployed_by or 'unknown'})")


def _owner_mark_undeployed(name: str, owner_prefix: str):
    s3 = _get_owner_s3(owner_prefix)
    content = s3.download_text(S3_DEPLOYMENTS_KEY)
    deployments = json.loads(content) if content else {}
    if name in deployments:
        del deployments[name]
        s3.upload_text(S3_DEPLOYMENTS_KEY, json.dumps(deployments, indent=2) + "\n")
        logger.debug(f"Marked preset as undeployed in owner({owner_prefix}) S3: {name}")


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


def _sync_shared_preset_to_local(name: str, owner_prefix: str) -> Optional[Path]:
    s3 = _get_owner_s3(owner_prefix)
    local_dir = Path(TERRAFORM_DIR) / "eks" / name
    local_dir.mkdir(parents=True, exist_ok=True)
    keys = s3.list_files(f"{S3_PRESET_PREFIX}/{name}/")
    for key in keys:
        filename = key.rsplit("/", 1)[-1]
        if not filename:
            continue
        local_path = local_dir / filename
        content = s3.download_text(key)
        if content or content == "":
            local_path.write_text(content)
    if local_dir.exists() and any(local_dir.iterdir()):
        return local_dir
    return None


async def _stream_action(action_label: str, name: str, commands: List[str],
                         resource_id: Optional[str], resource_dir: Optional[Path],
                         on_success=None,
                         explicit_cluster_name: Optional[str] = None,
                         owner_prefix: Optional[str] = None) -> AsyncIterator[str]:
    cred_err = await _eks_aws_credentials_error_message()
    if cred_err:
        yield cred_err
        yield f"{EXIT_SENTINEL_PREFIX}1\n"
        return

    yield f"=== EKS Preset {action_label} ===\n"
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

    ok, lines = await _setup_kubeconfig(resource_id, resource_dir,
                                         explicit_cluster_name=explicit_cluster_name)
    for line in lines:
        yield line
    if not ok:
        return

    if owner_prefix:
        yield f"Syncing shared preset from {owner_prefix}...\n"
        preset_dir = _sync_shared_preset_to_local(name, owner_prefix)
        if not preset_dir:
            logger.debug(f"Shared sync failed for {name}, falling back to local (OOTB)")
            preset_dir = preset_manager.sync_preset_to_local(name)
    else:
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
async def get_deployments(force: bool = Query(False)):
    try:
        deployments = preset_manager.get_deployments(force=force)
        my_prefix = _get_my_prefix()
        result: Dict = {"deployments": deployments}
        warnings = _build_ownership_warnings(deployments, my_prefix)
        if warnings:
            result["warnings"] = warnings
        return result
    except Exception as e:
        logger.error(f"Failed to get deployments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _resolve_preset(name: str, owner_prefix: Optional[str] = None) -> dict:
    if owner_prefix:
        s3 = _get_owner_s3(owner_prefix)
        content = s3.download_text(f"{S3_PRESET_PREFIX}/{name}/manifest.json")
        if content:
            return json.loads(content)
    return preset_manager.get_preset(name) or {}


@router.post("/presets/{name}/deploy")
async def deploy_preset(name: str, cluster_name: Optional[str] = Query(None),
                        owner_prefix: Optional[str] = Query(None)):
    preset = _resolve_preset(name, owner_prefix)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")

    commands = preset.get("deploy_commands", [])
    if not commands:
        raise HTTPException(status_code=400, detail="No deploy commands defined for this preset")

    resource_id, resource_dir = _get_eks_resource_info()
    my_prefix = _get_my_prefix()

    if owner_prefix and cluster_name:
        on_success = lambda: _owner_mark_deployed(name, owner_prefix, deployed_by=my_prefix)
    else:
        on_success = lambda: preset_manager.mark_deployed(name, deployed_by=my_prefix)

    return StreamingResponse(
        _stream_action("Deploy", name, commands, resource_id, resource_dir,
                        on_success=on_success,
                        explicit_cluster_name=cluster_name,
                        owner_prefix=owner_prefix),
        media_type="text/plain",
    )


@router.post("/presets/{name}/update")
async def update_preset_deploy(name: str, cluster_name: Optional[str] = Query(None),
                               owner_prefix: Optional[str] = Query(None)):
    preset = _resolve_preset(name, owner_prefix)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")

    commands = preset.get("update_commands", [])
    if not commands:
        raise HTTPException(status_code=400, detail="No update commands defined for this preset")

    resource_id, resource_dir = _get_eks_resource_info()

    return StreamingResponse(
        _stream_action("Update", name, commands, resource_id, resource_dir,
                        explicit_cluster_name=cluster_name,
                        owner_prefix=owner_prefix),
        media_type="text/plain",
    )


@router.post("/presets/{name}/undeploy")
async def undeploy_preset(name: str, cluster_name: Optional[str] = Query(None),
                          owner_prefix: Optional[str] = Query(None)):
    preset = _resolve_preset(name, owner_prefix)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")

    commands = preset.get("undeploy_commands", [])
    if not commands:
        raise HTTPException(status_code=400, detail="No undeploy commands defined for this preset")

    resource_id, resource_dir = _get_eks_resource_info()

    if owner_prefix and cluster_name:
        on_success = lambda: _owner_mark_undeployed(name, owner_prefix)
    else:
        on_success = lambda: preset_manager.mark_undeployed(name)

    return StreamingResponse(
        _stream_action("Undeploy", name, commands, resource_id, resource_dir,
                        on_success=on_success,
                        explicit_cluster_name=cluster_name,
                        owner_prefix=owner_prefix),
        media_type="text/plain",
    )


@router.post("/presets/{name}/force-delete")
async def force_delete_preset(name: str,
                              cluster_name: Optional[str] = Query(None),
                              owner_prefix: Optional[str] = Query(None)):
    if owner_prefix and cluster_name:
        _owner_mark_undeployed(name, owner_prefix)
    else:
        preset_manager.mark_undeployed(name)
    return {"success": True, "message": f"Preset '{name}' removed from deployed list"}


@router.post("/kubectl")
async def run_kubectl(body: dict = Body(...)):
    command = body.get("command", "").strip()
    cluster_name = body.get("cluster_name")
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
        cred_err = await _eks_aws_credentials_error_message()
        if cred_err:
            yield cred_err
            yield f"{EXIT_SENTINEL_PREFIX}1\n"
            return

        ok, lines = await _setup_kubeconfig(resource_id, resource_dir,
                                             explicit_cluster_name=cluster_name)
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



