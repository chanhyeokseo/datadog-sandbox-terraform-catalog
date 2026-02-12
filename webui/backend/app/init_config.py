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


def init_from_parameter_store():
    """Load configuration from Parameter Store and create terraform.tfvars"""
    from app.services.config_manager import ConfigManager

    logger.info("🔄 Initializing configuration from Parameter Store...")

    # Get terraform directory from environment
    terraform_dir = os.environ.get('TERRAFORM_DIR', '/app/terraform')
    tfvars_path = Path(terraform_dir) / 'terraform.tfvars'

    # Check if tfvars already exists
    if tfvars_path.exists():
        logger.info(f"📄 terraform.tfvars already exists at {tfvars_path}")
        # Don't overwrite existing file - let Parameter Store be the backup
        return True

    # Load from Parameter Store
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
        logger.info(f"✅ Successfully initialized config from Parameter Store ({len(variables)} variables)")
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
