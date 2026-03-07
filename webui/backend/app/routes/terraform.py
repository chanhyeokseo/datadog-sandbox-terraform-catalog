from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
from typing import List, Dict, Optional
from pathlib import Path
import logging
import asyncio
import json
import os
import re
import time
import boto3
from botocore.exceptions import ClientError, ProfileNotFound

from app.models.schemas import (
    ResourceType,
    TerraformResource,
    TerraformStateResponse,
    TerraformVariable
)
from app.services.terraform_parser import TerraformParser
from app.services.terraform_runner import TerraformRunner
from app.services.instance_discovery import get_resource_id_for_instance, get_resource_type_from_dir
from app.services.credential_manager import credential_manager

router = APIRouter(prefix="/api/terraform", tags=["terraform"])
logger = logging.getLogger(__name__)

TERRAFORM_DIR = os.environ.get("TERRAFORM_DIR", "/terraform")
parser = TerraformParser(TERRAFORM_DIR)
runner = TerraformRunner(TERRAFORM_DIR)

resource_locks: Dict[str, asyncio.Lock] = {}

_CREDENTIAL_ERROR_KEYWORDS = [
    "token has expired", "token retrieval", "no credentials",
    "credential retrieval", "invalidgrant", "expired token",
    "unable to locate credentials",
]


def _is_credential_error(error: Exception) -> bool:
    msg = str(error).lower()
    return any(kw in msg for kw in _CREDENTIAL_ERROR_KEYWORDS)


def _get_eks_resource_info() -> tuple[Optional[str], Optional[Path]]:
    try:
        for resource in parser.parse_all_resources():
            if resource.type != ResourceType.EKS:
                continue
            resource_dir = runner.get_resource_directory(resource.id)
            if resource_dir and resource_dir.exists():
                logger.debug(f"Resolved EKS resource directory for {resource.id}: {resource_dir}")
                return resource.id, resource_dir
    except Exception as e:
        logger.debug(f"Failed to resolve EKS resource from parsed resources: {e}")
    if parser.instances_dir.exists():
        for instance_dir in sorted(parser.instances_dir.iterdir()):
            if not instance_dir.is_dir() or not (instance_dir / "main.tf").exists():
                continue
            if get_resource_type_from_dir(instance_dir.name) != ResourceType.EKS:
                continue
            resource_id = get_resource_id_for_instance(instance_dir)
            logger.debug(f"Resolved EKS resource directory from instances scan for {resource_id}: {instance_dir}")
            return resource_id, instance_dir
    logger.debug("No EKS resource directory found while handling config request")
    return None, None


def _get_eks_config_file(resource_dir: Optional[Path]) -> Optional[Path]:
    if not resource_dir:
        return None
    return resource_dir / "eks-config.auto.tfvars"


def _parse_eks_config_file(config_path: Path) -> Optional[Dict]:
    if not config_path.exists():
        return None
    try:
        config: Dict = {}
        content = config_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r'^(\w+)\s*=\s*(.+)$', line)
            if not match:
                continue
            key, raw = match.group(1), match.group(2).strip()
            if raw in ("true", "false"):
                config[key] = raw == "true"
            elif raw.startswith("["):
                config[key] = json.loads(raw)
            elif raw.startswith('"') and raw.endswith('"'):
                config[key] = raw[1:-1]
            else:
                try:
                    config[key] = int(raw)
                except ValueError:
                    config[key] = raw
        logger.debug("Loaded EKS config from local file: %s (%d keys)", config_path, len(config))
        return config
    except Exception as e:
        logger.warning("Failed to parse EKS config file %s: %s", config_path, e)
        return None


def _parse_terraform_output_json(raw_output: str) -> Dict:
    try:
        parsed = json.loads(raw_output)
        if isinstance(parsed, dict):
            return parsed
    except Exception as e:
        logger.debug(f"Failed to parse terraform output JSON for EKS config: {e}")
    return {}


def _get_output_value(outputs: Dict, name: str):
    entry = outputs.get(name)
    if isinstance(entry, dict) and "value" in entry:
        return entry["value"]
    return None


def _extract_eks_config_from_outputs(outputs: Dict) -> tuple[Dict, List[str]]:
    config: Dict = {}
    missing: List[str] = []
    for name in ['enable_node_group', 'enable_windows_node_group', 'enable_fargate',
                 'endpoint_public_access', 'endpoint_private_access']:
        value = _get_output_value(outputs, name)
        if isinstance(value, bool):
            config[name] = value
        else:
            missing.append(name)
    for name in ['node_desired_size', 'node_min_size', 'node_max_size', 'node_disk_size',
                 'windows_node_desired_size', 'windows_node_min_size', 'windows_node_max_size',
                 'windows_node_disk_size']:
        value = _get_output_value(outputs, name)
        if isinstance(value, (int, float)):
            config[name] = int(value)
        else:
            missing.append(name)
    for name in ['node_capacity_type', 'windows_node_capacity_type', 'windows_node_ami_type']:
        value = _get_output_value(outputs, name)
        if isinstance(value, str) and value:
            config[name] = value
        else:
            missing.append(name)
    for name in ['node_instance_types', 'windows_node_instance_types', 'fargate_namespaces']:
        value = _get_output_value(outputs, name)
        if isinstance(value, list):
            config[name] = [str(item) for item in value]
        else:
            missing.append(name)
    return config, missing


def _build_sts_client():
    aws_env = parser.get_aws_env()
    region = aws_env.get("AWS_REGION", "ap-northeast-2")
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    session_token = os.environ.get("AWS_SESSION_TOKEN")
    if access_key and secret_key:
        return boto3.client(
            "sts", region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token,
        )
    return boto3.client("sts", region_name=region)


@router.get("/credentials/check")
async def check_credentials():
    try:
        sts = _build_sts_client()
        identity = await asyncio.to_thread(sts.get_caller_identity)
        return {
            "valid": True,
            "account": identity.get("Account", ""),
            "arn": identity.get("Arn", ""),
        }
    except ProfileNotFound:
        aws_profile = os.environ.get("AWS_PROFILE", "")
        logger.warning(f"AWS profile not found: {aws_profile}")
        raise HTTPException(
            status_code=401,
            detail={
                "message": f"AWS profile '{aws_profile}' not found in ~/.aws/config. Verify the profile name and re-run docker compose.",
                "aws_profile": aws_profile,
                "error_type": "profile_not_found",
            },
        )
    except Exception as e:
        logger.warning(f"Credential check failed: {e}, attempting SSO auto-refresh")
        refreshed = await asyncio.to_thread(credential_manager.try_refresh_credentials)
        if refreshed:
            try:
                sts = _build_sts_client()
                identity = await asyncio.to_thread(sts.get_caller_identity)
                return {
                    "valid": True,
                    "account": identity.get("Account", ""),
                    "arn": identity.get("Arn", ""),
                }
            except Exception as retry_err:
                logger.warning(f"Credential check failed after refresh: {retry_err}")

        aws_profile = os.environ.get("AWS_PROFILE", "")
        sso_command = f"aws sso login --profile={aws_profile}" if aws_profile else "aws sso login"
        sso_configured = credential_manager.get_sso_config() is not None
        raise HTTPException(
            status_code=401,
            detail={
                "message": f"AWS credentials expired or not configured. Run '{sso_command}' and refresh.",
                "aws_profile": aws_profile,
                "sso_command": sso_command,
                "sso_configured": sso_configured,
            },
        )


@router.post("/credentials/sso-login")
async def sso_login():
    session = await asyncio.to_thread(credential_manager.start_sso_login)
    if not session:
        raise HTTPException(
            status_code=400,
            detail="SSO is not configured for the current AWS profile",
        )
    return {
        "session_id": session.session_id,
        "verification_uri": session.verification_uri,
        "user_code": session.user_code,
        "expires_in": int(session.expires_at - time.time()),
    }


@router.get("/credentials/sso-status/{session_id}")
async def sso_status(session_id: str):
    result = await asyncio.to_thread(credential_manager.poll_sso_token, session_id)
    return result


@router.get("/credentials/health")
async def credential_health():
    return await asyncio.to_thread(credential_manager.get_credential_health)



@router.post("/ensure-data")
async def ensure_data():
    from app.init_config import ensure_terraform_data
    try:
        result = await asyncio.to_thread(ensure_terraform_data)
        logger.info(f"ensure-data result: {result}")
        return result
    except Exception as e:
        logger.error(f"ensure-data failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/provider-cache/status")
async def provider_cache_status():
    return runner.get_cache_status()


def get_resource_lock(resource_id: str) -> asyncio.Lock:
    if resource_id not in resource_locks:
        resource_locks[resource_id] = asyncio.Lock()
    return resource_locks[resource_id]


def _var_files_for_resource(resource_id: str) -> Optional[List[str]]:
    """
    Build list of -var-file paths for terraform commands
    Each instance uses ONLY its own directory's terraform.tfvars
    (Root tfvars is synced to instances during onboarding)
    """
    resource_dir = runner.get_resource_directory(resource_id)
    if not resource_dir:
        return None

    inst_tfvars = resource_dir / "terraform.tfvars"
    if inst_tfvars.exists():
        return [str(inst_tfvars)]

    return None


@router.get("/init/{resource_id}/status")
async def terraform_init_status(resource_id: str):
    resource_dir = runner.get_resource_directory(resource_id)
    if not resource_dir or not resource_dir.exists():
        raise HTTPException(status_code=404, detail="Resource directory not found")
    initialized = (resource_dir / ".terraform").exists()
    return {"initialized": initialized, "resource_id": resource_id}


@router.get("/init/stream/{resource_id}")
async def terraform_init_stream(resource_id: str):
    resource_dir = runner.get_resource_directory(resource_id)
    if not resource_dir or not resource_dir.exists():
        raise HTTPException(status_code=404, detail="Resource directory not found")

    aws_env = parser.get_aws_env()

    async def stream():
        from app.services.terraform_runner import EXIT_SENTINEL_PREFIX
        env = {**os.environ, **(aws_env or {})}
        try:
            process = await asyncio.create_subprocess_exec(
                "terraform", "init", "-no-color", "-input=false",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(resource_dir),
                env=env
            )
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                yield line.decode()
            code = (await process.wait()) or 0
            yield f"{EXIT_SENTINEL_PREFIX}{0 if code == 0 else 1}\n"
        except Exception as e:
            logger.error(f"Error streaming terraform init: {e}")
            yield f"Error: {str(e)}\n"
            yield f"{EXIT_SENTINEL_PREFIX}1\n"

    return StreamingResponse(stream(), media_type="text/plain")


@router.post("/init/{resource_id}")
async def terraform_init_resource(resource_id: str):
    try:
        resource_dir = runner.get_resource_directory(resource_id)
        
        if not resource_dir:
            raise HTTPException(status_code=404, detail="Resource directory not found")
        
        if not resource_dir.exists():
            raise HTTPException(status_code=404, detail="Resource directory does not exist")
        
        aws_env = parser.get_aws_env()
        env = {**os.environ, **(aws_env or {})}
        logger.info(f"Force running terraform init in {resource_dir}")
        process = await asyncio.create_subprocess_exec(
            "terraform", "init", "-no-color", "-input=false",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(resource_dir),
            env=env
        )
        
        lines = []
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            lines.append(line.decode())
        
        await process.wait()
        output = "".join(lines)
        success = process.returncode == 0
        
        if success:
            logger.info(f"Successfully initialized terraform in {resource_dir}")
        else:
            logger.error(f"Failed to initialize terraform in {resource_dir}: {output}")
        
        return {"success": success, "output": output, "resource_id": resource_id}
        
    except Exception as e:
        logger.error(f"Error initializing terraform for {resource_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _is_sensitive(name: str) -> bool:
    return any(k in name.lower() for k in ["key", "secret", "token"])


def _get_config_onboarding_status():
    from app.config import ONBOARDING_PHASES
    try:
        variables = parser.parse_variables()
    except Exception as parse_err:
        logger.exception("parse_variables failed in config-status: %s", parse_err)
        return {"config_onboarding_required": True, "phases": [], "steps": []}
    var_map = {v.name: v for v in variables}
    phases_out = []
    any_missing = False
    for phase_id, phase_name, var_list in ONBOARDING_PHASES:
        step_vars = []
        phase_filled = True
        for name, label in var_list:
            v = var_map.get(name)
            if v:
                filled = (v.sensitive and v.value == "***") or (not v.sensitive and (v.value or "").strip() != "")
            else:
                filled = False
            if not filled:
                phase_filled = False
                any_missing = True
            step_vars.append({
                "name": name,
                "label": label,
                "filled": filled,
                "sensitive": v.sensitive if v else _is_sensitive(name),
            })
        phases_out.append({
            "id": phase_id,
            "name": phase_name,
            "variables": step_vars,
            "all_filled": phase_filled,
        })
    steps_flat = []
    for p in phases_out:
        steps_flat.extend(p["variables"])
    return {"config_onboarding_required": any_missing, "phases": phases_out, "steps": steps_flat}


@router.get("/onboarding/config-status")
async def get_config_onboarding_status():
    try:
        return _get_config_onboarding_status()
    except Exception as e:
        logger.exception("Error in get_config_onboarding_status: %s", e)
        return {"config_onboarding_required": True, "phases": [], "steps": []}


def _get_ec2_client(region: str):
    return boto3.client("ec2", region_name=region)


def _get_tag_name(tags: list) -> Optional[str]:
    for tag in (tags or []):
        if tag.get("Key") == "Name" and tag.get("Value"):
            return tag["Value"]
    return None


@router.get("/aws/vpcs")
async def get_aws_vpcs(region: str = Query(..., description="AWS region")):
    try:
        ec2 = _get_ec2_client(region)
        response = await asyncio.to_thread(
            ec2.describe_vpcs,
            Filters=[{"Name": "state", "Values": ["available"]}],
        )
        vpcs = []
        for vpc in response.get("Vpcs", []):
            vpc_id = vpc["VpcId"]
            vpcs.append({
                "id": vpc_id,
                "cidr": vpc.get("CidrBlock", ""),
                "name": _get_tag_name(vpc.get("Tags")) or vpc_id,
            })
        return {"vpcs": vpcs}
    except Exception as e:
        logger.debug(f"get_aws_vpcs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/aws/subnets")
async def get_aws_subnets(region: str = Query(...), vpc_id: str = Query(...)):
    try:
        ec2 = _get_ec2_client(region)
        response = await asyncio.to_thread(
            ec2.describe_subnets,
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {"Name": "state", "Values": ["available"]},
            ],
        )
        subnets = []
        for subnet in response.get("Subnets", []):
            sid = subnet["SubnetId"]
            subnets.append({
                "id": sid,
                "cidr": subnet.get("CidrBlock", ""),
                "az": subnet.get("AvailabilityZone", ""),
                "name": _get_tag_name(subnet.get("Tags")) or sid,
            })
        return {"subnets": subnets}
    except Exception as e:
        logger.debug(f"get_aws_subnets error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _convert_rsa_pem_to_openssh(pem_content: str) -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    key = serialization.load_pem_private_key(
        pem_content.encode("utf-8"), password=None, backend=default_backend()
    )
    openssh_bytes = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return openssh_bytes.decode("utf-8")


@router.post("/aws/key-pair")
async def create_aws_key_pair():
    try:
        aws_env = parser.get_aws_env()
        region = (aws_env.get("AWS_REGION") or "").strip() or "ap-northeast-2"
        try:
            variables = parser.parse_variables()
        except Exception as parse_err:
            logger.exception("parse_variables failed in create_aws_key_pair")
            raise HTTPException(status_code=500, detail=f"Failed to read config: {parse_err}")
        var_map = {v.name: v.value for v in variables}
        name_prefix = (var_map.get("name_prefix") or "").strip() or "dogstac"
        safe = lambda s: "".join(c if c.isalnum() or c in "-_" else "-" for c in s)[:64]
        key_name = f"{safe(name_prefix)}-key-pair"
        try:
            ec2 = _get_ec2_client(region)
            response = await asyncio.to_thread(ec2.create_key_pair, KeyName=key_name)
        except ClientError as ce:
            msg = ce.response.get("Error", {}).get("Message", str(ce))
            logger.debug(f"CreateKeyPair API error: {msg}")
            raise HTTPException(status_code=500, detail=msg)
        kname = response.get("KeyName", "")
        private_key = response.get("KeyMaterial", "")
        if not kname or not private_key:
            logger.debug(f"CreateKeyPair response missing key name or material: kname={bool(kname)}")
            raise HTTPException(status_code=500, detail="CreateKeyPair did not return key name or material")
        try:
            private_key = _convert_rsa_pem_to_openssh(private_key)
        except Exception as conv_err:
            logger.debug(f"Key format conversion skipped: {conv_err}")
        try:
            parser.config_manager.save_key(private_key, key_name=kname)
        except Exception as e:
            logger.warning(f"Failed to upload key to Parameter Store: {e}")
        keys_dir = parser.terraform_dir / "keys"
        try:
            keys_dir.mkdir(parents=True, exist_ok=True)
            pem_path = keys_dir / f"{kname}.pem"
            pem_path.write_text(private_key, encoding="utf-8")
            pem_path.chmod(0o600)
        except OSError as e:
            logger.debug(f"Local key file write failed (non-critical): {e}")
        try:
            parser.write_root_tfvars("ec2_key_name", kname)
        except Exception as e:
            logger.exception("Failed to update tfvars with ec2_key_name")
            raise HTTPException(status_code=500, detail=f"Key created but failed to save config: {e}")
        key_path_str = f"keys/{kname}.pem"
        return {
            "key_name": kname,
            "private_key": private_key,
            "key_path": key_path_str,
            "ssh_hint": f"ssh -i {key_path_str} ec2-user@<instance-ip>",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("create_aws_key_pair error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/onboarding/status")
async def get_onboarding_status():
    try:
        resources = parser.parse_all_resources()
        sg_resource = next(
            (r for r in resources if r.type.value == "security_group"),
            None
        )

        if not sg_resource:
            return {
                "onboarding_required": True,
                "reason": "security_group_missing",
                "message": "Security Group resource not found"
            }

        if sg_resource.status.value == "enabled":
            return {
                "onboarding_required": False,
                "message": "Security Group is deployed. You can deploy other resources."
            }

        return {
            "onboarding_required": True,
            "reason": "security_group_not_deployed",
            "message": "Security Group must be deployed first",
            "next_steps": [
                "Select the Security Group from the list",
                "Click PLAN to preview changes",
                "Click DEPLOY to provision the Security Group",
                "Wait for the deployment to complete",
                "You can then deploy other resources"
            ]
        }

    except Exception as e:
        logger.error(f"Error checking onboarding status: {e}")
        return {
            "onboarding_required": True,
            "reason": "error",
            "message": str(e)
        }


@router.get("/resources", response_model=List[TerraformResource])
async def get_resources():
    try:
        resources = parser.parse_all_resources()
        logger.info(f"Loaded {len(resources)} resources with current states")
        return resources
    except ProfileNotFound:
        aws_profile = os.environ.get("AWS_PROFILE", "")
        logger.error(f"AWS profile not found: {aws_profile}")
        raise HTTPException(
            status_code=401,
            detail={
                "message": f"AWS profile '{aws_profile}' not found in ~/.aws/config. Verify the profile name and re-run docker compose.",
                "aws_profile": aws_profile,
                "error_type": "profile_not_found",
            },
        )
    except Exception as e:
        logger.error(f"Error getting resources: {e}")
        if _is_credential_error(e):
            aws_profile = os.environ.get("AWS_PROFILE", "")
            sso_command = f"aws sso login --profile={aws_profile}" if aws_profile else "aws sso login"
            raise HTTPException(
                status_code=401,
                detail={
                    "message": f"AWS credentials expired or not configured. Run '{sso_command}' and refresh.",
                    "aws_profile": aws_profile,
                    "sso_command": sso_command,
                },
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resources/{resource_id}/refresh-status")
async def refresh_resource_status(resource_id: str):
    try:
        target = parser.get_resource_by_id(resource_id)
        if not target:
            raise HTTPException(status_code=404, detail="Resource not found")
        resource_dir = runner.get_resource_directory(resource_id)
        dir_name = resource_dir.name if resource_dir else resource_id
        parser.invalidate_s3_status(dir_name)
        s3_statuses = parser._fetch_all_s3_statuses()
        status = s3_statuses.get(dir_name, target.status)
        return {"resource_id": resource_id, "status": status.value if hasattr(status, 'value') else str(status)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing resource status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/variables", response_model=List[TerraformVariable])
async def get_variables():
    try:
        variables = parser.parse_variables()
        return variables
    except Exception as e:
        logger.error(f"Error getting variables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/variables/{var_name}")
async def update_root_variable(var_name: str, payload: dict = Body(...)):
    from app.config import get_root_allowed_variable_names
    if var_name not in get_root_allowed_variable_names():
        parser._remove_variable_from_root(var_name)
        raise HTTPException(
            status_code=400,
            detail="Variable cannot be written to root. Root tfvars is only for Global Config and Onboarding. Use the resource's Resource Variables section for instance-specific variables."
        )
    value = (payload.get("value") or "").strip() if isinstance(payload.get("value"), str) else ""
    try:
        logger.info(f"Updating root variable {var_name} -> root terraform.tfvars only")
        success = parser.write_root_tfvars(var_name, value)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update variable")
        logger.info(f"Successfully updated root variable {var_name}")
        return {"success": True, "message": f"Variable {var_name} updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating variable: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/resources/{resource_id}/variables/{var_name}")
async def update_instance_variable(resource_id: str, var_name: str, payload: dict = Body(...)):
    raw = payload.get("value")
    if raw is None:
        value = ""
    elif isinstance(raw, str):
        value = raw.strip()
    else:
        value = str(raw).strip()
    try:
        resource = parser.get_resource_by_id(resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        parts = resource.file_path.split("/")
        if len(parts) < 2:
            raise HTTPException(status_code=500, detail="Invalid resource file_path")
        instance_dir = Path(TERRAFORM_DIR) / "instances" / parts[1]
        tfvars_path = instance_dir / "terraform.tfvars"
        root_tfvars = Path(TERRAFORM_DIR) / "terraform.tfvars"
        if parts[1] == ".." or tfvars_path == root_tfvars:
            raise HTTPException(
                status_code=500,
                detail="Cannot write instance variable to root terraform.tfvars"
            )
        if not instance_dir.exists() or not instance_dir.is_dir():
            raise HTTPException(
                status_code=500,
                detail=f"Instance directory not found: {instance_dir}"
            )
        success = parser.write_tfvars_to_path(tfvars_path, var_name, value)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to update variable (instance directory not found or not writable)"
            )
        parser.remove_non_common_from_root(var_name)
        logger.info(f"Updated variable {var_name} for resource {resource_id} -> {tfvars_path}")
        return {"success": True, "message": f"Variable {var_name} updated"}
    except HTTPException:
        raise
    except OSError as e:
        logger.error(f"Error writing instance tfvars: {e}")
        raise HTTPException(status_code=500, detail=f"Could not write file: {e}")
    except Exception as e:
        logger.exception("Error updating resource variable")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/onboarding/sync-tfvars-to-instances")
async def sync_tfvars_to_instances():
    try:
        success = parser.copy_root_tfvars_to_instances()
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Root terraform.tfvars not found or could not copy to any instance"
            )
        return {"success": True, "message": "Root terraform.tfvars copied to all instance directories"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error syncing tfvars to instances: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-name-prefix/{prefix}")
async def check_name_prefix(prefix: str):
    try:
        from app.services.config_manager import ConfigManager
        config_manager = ConfigManager(terraform_dir=runner.terraform_dir)
        result = config_manager.check_name_prefix_available(prefix)
        return result
    except Exception as e:
        logger.error(f"Error checking name_prefix: {e}")
        return {"available": True, "error": str(e)}


@router.post("/onboarding/sync-to-parameter-store")
async def sync_to_parameter_store():
    try:
        success = parser.sync_to_parameter_store()
        if not success:
            raise HTTPException(status_code=500, detail="Failed to sync configuration to Parameter Store")
        return {"success": True, "message": "Configuration synced to Parameter Store"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error syncing to Parameter Store: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resources/{resource_id}/variables/restore")
async def restore_resource_variables(resource_id: str):
    try:
        if not parser.get_resource_by_id(resource_id):
            raise HTTPException(status_code=404, detail="Resource not found")
        success = parser.copy_root_tfvars_to_resource(resource_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to restore variables from root")
        return {"success": True, "message": "Instance variables aligned with root terraform.tfvars"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring resource variables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources/{resource_id}/variables", response_model=List[TerraformVariable])
async def get_resource_variables(resource_id: str):
    try:
        from app.config import (
            is_common_variable,
            is_excluded_variable,
            get_resource_type_for_variables,
            get_resource_variables as get_resource_variable_configs,
        )

        var_names = parser.get_resource_variables(resource_id)
        all_variables = parser.parse_variables()
        resource_vars = [
            v for v in all_variables
            if v.name in var_names
            and not is_excluded_variable(v.name)
            and not is_common_variable(v.name)
        ]
        resource = parser.get_resource_by_id(resource_id)
        if resource:
            effective_type = get_resource_type_for_variables(resource.type.value, resource.id)
            configs = get_resource_variable_configs(effective_type)
            returned_names = {v.name for v in resource_vars}
            for config in configs:
                if config.name in var_names and config.name not in returned_names and not is_excluded_variable(config.name):
                    default_val = config.default_value
                    if isinstance(default_val, bool):
                        value = "true" if default_val else "false"
                    else:
                        value = str(default_val) if default_val is not None else ""
                    sensitive = any(k in config.name.lower() for k in ["password", "key", "secret", "token"])
                    resource_vars.append(TerraformVariable(
                        name=config.name,
                        value=value,
                        description=config.description,
                        sensitive=sensitive,
                        is_common=False,
                    ))
                    returned_names.add(config.name)
        instance_defaults = parser.parse_instance_variable_defaults(resource_id)
        for v in resource_vars:
            if v.name in instance_defaults:
                raw = instance_defaults[v.name]
                v.value = "***" if (v.sensitive and raw) else raw

        instance_map = parser.get_instance_tfvars_map(resource_id)
        for v in resource_vars:
            if v.name in instance_map:
                raw = instance_map[v.name]
                v.value = "***" if (v.sensitive and raw) else raw
        return resource_vars
    except Exception as e:
        logger.error(f"Error getting resource variables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resources/{resource_id}/description")
async def get_resource_description(resource_id: str):
    try:
        resource_dir = runner.get_resource_directory(resource_id)
        if not resource_dir or not resource_dir.exists():
            raise HTTPException(status_code=404, detail="Resource not found")
        desc_file = resource_dir / "DESCRIPTION.md"
        if not desc_file.exists():
            raise HTTPException(status_code=404, detail="No description for this resource")
        return {"content": desc_file.read_text(encoding="utf-8")}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting resource description: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/state", response_model=TerraformStateResponse)
async def get_state():
    try:
        resources = parser.parse_all_resources()
        variables = parser.parse_variables()
        return TerraformStateResponse(resources=resources, variables=variables)
    except Exception as e:
        logger.error(f"Error getting state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plan/stream/{resource_id}")
async def terraform_plan_stream_resource(resource_id: str):
    try:
        target_resource = parser.get_resource_by_id(resource_id)
        
        if not target_resource:
            raise HTTPException(status_code=404, detail="Resource not found")

        var_files = _var_files_for_resource(resource_id)
        aws_env = parser.get_aws_env()
        async def stream_generator():
            logger.info(f"Starting plan for resource {resource_id}")
            try:
                async for chunk in runner.stream_plan(resource_id=resource_id, var_files=var_files, env_extra=aws_env):
                    yield chunk
            finally:
                logger.info(f"Completed plan for resource {resource_id}")
        
        return StreamingResponse(
            stream_generator(),
            media_type="text/plain"
        )
    except Exception as e:
        logger.error(f"Error streaming terraform plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/apply/stream/{resource_id}")
async def terraform_apply_stream_resource(resource_id: str, auto_approve: bool = False):
    import json
    import asyncio
    
    try:
        target_resource = parser.get_resource_by_id(resource_id)
        
        if not target_resource:
            raise HTTPException(status_code=404, detail="Resource not found")

        var_files = _var_files_for_resource(resource_id)
        if resource_id == "security_group":
            resource_dir = runner.get_resource_directory(resource_id)
            if resource_dir:
                rules_file = resource_dir / "security-group-rules.auto.tfvars"
                
                if rules_file.exists():
                    my_ip = None
                    try:
                        import urllib.request
                        with urllib.request.urlopen('https://ifconfig.me/ip', timeout=5) as response:
                            my_ip = response.read().decode('utf-8').strip()
                        if my_ip:
                            logger.info(f"Fetched current IP for security group update: {my_ip}")
                    except Exception as e:
                        logger.warning(f"Failed to fetch current IP: {e}")
                    
                    if my_ip:
                        try:
                            with open(rules_file, 'r') as f:
                                content = f.read()
                            
                            import re
                            
                            def update_ip_in_rule(match):
                                rule_block = match.group(0)
                                if 'use_my_ip   = true' in rule_block or 'use_my_ip = true' in rule_block:
                                    rule_block = re.sub(
                                        r'cidr_blocks = \["[^"]*"\]',
                                        f'cidr_blocks = ["{my_ip}/32"]',
                                        rule_block
                                    )
                                return rule_block
                            
                            updated_content = re.sub(
                                r'\{[^}]+\}',
                                update_ip_in_rule,
                                content,
                                flags=re.DOTALL
                            )
                            
                            with open(rules_file, 'w') as f:
                                f.write(updated_content)
                            
                            logger.info(f"Updated security group rules with current IP: {my_ip}/32")
                        except Exception as e:
                            logger.error(f"Failed to update IP in tfvars: {e}")
        
        aws_env = parser.get_aws_env()
        async def locked_stream():
            resource_lock = get_resource_lock(resource_id)
            async with resource_lock:
                logger.info(f"Acquired lock for {resource_id} (apply)")
                exit_code = None
                try:
                    async for chunk in runner.stream_apply(
                        resource_id=resource_id,
                        auto_approve=auto_approve,
                        var_files=var_files,
                        env_extra=aws_env
                    ):
                        if chunk.startswith("__TF_EXIT__:"):
                            exit_code = chunk.strip().split(":")[1]
                        yield chunk
                finally:
                    logger.info(f"Released lock for {resource_id} (apply)")
                    if exit_code == "0":
                        res_dir = runner.get_resource_directory(resource_id)
                        dir_name = res_dir.name if res_dir else None
                        parser.invalidate_s3_status(dir_name)
        
        return StreamingResponse(
            locked_stream(),
            media_type="text/plain"
        )
    except Exception as e:
        logger.error(f"Error streaming terraform apply: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/force-unlock/{resource_id}")
async def terraform_force_unlock(resource_id: str, body: dict):
    lock_id = body.get("lock_id", "").strip()
    if not lock_id:
        raise HTTPException(status_code=400, detail="lock_id is required")
    target = parser.get_resource_by_id(resource_id)
    if not target:
        raise HTTPException(status_code=404, detail="Resource not found")
    aws_env = parser.get_aws_env()
    success, output = await runner.force_unlock(resource_id, lock_id, env_extra=aws_env)
    if success:
        res_dir = runner.get_resource_directory(resource_id)
        dir_name = res_dir.name if res_dir else None
        parser.invalidate_s3_status(dir_name)
    return {"success": success, "output": output}


@router.get("/destroy/stream/{resource_id}")
async def terraform_destroy_stream_resource(resource_id: str, auto_approve: bool = False):
    try:
        target_resource = parser.get_resource_by_id(resource_id)
        
        if not target_resource:
            raise HTTPException(status_code=404, detail="Resource not found")

        var_files = _var_files_for_resource(resource_id)
        aws_env = parser.get_aws_env()
        async def locked_stream():
            resource_lock = get_resource_lock(resource_id)
            async with resource_lock:
                logger.info(f"Acquired lock for {resource_id} (destroy)")
                exit_code = None
                try:
                    async for chunk in runner.stream_destroy(
                        resource_id=resource_id,
                        auto_approve=auto_approve,
                        var_files=var_files,
                        env_extra=aws_env
                    ):
                        if chunk.startswith("__TF_EXIT__:"):
                            exit_code = chunk.strip().split(":")[1]
                        yield chunk
                finally:
                    logger.info(f"Released lock for {resource_id} (destroy)")
                    if exit_code == "0":
                        res_dir = runner.get_resource_directory(resource_id)
                        dir_name = res_dir.name if res_dir else None
                        parser.invalidate_s3_status(dir_name)
        
        return StreamingResponse(
            locked_stream(),
            media_type="text/plain"
        )
    except Exception as e:
        logger.error(f"Error streaming terraform destroy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/output")
async def terraform_output(resource_id: Optional[str] = None):
    try:
        aws_env = parser.get_aws_env()
        success, output = await runner.output(resource_id=resource_id, env_extra=aws_env)
        return {"success": success, "output": output}
    except Exception as e:
        logger.error(f"Error getting terraform output: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/eks/config")
async def get_eks_config():
    try:
        resource_id, resource_dir = _get_eks_resource_info()
        if not resource_id or not resource_dir:
            return {"error": "EKS resource not found"}

        config_path = _get_eks_config_file(resource_dir)
        if config_path:
            local_config = _parse_eks_config_file(config_path)
            if local_config:
                return local_config

        aws_env = parser.get_aws_env()
        init_ok, init_out = await runner.ensure_terraform_init(resource_dir, env_extra=aws_env)
        if not init_ok:
            logger.debug(f"Terraform init failed for {resource_id}: {init_out}")
            return {"error": "Terraform init failed for EKS resource"}
        success, output = await runner.output(resource_id=resource_id, env_extra=aws_env)
        if not success:
            logger.debug(f"Terraform output unavailable for {resource_id}: {output}")
            return {"error": "Failed to read terraform output for EKS resource"}
        outputs = _parse_terraform_output_json(output)
        if not outputs:
            logger.debug(f"Terraform output for {resource_id} was empty or invalid JSON")
            return {"error": "Terraform output for EKS resource is empty or invalid"}
        config, missing_outputs = _extract_eks_config_from_outputs(outputs)
        if missing_outputs:
            logger.debug(f"EKS config outputs missing for {resource_id}: {missing_outputs}")
            return {
                "error": "Required EKS config outputs are missing",
                "missing_outputs": missing_outputs,
            }
        logger.debug(f"Loaded EKS config from terraform output for {resource_id}: {sorted(config.keys())}")
        return config
    except Exception as e:
        logger.error(f"Error getting EKS config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/eks/config")
async def update_eks_config(config: Dict):
    try:
        _, resource_dir = _get_eks_resource_info()
        eks_config_file = _get_eks_config_file(resource_dir)
        if not eks_config_file:
            raise HTTPException(status_code=404, detail="EKS resource not found")
        eks_config_file.parent.mkdir(parents=True, exist_ok=True)
        
        lines = [
            f"enable_node_group   = {str(config.get('enable_node_group', True)).lower()}",
            f"node_instance_types = {config.get('node_instance_types', ['t3.medium'])}".replace("'", '"'),
            f"node_desired_size   = {config.get('node_desired_size', 2)}",
            f"node_min_size       = {config.get('node_min_size', 1)}",
            f"node_max_size       = {config.get('node_max_size', 4)}",
            f"node_disk_size      = {config.get('node_disk_size', 20)}",
            f"node_capacity_type  = \"{config.get('node_capacity_type', 'ON_DEMAND')}\"",
            f"enable_windows_node_group   = {str(config.get('enable_windows_node_group', False)).lower()}",
            f"windows_node_instance_types = {config.get('windows_node_instance_types', ['t3.medium'])}".replace("'", '"'),
            f"windows_node_ami_type       = \"{config.get('windows_node_ami_type', 'WINDOWS_FULL_2022_x86_64')}\"",
            f"windows_node_desired_size   = {config.get('windows_node_desired_size', 2)}",
            f"windows_node_min_size       = {config.get('windows_node_min_size', 1)}",
            f"windows_node_max_size       = {config.get('windows_node_max_size', 4)}",
            f"windows_node_disk_size      = {config.get('windows_node_disk_size', 50)}",
            f"windows_node_capacity_type  = \"{config.get('windows_node_capacity_type', 'ON_DEMAND')}\"",
            f"enable_fargate     = {str(config.get('enable_fargate', False)).lower()}",
            f"fargate_namespaces = {config.get('fargate_namespaces', ['default', 'kube-system'])}".replace("'", '"'),
            f"endpoint_public_access  = {str(config.get('endpoint_public_access', True)).lower()}",
            f"endpoint_private_access = {str(config.get('endpoint_private_access', True)).lower()}",
        ]
        
        with open(eks_config_file, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        
        return {"success": True, "message": "EKS configuration updated successfully"}
        
    except Exception as e:
        logger.error(f"Error updating EKS config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


_DOCKER_AGENT_RESOURCE_ID = "ec2_datadog_docker"

_DEFAULT_DOCKER_RUN_COMMAND = (
    "docker run -d \\\n"
    "  --name dd-agent \\\n"
    "  -e DD_API_KEY={{DD_API_KEY}} \\\n"
    "  -e DD_SITE={{DD_SITE}} \\\n"
    "  -e DD_DOGSTATSD_NON_LOCAL_TRAFFIC=true \\\n"
    "  -e DD_TAGS=\"{{DD_TAGS}}\" \\\n"
    "  -v /var/run/docker.sock:/var/run/docker.sock:ro \\\n"
    "  -v /proc/:/host/proc/:ro \\\n"
    "  -v /sys/fs/cgroup/:/host/sys/fs/cgroup:ro \\\n"
    "  -v /var/lib/docker/containers:/var/lib/docker/containers:ro \\\n"
    "  {{DD_AGENT_IMAGE}}"
)

def _get_docker_agent_resource_dir() -> Optional[Path]:
    resource_dir = runner.get_resource_directory(_DOCKER_AGENT_RESOURCE_ID)
    if resource_dir and resource_dir.exists():
        return resource_dir
    if parser.instances_dir.exists():
        candidate = parser.instances_dir / "ec2-datadog-docker"
        if candidate.is_dir() and (candidate / "main.tf").exists():
            return candidate
    return None


def _get_docker_agent_config_path(resource_dir: Path) -> Path:
    return resource_dir / "docker-agent-config.json"


def _resolve_docker_agent_placeholders(command: str, tfvars: dict) -> str:
    mapping = {
        "{{DD_API_KEY}}": tfvars.get("datadog_api_key", ""),
        "{{DD_SITE}}": tfvars.get("datadog_site", "datadoghq.com"),
        "{{DD_AGENT_IMAGE}}": tfvars.get("datadog_agent_image", "gcr.io/datadoghq/agent:latest"),
        "{{DD_TAGS}}": "creator:{},team:{},terraform:true".format(
            tfvars.get("creator", ""), tfvars.get("team", "")
        ),
    }
    result = command
    for placeholder, value in mapping.items():
        result = result.replace(placeholder, value)
    return result


@router.get("/docker-agent/config")
async def get_docker_agent_config():
    try:
        resource_dir = _get_docker_agent_resource_dir()
        if not resource_dir:
            return {"error": "ec2_datadog_docker resource not found"}

        resource = parser.get_resource_by_id(_DOCKER_AGENT_RESOURCE_ID)
        resource_status = resource.status.value if resource else "disabled"

        config_path = _get_docker_agent_config_path(resource_dir)
        if config_path.exists():
            with open(config_path, "r") as f:
                saved = json.load(f)
            docker_run_command = saved.get("docker_run_command", _DEFAULT_DOCKER_RUN_COMMAND)
        else:
            docker_run_command = _DEFAULT_DOCKER_RUN_COMMAND

        root_vars = parser._read_tfvars_to_map(parser._root_tfvars_path())
        instance_vars = parser.get_instance_tfvars_map(_DOCKER_AGENT_RESOURCE_ID)
        merged = {**root_vars, **instance_vars}

        placeholders = {
            "DD_API_KEY": "(configured)" if merged.get("datadog_api_key") else "(not set)",
            "DD_SITE": merged.get("datadog_site", "datadoghq.com"),
            "DD_AGENT_IMAGE": merged.get("datadog_agent_image", "gcr.io/datadoghq/agent:latest"),
            "DD_TAGS": "creator:{},team:{},...".format(
                merged.get("creator", ""), merged.get("team", "")
            ),
        }

        return {
            "docker_run_command": docker_run_command,
            "resource_status": resource_status,
            "placeholders": placeholders,
        }
    except Exception as e:
        logger.error(f"Error getting docker agent config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/docker-agent/config")
async def update_docker_agent_config(config: Dict):
    try:
        resource_dir = _get_docker_agent_resource_dir()
        if not resource_dir:
            raise HTTPException(status_code=404, detail="ec2_datadog_docker resource not found")

        docker_run_command = config.get("docker_run_command", "").strip()
        if not docker_run_command:
            raise HTTPException(status_code=400, detail="docker_run_command is required")

        config_path = _get_docker_agent_config_path(resource_dir)
        with open(config_path, "w") as f:
            json.dump({"docker_run_command": docker_run_command}, f, indent=2)
        logger.debug(f"Saved docker agent config to {config_path}")

        resource = parser.get_resource_by_id(_DOCKER_AGENT_RESOURCE_ID)
        is_deployed = resource and resource.status.value == "enabled"

        root_vars = parser._read_tfvars_to_map(parser._root_tfvars_path())
        instance_vars = parser.get_instance_tfvars_map(_DOCKER_AGENT_RESOURCE_ID)
        merged = {**root_vars, **instance_vars}
        resolved_command = _resolve_docker_agent_placeholders(docker_run_command, merged)

        if is_deployed:
            logger.info("Resource is deployed, applying docker agent config via SSH")
            return await _apply_docker_agent_via_ssh(resource_dir, resolved_command, merged)
        else:
            logger.info("Resource is not deployed, writing docker-agent.auto.tfvars")
            tfvars_path = resource_dir / "docker-agent.auto.tfvars"
            escaped = resolved_command.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            with open(tfvars_path, "w") as f:
                f.write(f'docker_run_command = "{escaped}"\n')
            logger.debug(f"Wrote docker-agent.auto.tfvars to {tfvars_path}")
            return {
                "success": True,
                "message": "Docker agent configuration saved. Click Deploy to apply with the new settings.",
                "mode": "terraform",
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating docker agent config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _apply_docker_agent_via_ssh(resource_dir: Path, resolved_command: str, merged_vars: dict) -> dict:
    import paramiko
    from io import StringIO

    aws_env = parser.get_aws_env()
    success, raw_output = await runner.output(resource_id=_DOCKER_AGENT_RESOURCE_ID, env_extra=aws_env)
    if not success:
        return {"success": False, "message": "Failed to get terraform outputs. Is the resource deployed?", "mode": "ssh"}

    outputs = _parse_terraform_output_json(raw_output)
    public_ip = _get_output_value(outputs, "public_ip")
    if not public_ip:
        return {"success": False, "message": "Public IP not found in terraform outputs.", "mode": "ssh"}

    key_name = merged_vars.get("ec2_key_name", "ec2-key")
    terraform_dir = Path(os.environ.get("TERRAFORM_DIR", "/terraform"))
    key_path = None
    for candidate in [
        terraform_dir / "keys" / f"{key_name}.pem",
        Path.cwd() / "keys" / f"{key_name}.pem",
    ]:
        if candidate.exists():
            key_path = candidate
            break

    if not key_path:
        from app.services.key_manager import LocalKeyManager
        local_km = LocalKeyManager(keys_dir=str(terraform_dir / "keys"))
        key_content = local_km.get_key(key_name)
        if not key_content:
            return {"success": False, "message": f"SSH key '{key_name}' not found.", "mode": "ssh"}
        key_obj = paramiko.RSAKey.from_private_key(StringIO(key_content))
    else:
        key_obj = paramiko.RSAKey.from_private_key_file(str(key_path))

    ssh_script = (
        "docker stop dd-agent 2>/dev/null; "
        "docker rm dd-agent 2>/dev/null; "
        f"{resolved_command}"
    )

    try:
        ssh_output = await asyncio.to_thread(
            _ssh_exec_command, public_ip, "ec2-user", key_obj, ssh_script
        )
        logger.info(f"SSH command executed on {public_ip}: {ssh_output[:200]}")
        return {
            "success": True,
            "message": "Docker agent container restarted with new configuration.",
            "mode": "ssh",
            "ssh_output": ssh_output,
        }
    except Exception as e:
        logger.error(f"SSH execution failed on {public_ip}: {e}")
        return {"success": False, "message": f"SSH execution failed: {e}", "mode": "ssh"}


def _ssh_exec_command(hostname: str, username: str, key: "paramiko.PKey", command: str, timeout: int = 30) -> str:
    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname, username=username, pkey=key, timeout=timeout)
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return out + err
    finally:
        client.close()


def _sg_ensure_defaults(ingress_rules: list) -> list:
    for r in ingress_rules:
        if r.get("from_port") in (22, 3389):
            r["readonly"] = True
    if not any(r.get("from_port") == 22 for r in ingress_rules):
        ingress_rules.insert(0, {
            "description": "Allow SSH from my IP", "from_port": 22, "to_port": 22,
            "protocol": "tcp", "cidr_blocks": [], "readonly": True,
        })
    if not any(r.get("from_port") == 3389 for r in ingress_rules):
        ingress_rules.insert(1, {
            "description": "Allow RDP from my IP", "from_port": 3389, "to_port": 3389,
            "protocol": "tcp", "cidr_blocks": [], "readonly": True,
        })
    return ingress_rules


@router.get("/security-group/rules")
async def get_security_group_rules():
    try:
        import json

        resource_dir = runner.get_resource_directory("security_group")

        if resource_dir:
            json_file = resource_dir / "security-group-rules.json"
            if json_file.exists():
                logger.debug("Reading SG rules from saved JSON: %s", json_file)
                with open(json_file, 'r') as f:
                    saved = json.load(f)
                ingress_rules = _sg_ensure_defaults(saved.get("ingress_rules", []))
                return {
                    "ingress_rules": ingress_rules,
                    "egress_rules": saved.get("egress_rules", []),
                }

        state_file = (resource_dir / "terraform.tfstate") if resource_dir else None
        if state_file and state_file.exists():
            logger.debug("Reading SG rules from state: %s", state_file)
            with open(state_file, 'r') as f:
                state = json.load(f)

            for resource in state.get("resources", []):
                if (resource.get("module") == "module.security_group" and
                    resource.get("type") == "aws_security_group" and
                    resource.get("name") in ("personal", "main")):

                    instances = resource.get("instances", [])
                    if not instances:
                        continue
                    attributes = instances[0].get("attributes", {})

                    ingress_rules = [{
                        "description": r.get("description", ""),
                        "from_port": r.get("from_port", 0),
                        "to_port": r.get("to_port", 0),
                        "protocol": r.get("protocol", "tcp"),
                        "cidr_blocks": r.get("cidr_blocks", []),
                    } for r in attributes.get("ingress", [])]

                    egress_rules = [{
                        "description": r.get("description", ""),
                        "from_port": r.get("from_port", 0),
                        "to_port": r.get("to_port", 0),
                        "protocol": r.get("protocol", "tcp"),
                        "cidr_blocks": r.get("cidr_blocks", []),
                    } for r in attributes.get("egress", [])]

                    ingress_rules = _sg_ensure_defaults(ingress_rules)
                    logger.debug("Loaded %d ingress / %d egress rules from state", len(ingress_rules), len(egress_rules))
                    return {"ingress_rules": ingress_rules, "egress_rules": egress_rules}

        logger.info("No SG config or state found, returning defaults")
        return {
            "ingress_rules": [
                {"description": "Allow SSH from my IP", "from_port": 22, "to_port": 22, "protocol": "tcp", "cidr_blocks": [], "readonly": True},
                {"description": "Allow RDP from my IP", "from_port": 3389, "to_port": 3389, "protocol": "tcp", "cidr_blocks": [], "readonly": True},
            ],
            "egress_rules": [],
        }

    except Exception as e:
        logger.error(f"Error getting security group rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/security-group/rules")
async def update_security_group_rules(rules_data: dict):
    import json
    import asyncio
    
    try:
        ingress_rules = rules_data.get("ingress_rules", [])
        egress_rules = rules_data.get("egress_rules", [])
        
        for rule in ingress_rules:
            if rule.get("from_port") in [22, 3389]:
                rule["use_my_ip"] = True
                rule["readonly"] = True
        
        resource_dir = runner.get_resource_directory("security_group")
        if not resource_dir or not resource_dir.exists():
            raise HTTPException(status_code=404, detail="Security group resource directory not found")
        rules_file = resource_dir / "security-group-rules.auto.tfvars"
        
        content = "# Security Group Rules Configuration\n"
        content += "# This file is auto-generated and managed by the WebUI\n\n"
        
        content += "sg_ingress_rules = [\n"
        for rule in ingress_rules:
            content += "  {\n"
            content += f'    description = "{rule["description"]}"\n'
            content += f'    from_port   = {rule["from_port"]}\n'
            content += f'    to_port     = {rule["to_port"]}\n'
            content += f'    protocol    = "{rule["protocol"]}"\n'
            content += f'    cidr_blocks = {json.dumps(rule.get("cidr_blocks", ["0.0.0.0/0"]))}\n'
            content += f'    use_my_ip   = {"true" if rule.get("use_my_ip") else "false"}\n'
            content += "  },\n"
        content += "]\n\n"
        
        content += "sg_egress_rules = [\n"
        for rule in egress_rules:
            content += "  {\n"
            content += f'    description = "{rule["description"]}"\n'
            content += f'    from_port   = {rule["from_port"]}\n'
            content += f'    to_port     = {rule["to_port"]}\n'
            content += f'    protocol    = "{rule["protocol"]}"\n'
            content += f'    cidr_blocks = {json.dumps(rule.get("cidr_blocks", ["0.0.0.0/0"]))}\n'
            content += f'    use_my_ip   = {"true" if rule.get("use_my_ip") else "false"}\n'
            content += "  },\n"
        content += "]\n"
        
        with open(rules_file, 'w') as f:
            f.write(content)

        json_file = resource_dir / "security-group-rules.json"
        with open(json_file, 'w') as f:
            json.dump({"ingress_rules": ingress_rules, "egress_rules": egress_rules}, f, indent=2)

        return {
            "success": True,
            "message": "Security group rules updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error updating security group rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))
