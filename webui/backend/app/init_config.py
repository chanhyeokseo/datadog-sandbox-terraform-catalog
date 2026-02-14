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
logging.basicConfig(
    level=logging.INFO,
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


def get_s3_bucket_name():
    """Get S3 bucket name from ConfigManager"""
    from app.services.config_manager import ConfigManager

    try:
        # Try to get creator and team from existing tfvars or environment
        terraform_dir = os.environ.get('TERRAFORM_DIR', '/app/terraform')
        tfvars_path = Path(terraform_dir) / 'terraform.tfvars'

        creator = os.environ.get('CREATOR', 'default')
        team = os.environ.get('TEAM', 'default')

        # If tfvars exists, try to read creator/team from it
        if tfvars_path.exists():
            config_manager = ConfigManager()
            creator_from_tfvars, team_from_tfvars = config_manager._get_creator_team_from_tfvars()
            if creator_from_tfvars != 'default':
                creator = creator_from_tfvars
            if team_from_tfvars != 'default':
                team = team_from_tfvars

        config_manager = ConfigManager()
        bucket_name = config_manager.generate_bucket_name(creator, team)
        return bucket_name
    except Exception as e:
        logger.warning(f"Could not determine S3 bucket name: {e}")
        return None


def sync_from_s3():
    """Download configuration files from S3"""
    from app.services.s3_config_manager import S3ConfigManager

    bucket_name = get_s3_bucket_name()
    if not bucket_name:
        logger.debug("S3 bucket name not available, skipping S3 sync")
        return False

    logger.info(f"📦 Syncing configuration from S3 bucket: {bucket_name}")

    terraform_dir = Path(os.environ.get('TERRAFORM_DIR', '/app/terraform'))
    instances_dir = terraform_dir / 'instances'

    s3_manager = S3ConfigManager(bucket_name)

    # Download root terraform.tfvars
    root_success = s3_manager.download_root_tfvars(terraform_dir)
    if root_success:
        logger.info("✓ Downloaded root terraform.tfvars from S3")
    else:
        logger.debug("Root terraform.tfvars not found in S3 (may not exist yet)")

    # Download all instance terraform.tfvars
    results = s3_manager.sync_all_instances_from_s3(instances_dir)

    success_count = sum(1 for success in results.values() if success)
    if success_count > 0:
        logger.info(f"✓ Downloaded {success_count} instance tfvars from S3")
    else:
        logger.debug("No instance tfvars found in S3 (may not exist yet)")

    return root_success or success_count > 0


def regenerate_backend_files():
    from app.services.config_manager import ConfigManager
    from app.services.backend_manager import BackendManager
    from app.services.instance_discovery import get_resource_id_for_instance

    terraform_dir = Path(os.environ.get('TERRAFORM_DIR', '/app/terraform'))
    instances_dir = terraform_dir / 'instances'

    if not instances_dir.exists():
        return

    config_manager = ConfigManager(terraform_dir=str(terraform_dir))
    creator, team = config_manager._get_creator_team_from_tfvars()

    if creator == 'default' and team == 'default':
        logger.debug("No creator/team configured, skipping backend.tf regeneration")
        return

    bucket_name = config_manager.generate_bucket_name(creator, team)
    table_name = config_manager.generate_dynamodb_table_name(creator, team)
    region = os.environ.get('AWS_REGION', 'ap-northeast-2')

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

    s3_synced = sync_from_s3()

    if s3_synced:
        logger.info("Configuration restored from S3")
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
        logger.info("Retrying S3 sync with resolved bucket name...")
        sync_from_s3()
        regenerate_backend_files()
        restore_key_from_parameter_store()
    else:
        logger.error("Failed to initialize config from Parameter Store")

    return success


if __name__ == '__main__':
    try:
        success = init_from_parameter_store()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}", exc_info=True)
        sys.exit(1)
