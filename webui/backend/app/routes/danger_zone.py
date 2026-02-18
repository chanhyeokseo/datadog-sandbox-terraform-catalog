from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict
from pathlib import Path
import logging
import asyncio
import os
import shutil
import json

from app.services.terraform_parser import TerraformParser
from app.services.terraform_runner import TerraformRunner
from app.services.config_manager import ConfigManager
from app.services.backend_manager import BackendManager

router = APIRouter(prefix="/api/danger-zone", tags=["danger-zone"])
logger = logging.getLogger(__name__)

TERRAFORM_DIR = os.environ.get("TERRAFORM_DIR", "/terraform")
parser = TerraformParser(TERRAFORM_DIR)
runner = TerraformRunner(TERRAFORM_DIR)

EXIT_SENTINEL_PREFIX = "__TF_EXIT__:"


def _var_files_for_resource(resource_id: str) -> Optional[List[str]]:
    resource_dir = runner.get_resource_directory(resource_id)
    if not resource_dir:
        return None
    inst_tfvars = resource_dir / "terraform.tfvars"
    if inst_tfvars.exists():
        return [str(inst_tfvars)]
    return None


def _get_enabled_resource_ids() -> List[str]:
    resources = parser.parse_all_resources()
    return [r.id for r in resources if r.status.value == "enabled"]


@router.get("/status")
async def danger_zone_status():
    try:
        enabled = _get_enabled_resource_ids()
        return {
            "enabled_count": len(enabled),
            "enabled_resources": enabled,
            "hard_reset_available": len(enabled) == 0,
        }
    except Exception as e:
        logger.error(f"Error getting danger zone status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/destroy-all/stream")
async def destroy_all_resources_stream():
    try:
        enabled = _get_enabled_resource_ids()
        if not enabled:
            async def empty():
                yield "No enabled resources to destroy.\n"
                yield f"{EXIT_SENTINEL_PREFIX}0\n"
            return StreamingResponse(empty(), media_type="text/plain")

        aws_env = parser.get_aws_env()

        async def stream():
            yield f"Found {len(enabled)} enabled resource(s) to destroy: {', '.join(enabled)}\n\n"
            all_success = True

            for idx, resource_id in enumerate(enabled):
                yield f"{'='*60}\n"
                yield f"[{idx+1}/{len(enabled)}] Destroying: {resource_id}\n"
                yield f"{'='*60}\n"

                var_files = _var_files_for_resource(resource_id)
                try:
                    async for chunk in runner.stream_destroy(
                        resource_id=resource_id,
                        auto_approve=True,
                        var_files=var_files,
                        env_extra=aws_env,
                    ):
                        if chunk.startswith(EXIT_SENTINEL_PREFIX):
                            code = chunk.strip().split(":")[1]
                            if code != "0":
                                all_success = False
                                yield f"\n[FAILED] {resource_id} destroy failed.\n\n"
                            else:
                                yield f"\n[OK] {resource_id} destroyed successfully.\n\n"
                        else:
                            yield chunk
                except Exception as e:
                    all_success = False
                    yield f"\n[ERROR] {resource_id}: {e}\n\n"

            yield f"{'='*60}\n"
            if all_success:
                yield "All resources destroyed successfully.\n"
            else:
                yield "Some resources failed to destroy. Check the log above.\n"
            yield f"{EXIT_SENTINEL_PREFIX}{'0' if all_success else '1'}\n"

        return StreamingResponse(stream(), media_type="text/plain")
    except Exception as e:
        logger.error(f"Error in destroy-all stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hard-reset")
async def hard_reset():
    enabled = _get_enabled_resource_ids()
    if enabled:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot hard reset while resources are active: {', '.join(enabled)}",
        )

    results: Dict[str, dict] = {}
    config_manager = ConfigManager(terraform_dir=TERRAFORM_DIR)

    results["ssh_key"] = _delete_ssh_keys(config_manager)
    results["parameter_store"] = _delete_parameter_store(config_manager)
    results["s3_bucket"] = await asyncio.to_thread(_delete_s3_bucket, config_manager)
    results["dynamodb"] = await asyncio.to_thread(_delete_dynamodb_table, config_manager)
    results["local_data"] = _clean_local_terraform_data()

    all_ok = all(r.get("success", False) for r in results.values())
    return {
        "success": all_ok,
        "message": "Hard reset completed." if all_ok else "Hard reset completed with some errors.",
        "details": results,
    }


def _resolve_key_pair_name() -> str:
    variables = parser.parse_variables()
    var_map = {v.name: v.value for v in variables}
    ec2_key = (var_map.get("ec2_key_name") or "").strip()
    if ec2_key:
        return ec2_key
    creator = (var_map.get("creator") or "").strip()
    team = (var_map.get("team") or "").strip()
    if creator and team:
        safe = lambda s: "".join(c if c.isalnum() or c in "-_" else "-" for c in s)[:64]
        return f"{safe(creator)}-{safe(team)}"
    return ""


def _delete_ssh_keys(config_manager: ConfigManager) -> dict:
    result = {"success": True, "actions": []}
    try:
        key_name = _resolve_key_pair_name()

        if key_name:
            try:
                region = (os.environ.get("AWS_REGION") or "ap-northeast-2").strip()
                import boto3
                ec2 = boto3.client("ec2", region_name=region)
                ec2.delete_key_pair(KeyName=key_name)
                result["actions"].append(f"Deleted EC2 key pair: {key_name}")
                logger.info(f"Deleted EC2 key pair: {key_name}")
            except Exception as e:
                msg = f"Failed to delete EC2 key pair '{key_name}': {e}"
                result["actions"].append(msg)
                logger.warning(msg)
        else:
            result["actions"].append("Could not determine key pair name (no ec2_key_name, creator, or team)")

        try:
            deleted = config_manager.ssm_client.delete_parameter(Name=config_manager.key_parameter_name)
            result["actions"].append(f"Deleted Parameter Store key: {config_manager.key_parameter_name}")
            logger.info(f"Deleted Parameter Store key: {config_manager.key_parameter_name}")
        except Exception as e:
            if "ParameterNotFound" in str(e):
                result["actions"].append("Parameter Store key not found (already clean)")
            else:
                msg = f"Failed to delete Parameter Store key: {e}"
                result["actions"].append(msg)
                logger.warning(msg)

        keys_dir = Path(TERRAFORM_DIR) / "keys"
        if keys_dir.exists():
            for pem in keys_dir.glob("*.pem"):
                pem.unlink()
                result["actions"].append(f"Deleted local key: {pem.name}")
            logger.info("Cleaned local keys directory")
        else:
            result["actions"].append("No local keys directory found")

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        logger.error(f"Error deleting SSH keys: {e}")
    return result


def _delete_parameter_store(config_manager: ConfigManager) -> dict:
    result = {"success": True, "actions": []}
    try:
        ssm = config_manager.ssm_client
        if not ssm:
            result["actions"].append("SSM client not available")
            return result

        prefix = config_manager._namespace_prefix
        try:
            paginator = ssm.get_paginator("describe_parameters")
            names_to_delete = []
            for page in paginator.paginate(
                ParameterFilters=[{"Key": "Name", "Option": "BeginsWith", "Values": [prefix]}]
            ):
                for param in page.get("Parameters", []):
                    names_to_delete.append(param["Name"])

            if names_to_delete:
                for batch_start in range(0, len(names_to_delete), 10):
                    batch = names_to_delete[batch_start : batch_start + 10]
                    ssm.delete_parameters(Names=batch)
                result["actions"].append(f"Deleted {len(names_to_delete)} parameter(s) under {prefix}")
                logger.info(f"Deleted {len(names_to_delete)} parameters under {prefix}")
            else:
                result["actions"].append(f"No parameters found under {prefix}")
        except Exception as e:
            msg = f"Failed to delete parameters under {prefix}: {e}"
            result["actions"].append(msg)
            result["success"] = False
            logger.warning(msg)
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        logger.error(f"Error deleting Parameter Store: {e}")
    return result


def _delete_s3_bucket(config_manager: ConfigManager) -> dict:
    result = {"success": True, "actions": []}
    try:
        name_prefix = config_manager._get_name_prefix_from_tfvars()
        bucket_name = config_manager.generate_bucket_name(name_prefix)
        region = (os.environ.get("AWS_REGION") or "ap-northeast-2").strip()

        import boto3
        s3 = boto3.resource("s3", region_name=region)
        bucket = s3.Bucket(bucket_name)

        try:
            boto3.client("s3", region_name=region).head_bucket(Bucket=bucket_name)
        except Exception:
            result["actions"].append(f"S3 bucket '{bucket_name}' does not exist")
            return result

        bucket.object_versions.delete()
        bucket.objects.delete()
        bucket.delete()
        result["actions"].append(f"Deleted S3 bucket: {bucket_name}")
        logger.info(f"Deleted S3 bucket: {bucket_name}")
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        result["actions"].append(f"Failed to delete S3 bucket: {e}")
        logger.error(f"Error deleting S3 bucket: {e}")
    return result


def _delete_dynamodb_table(config_manager: ConfigManager) -> dict:
    result = {"success": True, "actions": []}
    try:
        table_name = config_manager.generate_dynamodb_table_name()
        region = (os.environ.get("AWS_REGION") or "ap-northeast-2").strip()

        import boto3
        dynamodb = boto3.client("dynamodb", region_name=region)

        try:
            dynamodb.describe_table(TableName=table_name)
        except Exception:
            result["actions"].append(f"DynamoDB table '{table_name}' does not exist")
            return result

        dynamodb.delete_table(TableName=table_name)
        result["actions"].append(f"Deleted DynamoDB table: {table_name}")
        logger.info(f"Deleted DynamoDB table: {table_name}")
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        result["actions"].append(f"Failed to delete DynamoDB table: {e}")
        logger.error(f"Error deleting DynamoDB table: {e}")
    return result


def _clean_local_terraform_data() -> dict:
    result = {"success": True, "actions": []}
    try:
        td = Path(TERRAFORM_DIR)
        if not td.exists():
            result["actions"].append(f"Directory not found: {td}")
            return result

        shutil.rmtree(td)
        result["actions"].append(f"Deleted terraform-data directory: {td}")
        logger.info(f"Deleted terraform-data directory: {td}")
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        result["actions"].append(f"Failed to delete terraform-data: {e}")
        logger.error(f"Error deleting terraform-data: {e}")
    return result
