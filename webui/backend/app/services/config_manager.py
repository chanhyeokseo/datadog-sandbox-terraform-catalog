"""
Configuration Manager for storing/loading terraform variables to/from AWS Parameter Store
"""
import json
import logging
import os
import hashlib
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

    def _get_credentials_hash(self) -> str:
        """
        Generate hash from AWS Access Key ID for namespacing
        Uses only Access Key ID (public identifier) for practical rotation support
        """
        access_key = os.environ.get('AWS_ACCESS_KEY_ID', '')

        if not access_key:
            logger.debug("No AWS_ACCESS_KEY_ID found, using 'default' hash")
            return 'default'

        # SHA256 hash, use first 12 characters (sufficient uniqueness, readable length)
        hash_obj = hashlib.sha256(access_key.encode('utf-8'))
        hash_value = hash_obj.hexdigest()[:12]

        logger.debug(f"Generated credentials hash: {hash_value}")
        return hash_value

    @property
    def parameter_name(self) -> str:
        """
        Generate parameter name based on AWS credentials hash and creator/team
        Format: /dogstac-<hash>/<creator>-<team>/config/variables
        """
        if self._parameter_name_cache is None:
            creds_hash = self._get_credentials_hash()
            creator, team = self._get_creator_team_from_tfvars()

            # Sanitize names for use in parameter store path
            safe_creator = ''.join(c if c.isalnum() or c in '-_' else '-' for c in creator)[:64]
            safe_team = ''.join(c if c.isalnum() or c in '-_' else '-' for c in team)[:64]

            self._parameter_name_cache = f"/dogstac-{creds_hash}/{safe_creator}-{safe_team}/config/variables"
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
        Load terraform variables from Parameter Store with auto-discovery

        Strategy:
        1. If terraform.tfvars exists, use exact path based on creator/team
        2. If not, search under /dogstac-<hash> prefix to auto-discover

        Returns:
            Dictionary of variable name -> value, or None if not found/error
        """
        if not self.ssm_client:
            logger.warning("SSM client not available, cannot load from Parameter Store")
            return None

        tfvars_path = self.terraform_dir / 'terraform.tfvars'

        # Try exact path first (when terraform.tfvars exists)
        if tfvars_path.exists():
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

        # Auto-discovery: search under /dogstac-<hash> when terraform.tfvars doesn't exist
        logger.info("terraform.tfvars not found, attempting auto-discovery...")

        try:
            creds_hash = self._get_credentials_hash()
            search_path = f"/dogstac-{creds_hash}"

            logger.debug(f"Searching for config under: {search_path}")

            response = self.ssm_client.get_parameters_by_path(
                Path=search_path,
                Recursive=True,
                WithDecryption=True
            )

            if not response['Parameters']:
                logger.info(f"No parameters found under {search_path} (first run or not yet configured)")
                return None

            # Use the first parameter found (typically only one exists per hash)
            param = response['Parameters'][0]
            config_json = param['Value']
            variables = json.loads(config_json)

            logger.info(f"✅ Auto-discovered config at: {param['Name']} ({len(variables)} variables)")
            return variables

        except Exception as e:
            logger.warning(f"Auto-discovery failed: {e}")
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

    def generate_bucket_name(self, creator: str, team: str) -> str:
        """
        Generate S3 bucket name using AWS credential hash
        Format: dogstac-<creator>-<hash>
        (Max 63 chars: dogstac=7, creator=max 32, hash=12, hyphens=2 = max 53 chars)

        Args:
            creator: Creator name (used in bucket name, truncated if needed)
            team: Team name (not used)

        Returns:
            Generated bucket name with hash
        """
        creds_hash = self._get_credentials_hash()

        # Sanitize creator name for S3 bucket
        safe_creator = creator.lower().replace('_', '-')
        safe_creator = ''.join(c if c.isalnum() or c == '-' else '-' for c in safe_creator)
        safe_creator = safe_creator[:32]  # Limit length

        # Format: dogstac-{creator}-{hash}
        bucket_name = f"dogstac-{safe_creator}-{creds_hash}"

        logger.info(f"Generated bucket name: {bucket_name}")
        return bucket_name

    def generate_dynamodb_table_name(self, creator: str, team: str) -> str:
        """
        Generate DynamoDB table name using AWS credential hash
        Format: dogstac-<hash>-locks

        Args:
            creator: Creator name (not used due to length constraints)
            team: Team name (not used due to length constraints)

        Returns:
            Generated table name with hash
        """
        creds_hash = self._get_credentials_hash()

        # Simple format for table name
        table_name = f"dogstac-{creds_hash}-locks"

        logger.info(f"Generated DynamoDB table name: {table_name}")
        return table_name
