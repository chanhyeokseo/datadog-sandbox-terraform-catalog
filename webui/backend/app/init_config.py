#!/usr/bin/env python3
"""
Initialize terraform configuration from Parameter Store
Run this at container startup to restore config from Parameter Store
"""
import os
import sys
import logging
from pathlib import Path

# Setup logging
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def write_tfvars_file(variables: dict, tfvars_path: Path):
    """Write variables dictionary to terraform.tfvars file"""
    try:
        # Ensure directory exists
        tfvars_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to file
        with open(tfvars_path, 'w', encoding='utf-8') as f:
            for key, value in sorted(variables.items()):
                # Handle different value types
                if value is None or value == '':
                    continue

                # Escape quotes in string values
                escaped_value = str(value).replace('"', '\\"')
                f.write(f'{key} = "{escaped_value}"\n')

        logger.info(f"✅ Written {len(variables)} variables to {tfvars_path}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to write tfvars file: {e}")
        return False


def _apply_overrides_to_content(content: str, overrides: dict) -> str:
    import re as _re
    lines = content.splitlines(keepends=True)
    applied = set()
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            var = stripped.split('=', 1)[0].strip()
            if var in overrides:
                result.append(f'{var} = "{overrides[var]}"\n')
                applied.add(var)
                continue
        result.append(line)
    for var in sorted(set(overrides) - applied):
        result.append(f'{var} = "{overrides[var]}"\n')
    return ''.join(result)


def sync_tfvars_from_ssm():
    from app.services.config_manager import ConfigManager
    from app.services.terraform_parser import TerraformParser
    from app.config import get_root_allowed_variable_names

    terraform_dir = Path(os.environ.get('TERRAFORM_DIR', '/app/terraform'))
    instances_dir = terraform_dir / 'instances'

    try:
        config_manager = ConfigManager(terraform_dir=str(terraform_dir))
        name_prefix = config_manager._get_name_prefix_from_tfvars()
        if name_prefix == 'default':
            logger.debug("No name_prefix configured, skipping Parameter Store tfvars sync")
            return False
    except Exception as e:
        logger.warning(f"Could not initialize ConfigManager for tfvars sync: {e}")
        return False

    logger.info("Syncing tfvars from Parameter Store...")

    root_path = terraform_dir / 'terraform.tfvars'
    root_content = config_manager.load_tfvars()
    if root_content:
        root_path.parent.mkdir(parents=True, exist_ok=True)
        root_path.write_text(root_content, encoding='utf-8')
        logger.info("Restored root terraform.tfvars from Parameter Store")
    elif root_path.exists():
        root_content = root_path.read_text(encoding='utf-8')
        logger.info("Using existing local root terraform.tfvars")
    else:
        logger.debug("Root tfvars not available")
        return False

    allowed = get_root_allowed_variable_names()
    filtered_lines = []
    for line in root_content.splitlines(keepends=True):
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            filtered_lines.append(line)
            continue
        var = stripped.split('=', 1)[0].strip()
        if var in allowed:
            filtered_lines.append(line)
    common_content = ''.join(filtered_lines)

    overrides_raw = config_manager.load_instance_overrides() or ""
    overrides_map = TerraformParser.parse_overrides(overrides_raw)

    restored = 0
    if instances_dir.exists():
        for inst_dir in sorted(instances_dir.iterdir()):
            if not inst_dir.is_dir() or not (inst_dir / 'main.tf').exists():
                continue
            inst_name = inst_dir.name
            inst_content = common_content
            if inst_name in overrides_map:
                inst_content = _apply_overrides_to_content(inst_content, overrides_map[inst_name])
            (inst_dir / 'terraform.tfvars').write_text(inst_content, encoding='utf-8')
            restored += 1

    logger.info(f"Restored {restored} instance tfvars ({len(overrides_map)} with overrides)")
    return True


def regenerate_backend_files():
    from app.services.config_manager import ConfigManager
    from app.services.backend_manager import BackendManager
    from app.services.instance_discovery import get_resource_id_for_instance

    terraform_dir = Path(os.environ.get('TERRAFORM_DIR', '/app/terraform'))
    instances_dir = terraform_dir / 'instances'

    if not instances_dir.exists():
        return

    config_manager = ConfigManager(terraform_dir=str(terraform_dir))
    name_prefix = config_manager._get_name_prefix_from_tfvars()

    if name_prefix == 'default':
        logger.debug("No name_prefix configured, skipping backend.tf regeneration")
        return

    bucket_name = config_manager.generate_bucket_name(name_prefix)
    table_name = config_manager.generate_dynamodb_table_name()
    region = config_manager._get_region()

    import boto3
    try:
        s3_client = boto3.client('s3', region_name=region)
        paginator = s3_client.get_paginator('list_objects_v2')
        s3_state_keys = {}
        for page in paginator.paginate(Bucket=bucket_name, Prefix='instances/'):
            for obj in page.get('Contents', []):
                key = obj['Key']
                if key.endswith('/terraform.tfstate'):
                    parts = key.split('/')
                    if len(parts) == 3:
                        s3_state_keys[parts[1]] = parts[1]
    except Exception as e:
        logger.debug(f"Could not list S3 state files: {e}")
        s3_state_keys = {}

    manager = BackendManager(region=region)
    count = 0

    for instance_dir in sorted(instances_dir.iterdir()):
        if not instance_dir.is_dir() or not (instance_dir / "main.tf").exists():
            continue

        backend_tf = instance_dir / "backend.tf"
        if backend_tf.exists():
            continue

        resource_id = get_resource_id_for_instance(instance_dir)
        dir_name = instance_dir.name

        if resource_id in s3_state_keys:
            instance_name = resource_id
        elif dir_name in s3_state_keys:
            instance_name = dir_name
        else:
            instance_name = resource_id

        backend_content = manager.generate_backend_config(
            bucket_name=bucket_name,
            instance_name=instance_name,
            table_name=table_name
        )
        backend_tf.write_text(backend_content, encoding="utf-8")
        count += 1
        logger.info(f"Regenerated backend.tf for {dir_name} (key: instances/{instance_name}/terraform.tfstate)")

    if count > 0:
        logger.info(f"✓ Regenerated {count} backend.tf files")


def restore_key_from_parameter_store():
    from app.services.config_manager import ConfigManager

    terraform_dir = Path(os.environ.get('TERRAFORM_DIR', '/app/terraform'))
    config_manager = ConfigManager(terraform_dir=str(terraform_dir))
    key_data = config_manager.load_key()
    if not key_data or not key_data.get("private_key"):
        logger.debug("No key found in Parameter Store")
        return False

    key_name = key_data.get("key_name", "")
    if not key_name:
        logger.debug("Key in Parameter Store has no key_name, skipping local restore")
        return False

    keys_dir = terraform_dir / "keys"
    pem_path = keys_dir / f"{key_name}.pem"
    if pem_path.exists():
        logger.debug(f"Key '{key_name}' already exists locally")
        return True

    try:
        keys_dir.mkdir(parents=True, exist_ok=True)
        pem_path.write_text(key_data["private_key"], encoding="utf-8")
        pem_path.chmod(0o600)
        logger.info(f"Restored key '{key_name}' from Parameter Store to {pem_path}")
        return True
    except Exception as e:
        logger.warning(f"Failed to restore key locally: {e}")
        return False


def init_from_parameter_store():
    from app.services.config_manager import ConfigManager

    logger.info("Initializing configuration...")

    terraform_dir = os.environ.get('TERRAFORM_DIR', '/app/terraform')
    tfvars_path = Path(terraform_dir) / 'terraform.tfvars'

    ssm_synced = sync_tfvars_from_ssm()

    if ssm_synced:
        logger.info("Configuration restored from Parameter Store (tfvars)")
        regenerate_backend_files()
        restore_key_from_parameter_store()
        return True

    if tfvars_path.exists():
        logger.info("Using existing local terraform.tfvars")
        regenerate_backend_files()
        restore_key_from_parameter_store()
        return True

    logger.info("Loading configuration from Parameter Store...")
    config_manager = ConfigManager()
    variables = config_manager.load_config()

    if variables is None:
        logger.info("No configuration found in Parameter Store (first run)")
        return True

    if not variables:
        logger.warning("Empty configuration in Parameter Store")
        return True

    success = write_tfvars_file(variables, tfvars_path)

    if success:
        logger.info(f"Initialized config from Parameter Store ({len(variables)} variables)")
        logger.info("Retrying tfvars sync with resolved namespace...")
        sync_tfvars_from_ssm()
        regenerate_backend_files()
        restore_key_from_parameter_store()
    else:
        logger.error("Failed to initialize config from Parameter Store")

    return success


def _seed_from_image(terraform_dir: Path) -> dict:
    source_dir = Path('/app/terraform-source')
    result = {"instances": False, "modules": False, "apps": False}

    instances_dir = terraform_dir / 'instances'
    has_instances = instances_dir.exists() and any(
        (d / 'main.tf').exists() for d in instances_dir.iterdir() if d.is_dir()
    ) if instances_dir.exists() else False

    if not has_instances and (source_dir / 'instances').exists():
        import shutil
        if instances_dir.exists():
            shutil.rmtree(instances_dir)
        shutil.copytree(source_dir / 'instances', instances_dir)
        result["instances"] = True
        logger.info(f"Re-seeded instances from image ({sum(1 for d in instances_dir.iterdir() if d.is_dir())} dirs)")

    modules_dir = terraform_dir / 'modules'
    if not modules_dir.exists() and (source_dir / 'modules').exists():
        import shutil
        shutil.copytree(source_dir / 'modules', modules_dir)
        result["modules"] = True
        logger.info("Re-seeded modules from image")

    apps_dir = terraform_dir / 'apps'
    if not apps_dir.exists() and (source_dir / 'apps').exists():
        import shutil
        shutil.copytree(source_dir / 'apps', apps_dir)
        result["apps"] = True
        logger.info("Re-seeded apps from image")

    return result


def ensure_terraform_data() -> dict:
    terraform_dir = Path(os.environ.get('TERRAFORM_DIR', '/app/terraform'))
    terraform_dir.mkdir(parents=True, exist_ok=True)

    seed_result = _seed_from_image(terraform_dir)
    seeded = any(seed_result.values())

    tfvars_missing = not (terraform_dir / 'terraform.tfvars').exists()

    config_synced = False
    if seeded or tfvars_missing:
        logger.info(f"Recovery needed: seeded={seeded}, tfvars_missing={tfvars_missing}")
        config_synced = init_from_parameter_store()

    return {
        "seeded": seed_result,
        "tfvars_missing": tfvars_missing,
        "config_synced": config_synced,
        "recovered": seeded or (tfvars_missing and config_synced),
    }


if __name__ == '__main__':
    try:
        success = init_from_parameter_store()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}", exc_info=True)
        sys.exit(1)
