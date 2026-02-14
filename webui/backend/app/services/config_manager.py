import json
import logging
import os
import hashlib
import re
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:

    def __init__(self, terraform_dir: str = None):
        self.terraform_dir = Path(terraform_dir) if terraform_dir else Path(os.environ.get('TERRAFORM_DIR', '/app/terraform'))
        self._boto3_client = None
        self._parameter_name_cache = None

    def _read_tfvar(self, key: str, default: str = "default") -> str:
        tfvars_path = self.terraform_dir / 'terraform.tfvars'
        if not tfvars_path.exists():
            return default
        try:
            with open(tfvars_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        match = re.match(r'^(\w+)\s*=\s*(?:"([^"]*)"|(\S+))', line)
                        if match and match.group(1) == key:
                            return (match.group(2) or match.group(3) or "").strip() or default
        except Exception as e:
            logger.warning(f"Failed to read {key} from tfvars: {e}")
        return default

    def _get_name_prefix_from_tfvars(self) -> str:
        return self._read_tfvar('name_prefix')

    def _get_creator_team_from_tfvars(self) -> tuple:
        return self._read_tfvar('creator'), self._read_tfvar('team')

    def _get_credentials_hash(self) -> str:
        access_key = os.environ.get('AWS_ACCESS_KEY_ID', '')
        if not access_key:
            logger.debug("No AWS_ACCESS_KEY_ID found, using 'default' hash")
            return 'default'
        hash_value = hashlib.sha256(access_key.encode('utf-8')).hexdigest()[:12]
        logger.debug(f"Generated credentials hash: {hash_value}")
        return hash_value

    @property
    def _namespace_prefix(self) -> str:
        if not hasattr(self, '_namespace_prefix_cache') or self._namespace_prefix_cache is None:
            creds_hash = self._get_credentials_hash()
            name_prefix = self._get_name_prefix_from_tfvars()
            safe_prefix = ''.join(c if c.isalnum() or c in '-_' else '-' for c in name_prefix)[:64]
            self._namespace_prefix_cache = f"/dogstac-{safe_prefix}/{creds_hash}"
            logger.debug(f"Namespace prefix: {self._namespace_prefix_cache}")
        return self._namespace_prefix_cache

    @property
    def parameter_name(self) -> str:
        if self._parameter_name_cache is None:
            self._parameter_name_cache = f"{self._namespace_prefix}/config/variables"
            logger.debug(f"Using Parameter Store key: {self._parameter_name_cache}")
        return self._parameter_name_cache

    @property
    def key_parameter_name(self) -> str:
        return f"{self._namespace_prefix}/key"

    @property
    def ssm_client(self):
        if self._boto3_client is None:
            try:
                import boto3
                region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION') or 'ap-northeast-2'
                self._boto3_client = boto3.client('ssm', region_name=region)
            except Exception as e:
                logger.warning(f"Failed to create SSM client: {e}")
                return None
        return self._boto3_client

    def check_name_prefix_available(self, prefix: str) -> Dict:
        if not self.ssm_client:
            return {"available": True, "error": "SSM client not available, skipping check"}
        try:
            safe = ''.join(c if c.isalnum() or c in '-_' else '-' for c in prefix)[:64]
            search_path = f"/dogstac-{safe}"
            response = self.ssm_client.get_parameters_by_path(
                Path=search_path, Recursive=True, MaxResults=1,
            )
            if response.get('Parameters'):
                logger.debug(f"name_prefix '{prefix}' is already in use")
                return {"available": False}
            logger.debug(f"name_prefix '{prefix}' is available")
            return {"available": True}
        except Exception as e:
            logger.warning(f"Error checking name_prefix availability: {e}")
            return {"available": True, "error": str(e)}

    def save_config(self, variables: Dict[str, str]) -> bool:
        if not self.ssm_client:
            logger.warning("SSM client not available, skipping Parameter Store save")
            return False
        try:
            config_json = json.dumps(variables, indent=2)
            self.ssm_client.put_parameter(
                Name=self.parameter_name,
                Value=config_json,
                Type='SecureString',
                Overwrite=True,
                Description='Terraform WebUI configuration variables',
            )
            logger.info(f"Saved {len(variables)} variables to Parameter Store: {self.parameter_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config to Parameter Store: {e}")
            return False

    def load_config(self) -> Optional[Dict[str, str]]:
        if not self.ssm_client:
            logger.warning("SSM client not available, cannot load from Parameter Store")
            return None

        tfvars_path = self.terraform_dir / 'terraform.tfvars'

        if tfvars_path.exists():
            try:
                response = self.ssm_client.get_parameter(Name=self.parameter_name, WithDecryption=True)
                variables = json.loads(response['Parameter']['Value'])
                logger.info(f"Loaded {len(variables)} variables from Parameter Store: {self.parameter_name}")
                return variables
            except self.ssm_client.exceptions.ParameterNotFound:
                logger.info(f"Parameter not found: {self.parameter_name}")
                return None
            except Exception as e:
                logger.error(f"Failed to load config from Parameter Store: {e}")
                return None

        logger.info("terraform.tfvars not found, attempting auto-discovery...")
        try:
            creds_hash = self._get_credentials_hash()
            paginator = self.ssm_client.get_paginator('describe_parameters')
            for page in paginator.paginate(
                ParameterFilters=[{
                    'Key': 'Name',
                    'Option': 'BeginsWith',
                    'Values': ['/dogstac-'],
                }],
            ):
                for param in page.get('Parameters', []):
                    name = param['Name']
                    if f"/{creds_hash}/" in name and name.endswith('/config/variables'):
                        logger.debug(f"Auto-discovery matched: {name}")
                        resp = self.ssm_client.get_parameter(Name=name, WithDecryption=True)
                        variables = json.loads(resp['Parameter']['Value'])
                        logger.info(f"Auto-discovered config at: {name} ({len(variables)} variables)")
                        return variables
            logger.info("No matching parameters found during auto-discovery")
            return None
        except Exception as e:
            logger.warning(f"Auto-discovery failed: {e}")
            return None

    def delete_config(self) -> bool:
        if not self.ssm_client:
            logger.warning("SSM client not available")
            return False
        try:
            self.ssm_client.delete_parameter(Name=self.parameter_name)
            logger.info(f"Deleted config from Parameter Store: {self.parameter_name}")
            return True
        except self.ssm_client.exceptions.ParameterNotFound:
            return True
        except Exception as e:
            logger.error(f"Failed to delete config from Parameter Store: {e}")
            return False

    def config_exists(self) -> bool:
        return self.load_config() is not None

    def save_key(self, private_key_content: str, key_name: str = "") -> bool:
        if not self.ssm_client:
            logger.warning("SSM client not available, skipping key save")
            return False
        try:
            value = private_key_content
            if key_name:
                value = json.dumps({"key_name": key_name, "private_key": private_key_content})
            size_kb = len(value.encode('utf-8')) / 1024
            tier = "Advanced" if size_kb > 4 else "Standard"
            self.ssm_client.put_parameter(
                Name=self.key_parameter_name,
                Value=value,
                Type='SecureString',
                Tier=tier,
                Overwrite=True,
                Description=f'SSH key for EC2 (key_name={key_name})',
            )
            logger.info(f"Saved key to Parameter Store: {self.key_parameter_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save key to Parameter Store: {e}")
            return False

    def load_key(self) -> Optional[Dict[str, str]]:
        if not self.ssm_client:
            logger.warning("SSM client not available, cannot load key")
            return None
        try:
            response = self.ssm_client.get_parameter(Name=self.key_parameter_name, WithDecryption=True)
            raw = response['Parameter']['Value']
            try:
                data = json.loads(raw)
                logger.info(f"Loaded key '{data.get('key_name', '')}' from Parameter Store: {self.key_parameter_name}")
                return data
            except json.JSONDecodeError:
                return {"key_name": "", "private_key": raw}
        except Exception as e:
            if "ParameterNotFound" in str(type(e).__name__) or "ParameterNotFound" in str(e):
                logger.debug(f"Key not found in Parameter Store: {self.key_parameter_name}")
            else:
                logger.warning(f"Failed to load key from Parameter Store: {e}")
            return None

    def generate_bucket_name(self, name_prefix: str) -> str:
        creds_hash = self._get_credentials_hash()
        safe = name_prefix.lower().replace('_', '-')
        safe = ''.join(c if c.isalnum() or c == '-' else '-' for c in safe)[:32]
        bucket_name = f"dogstac-{safe}-{creds_hash}"
        logger.info(f"Generated bucket name: {bucket_name}")
        return bucket_name

    def generate_dynamodb_table_name(self) -> str:
        creds_hash = self._get_credentials_hash()
        table_name = f"dogstac-{creds_hash}-locks"
        logger.info(f"Generated DynamoDB table name: {table_name}")
        return table_name
