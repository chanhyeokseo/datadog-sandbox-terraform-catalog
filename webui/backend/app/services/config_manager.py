"""
Configuration Manager for storing/loading terraform variables to/from AWS Parameter Store
"""
import json
import logging
import os
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages terraform configuration in AWS Parameter Store"""

    def __init__(self, terraform_dir: str = None):
        self.terraform_dir = Path(terraform_dir) if terraform_dir else Path(os.environ.get('TERRAFORM_DIR', '/app/terraform'))
        self._boto3_client = None
        self._parameter_name_cache = None

    def _get_creator_team_from_tfvars(self) -> tuple:
        """Read creator and team from terraform.tfvars"""
        tfvars_path = self.terraform_dir / 'terraform.tfvars'
        creator = 'default'
        team = 'default'

        if tfvars_path.exists():
            try:
                with open(tfvars_path, 'r', encoding='utf-8') as f:
                    import re
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            match = re.match(r'^(\w+)\s*=\s*(?:"([^"]*)"|(\S+))', line)
                            if match:
                                key = match.group(1)
                                value = (match.group(2) or match.group(3) or "").strip()
                                if key == 'creator':
                                    creator = value
                                elif key == 'team':
                                    team = value
            except Exception as e:
                logger.warning(f"Failed to read creator/team from tfvars: {e}")

        return creator, team

    @property
    def parameter_name(self) -> str:
        """Generate parameter name based on creator and team"""
        if self._parameter_name_cache is None:
            creator, team = self._get_creator_team_from_tfvars()
            # Sanitize names for use in parameter store path
            safe_creator = ''.join(c if c.isalnum() or c in '-_' else '-' for c in creator)[:64]
            safe_team = ''.join(c if c.isalnum() or c in '-_' else '-' for c in team)[:64]
            self._parameter_name_cache = f"/dogstac-{safe_creator}-{safe_team}/config/variables"
            logger.debug(f"Using Parameter Store key: {self._parameter_name_cache}")
        return self._parameter_name_cache

    @property
    def ssm_client(self):
        """Lazy load boto3 SSM client"""
        if self._boto3_client is None:
            try:
                import boto3
                import os

                # Get region from environment or default
                region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION') or 'ap-northeast-2'

                self._boto3_client = boto3.client('ssm', region_name=region)
            except Exception as e:
                logger.warning(f"Failed to create SSM client: {e}")
                return None
        return self._boto3_client

    def save_config(self, variables: Dict[str, str]) -> bool:
        """
        Save terraform variables to Parameter Store as JSON

        Args:
            variables: Dictionary of variable name -> value

        Returns:
            True if successful, False otherwise
        """
        if not self.ssm_client:
            logger.warning("SSM client not available, skipping Parameter Store save")
            return False

        try:
            # Convert dict to JSON string
            config_json = json.dumps(variables, indent=2)

            # Save to Parameter Store
            self.ssm_client.put_parameter(
                Name=self.parameter_name,
                Value=config_json,
                Type='String',  # Use 'SecureString' if encryption needed at rest
                Overwrite=True,
                Description='Terraform WebUI configuration variables'
            )

            logger.info(f"Saved {len(variables)} variables to Parameter Store: {self.parameter_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to save config to Parameter Store: {e}")
            return False

    def load_config(self) -> Optional[Dict[str, str]]:
        """
        Load terraform variables from Parameter Store

        Returns:
            Dictionary of variable name -> value, or None if not found/error
        """
        if not self.ssm_client:
            logger.warning("SSM client not available, cannot load from Parameter Store")
            return None

        try:
            response = self.ssm_client.get_parameter(
                Name=self.parameter_name,
                WithDecryption=True
            )

            config_json = response['Parameter']['Value']
            variables = json.loads(config_json)

            logger.info(f"Loaded {len(variables)} variables from Parameter Store: {self.parameter_name}")
            return variables

        except self.ssm_client.exceptions.ParameterNotFound:
            logger.info(f"Parameter not found: {self.parameter_name} (first run or not yet configured)")
            return None
        except Exception as e:
            logger.error(f"Failed to load config from Parameter Store: {e}")
            return None

    def delete_config(self) -> bool:
        """
        Delete configuration from Parameter Store

        Returns:
            True if successful, False otherwise
        """
        if not self.ssm_client:
            logger.warning("SSM client not available")
            return False

        try:
            self.ssm_client.delete_parameter(Name=self.parameter_name)
            logger.info(f"Deleted config from Parameter Store: {self.parameter_name}")
            return True
        except self.ssm_client.exceptions.ParameterNotFound:
            logger.info(f"Parameter not found (already deleted): {self.parameter_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete config from Parameter Store: {e}")
            return False

    def config_exists(self) -> bool:
        """
        Check if configuration exists in Parameter Store

        Returns:
            True if exists, False otherwise
        """
        return self.load_config() is not None
