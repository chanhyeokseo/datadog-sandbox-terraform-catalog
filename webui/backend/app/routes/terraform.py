from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Body
from fastapi.responses import StreamingResponse
from typing import List, Dict, Optional
from pathlib import Path
import logging
import asyncio
import os

from app.models.schemas import (
    TerraformResource,
    TerraformStateResponse,
    TerraformVariable
)
from app.services.terraform_parser import TerraformParser
from app.services.terraform_runner import TerraformRunner

router = APIRouter(prefix="/api/terraform", tags=["terraform"])
logger = logging.getLogger(__name__)

TERRAFORM_DIR = os.environ.get("TERRAFORM_DIR", "/terraform")
parser = TerraformParser(TERRAFORM_DIR)
runner = TerraformRunner(TERRAFORM_DIR)

resource_locks: Dict[str, asyncio.Lock] = {}

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


@router.post("/init/{resource_id}")
async def terraform_init_resource(resource_id: str):
    try:
        resource_dir = runner.get_resource_directory(resource_id)
        
        if not resource_dir:
            raise HTTPException(status_code=404, detail="Resource directory not found")
        
        if not resource_dir.exists():
            raise HTTPException(status_code=404, detail="Resource directory does not exist")
        
        aws_env = parser.get_aws_env()
        env = {**os.environ, **aws_env} if aws_env else None
        logger.info(f"Force running terraform init in {resource_dir}")
        process = await asyncio.create_subprocess_exec(
            "terraform", "init", "-no-color", "-upgrade",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(resource_dir),
            env=env
        )
        
        stdout, stderr = await process.communicate()
        output = stdout.decode() + stderr.decode()
        
        if process.returncode == 0:
            logger.info(f"Successfully force initialized terraform in {resource_dir}")
            return {
                "success": True,
                "output": output,
                "resource_id": resource_id
            }
        else:
            logger.error(f"Failed to force initialize terraform in {resource_dir}: {output}")
            return {
                "success": False,
                "output": output,
                "resource_id": resource_id
            }
        
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


EC2_NS = "http://ec2.amazonaws.com/doc/2016-11-15/"


def _ec2_request(region: str, env: dict, action: str, extra_params: Optional[Dict[str, str]] = None) -> str:
    import requests
    from requests_aws4auth import AWS4Auth
    params = {"Action": action, "Version": "2016-11-15"}
    if extra_params:
        params.update(extra_params)
    auth = AWS4Auth(
        env.get("AWS_ACCESS_KEY_ID", ""),
        env.get("AWS_SECRET_ACCESS_KEY", ""),
        region,
        "ec2",
        session_token=env.get("AWS_SESSION_TOKEN") or None,
    )
    url = f"https://ec2.{region}.amazonaws.com/"
    resp = requests.get(url, params=params, auth=auth, timeout=30)
    resp.raise_for_status()
    return resp.text


def _parse_describe_vpcs(xml_text: str) -> list:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text)
    vpcs = []
    vpc_set = root.find(f".//{{{EC2_NS}}}vpcSet")
    if vpc_set is None:
        return vpcs
    for item in vpc_set.findall(f"{{{EC2_NS}}}item"):
        vpc_id_el = item.find(f"{{{EC2_NS}}}vpcId")
        cidr_el = item.find(f"{{{EC2_NS}}}cidrBlock")
        vpc_id = (vpc_id_el.text or "").strip() if vpc_id_el is not None else ""
        if not vpc_id:
            continue
        cidr = (cidr_el.text or "").strip() if cidr_el is not None else ""
        name = vpc_id
        tag_set = item.find(f"{{{EC2_NS}}}tagSet")
        if tag_set is not None:
            for tag in tag_set.findall(f"{{{EC2_NS}}}item"):
                key_el = tag.find(f"{{{EC2_NS}}}key")
                val_el = tag.find(f"{{{EC2_NS}}}value")
                if key_el is not None and key_el.text == "Name" and val_el is not None and val_el.text:
                    name = val_el.text.strip()
                    break
        vpcs.append({"id": vpc_id, "cidr": cidr, "name": name})
    return vpcs


def _parse_describe_subnets(xml_text: str) -> list:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text)
    subnets = []
    subnet_set = root.find(f".//{{{EC2_NS}}}subnetSet")
    if subnet_set is None:
        return subnets
    for item in subnet_set.findall(f"{{{EC2_NS}}}item"):
        sid_el = item.find(f"{{{EC2_NS}}}subnetId")
        cidr_el = item.find(f"{{{EC2_NS}}}cidrBlock")
        az_el = item.find(f"{{{EC2_NS}}}availabilityZone")
        sid = (sid_el.text or "").strip() if sid_el is not None else ""
        if not sid:
            continue
        cidr = (cidr_el.text or "").strip() if cidr_el is not None else ""
        az = (az_el.text or "").strip() if az_el is not None else ""
        name = sid
        tag_set = item.find(f"{{{EC2_NS}}}tagSet")
        if tag_set is not None:
            for tag in tag_set.findall(f"{{{EC2_NS}}}item"):
                key_el = tag.find(f"{{{EC2_NS}}}key")
                val_el = tag.find(f"{{{EC2_NS}}}value")
                if key_el is not None and key_el.text == "Name" and val_el is not None and val_el.text:
                    name = val_el.text.strip()
                    break
        subnets.append({"id": sid, "cidr": cidr, "az": az, "name": name})
    return subnets


@router.get("/aws/vpcs")
async def get_aws_vpcs(region: str = Query(..., description="AWS region")):
    try:
        env = parser.get_aws_env()
        if not env:
            raise HTTPException(status_code=400, detail="AWS credentials not configured")
        params = {"Filter.1.Name": "state", "Filter.1.Value.1": "available"}
        xml_text = await asyncio.to_thread(_ec2_request, region, env, "DescribeVpcs", params)
        vpcs = _parse_describe_vpcs(xml_text)
        return {"vpcs": vpcs}
    except Exception as e:
        logger.debug(f"get_aws_vpcs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/aws/subnets")
async def get_aws_subnets(region: str = Query(...), vpc_id: str = Query(...)):
    try:
        env = parser.get_aws_env()
        if not env:
            raise HTTPException(status_code=400, detail="AWS credentials not configured")
        params = {
            "Filter.1.Name": "vpc-id",
            "Filter.1.Value.1": vpc_id,
            "Filter.2.Name": "state",
            "Filter.2.Value.1": "available",
        }
        xml_text = await asyncio.to_thread(_ec2_request, region, env, "DescribeSubnets", params)
        subnets = _parse_describe_subnets(xml_text)
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


def _parse_ec2_error(xml_text: str) -> str:
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_text)
        err = root.find(f".//{{{EC2_NS}}}Error") or root.find(".//Error")
        if err is not None:
            code_el = err.find(f"{{{EC2_NS}}}Code") or err.find("Code")
            msg_el = err.find(f"{{{EC2_NS}}}Message") or err.find("Message")
            code = (code_el.text or "").strip() if code_el is not None else ""
            msg = (msg_el.text or "").strip() if msg_el is not None else ""
            out = f"{code}: {msg}" if code or msg else xml_text[:500]
            if code == "RequestExpired":
                out += " Check that your system clock is correct (and that the server running the app is in sync), then try again."
            return out
    except Exception:
        pass
    return xml_text[:500] if xml_text else "Unknown error"


def _parse_create_key_pair(xml_text: str) -> tuple:
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_text)
    err = root.find(f".//{{{EC2_NS}}}Errors")
    if err is not None:
        raise RuntimeError(_parse_ec2_error(xml_text))
    key_name_el = root.find(f".//{{{EC2_NS}}}keyName")
    key_material_el = root.find(f".//{{{EC2_NS}}}keyMaterial")
    key_name = (key_name_el.text or "").strip() if key_name_el is not None else ""
    key_material = (key_material_el.text or "").strip() if key_material_el is not None else ""
    if not key_material and key_material_el is not None and len(key_material_el) > 0:
        key_material = "".join(key_material_el.itertext()).strip()
    return key_name, key_material


@router.post("/aws/key-pair")
async def create_aws_key_pair():
    try:
        env = parser.get_aws_env()
        if not env:
            raise HTTPException(status_code=400, detail="AWS credentials not configured")
        region = (env.get("AWS_REGION") or "").strip() or "ap-northeast-2"
        try:
            variables = parser.parse_variables()
        except Exception as parse_err:
            logger.exception("parse_variables failed in create_aws_key_pair")
            raise HTTPException(status_code=500, detail=f"Failed to read config: {parse_err}")
        var_map = {v.name: v.value for v in variables}
        creator = (var_map.get("creator") or "").strip() or "creator"
        team = (var_map.get("team") or "").strip() or "team"
        safe = lambda s: "".join(c if c.isalnum() or c in "-_" else "-" for c in s)[:64]
        key_name = f"{safe(creator)}-{safe(team)}"
        params = {"KeyName": key_name}
        try:
            xml_text = await asyncio.to_thread(_ec2_request, region, env, "CreateKeyPair", params)
        except Exception as req_err:
            resp = getattr(req_err, "response", None)
            if resp is not None and getattr(resp, "text", None):
                try:
                    msg = _parse_ec2_error(resp.text)
                except Exception:
                    msg = (resp.text or str(req_err))[:500]
                logger.debug(f"CreateKeyPair API error: {msg}")
                raise HTTPException(status_code=500, detail=msg)
            raise HTTPException(status_code=500, detail=str(req_err))
        kname, private_key = _parse_create_key_pair(xml_text)
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
                "1. Select the Security Group from the list",
                "2. Click PLAN to preview changes",
                "3. Click DEPLOY to provision the Security Group",
                "4. Wait for the deployment to complete",
                "5. You can then deploy other resources"
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
    except Exception as e:
        logger.error(f"Error getting resources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resources/{resource_id}/refresh-status")
async def refresh_resource_status(resource_id: str):
    try:
        s3_statuses = parser._fetch_all_s3_statuses()
        target = parser.get_resource_by_id(resource_id)
        if not target:
            raise HTTPException(status_code=404, detail="Resource not found")
        resource_dir = runner.get_resource_directory(resource_id)
        dir_name = resource_dir.name if resource_dir else resource_id
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


@router.post("/onboarding/sync-to-parameter-store")
async def sync_to_parameter_store():
    """
    Sync terraform.tfvars to Parameter Store
    Should be called after onboarding is complete
    """
    try:
        success = parser.sync_to_parameter_store()
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to sync configuration to Parameter Store"
            )
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
                try:
                    async for chunk in runner.stream_apply(
                        resource_id=resource_id,
                        auto_approve=auto_approve,
                        var_files=var_files,
                        env_extra=aws_env
                    ):
                        yield chunk
                finally:
                    logger.info(f"Released lock for {resource_id} (apply)")
        
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
                try:
                    async for chunk in runner.stream_destroy(
                        resource_id=resource_id,
                        auto_approve=auto_approve,
                        var_files=var_files,
                        env_extra=aws_env
                    ):
                        yield chunk
                finally:
                    logger.info(f"Released lock for {resource_id} (destroy)")
        
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
        from pathlib import Path
        import re
        
        eks_config_file = runner.instances_dir / "eks-cluster" / "eks-config.auto.tfvars"
        
        if not eks_config_file.exists():
            return {"error": "EKS config file not found"}
        
        config = {}
        with open(eks_config_file, 'r') as f:
            content = f.read()
            
            for var in ['enable_node_group', 'enable_windows_node_group', 'enable_fargate', 
                       'endpoint_public_access', 'endpoint_private_access']:
                match = re.search(rf'{var}\s*=\s*(true|false)', content)
                if match:
                    config[var] = match.group(1) == 'true'
            
            for var in ['node_desired_size', 'node_min_size', 'node_max_size', 'node_disk_size',
                       'windows_node_desired_size', 'windows_node_min_size', 'windows_node_max_size', 
                       'windows_node_disk_size']:
                match = re.search(rf'{var}\s*=\s*(\d+)', content)
                if match:
                    config[var] = int(match.group(1))
            
            for var in ['node_capacity_type', 'windows_node_capacity_type', 'windows_node_ami_type']:
                match = re.search(rf'{var}\s*=\s*"([^"]+)"', content)
                if match:
                    config[var] = match.group(1)
            
            for var in ['node_instance_types', 'windows_node_instance_types', 'fargate_namespaces']:
                match = re.search(rf'{var}\s*=\s*\[(.*?)\]', content)
                if match:
                    list_content = match.group(1)
                    items = [item.strip().strip('"') for item in list_content.split(',') if item.strip()]
                    config[var] = items
        
        return config
    except Exception as e:
        logger.error(f"Error getting EKS config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/eks/config")
async def update_eks_config(config: Dict):
    try:
        from pathlib import Path
        
        eks_config_file = runner.instances_dir / "eks-cluster" / "eks-config.auto.tfvars"
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
