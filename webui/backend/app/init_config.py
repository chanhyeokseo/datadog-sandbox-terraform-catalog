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


def init_from_parameter_store():
    """Load configuration from Parameter Store and S3"""
    from app.services.config_manager import ConfigManager

    logger.info("🔄 Initializing configuration...")

    # Get terraform directory from environment
    terraform_dir = os.environ.get('TERRAFORM_DIR', '/app/terraform')
    tfvars_path = Path(terraform_dir) / 'terraform.tfvars'

    # Step 1: Try to sync from S3 first (most up-to-date)
    s3_synced = sync_from_s3()

    if s3_synced:
        logger.info("✅ Configuration restored from S3")
        return True

    # Step 2: If S3 sync failed, check if local tfvars exists
    if tfvars_path.exists():
        logger.info(f"📄 Using existing local terraform.tfvars")
        return True

    # Step 3: Fall back to Parameter Store
    logger.info("⚙️  Loading configuration from Parameter Store...")
    config_manager = ConfigManager()
    variables = config_manager.load_config()

    if variables is None:
        logger.info("ℹ️  No configuration found in Parameter Store (first run)")
        logger.info("   Configuration will be created during onboarding")
        return True

    if not variables:
        logger.warning("⚠️  Empty configuration in Parameter Store")
        return True

    # Write to terraform.tfvars
    success = write_tfvars_file(variables, tfvars_path)

    if success:
        logger.info(f"✅ Initialized config from Parameter Store ({len(variables)} variables)")
    else:
        logger.error("❌ Failed to initialize config from Parameter Store")

    return success


if __name__ == '__main__':
    try:
        success = init_from_parameter_store()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}", exc_info=True)
        sys.exit(1)
