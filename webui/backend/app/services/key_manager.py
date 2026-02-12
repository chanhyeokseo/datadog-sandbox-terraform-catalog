"""
AWS Parameter Store Key Manager
Manages SSH private keys in AWS Systems Manager Parameter Store
"""
import boto3
import logging
from typing import Optional, List, Dict
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class ParameterStoreKeyManager:
    """Manages SSH keys in AWS Parameter Store"""

    def __init__(self, region: str = "ap-northeast-2"):
        self.region = region
        self.ssm_client = boto3.client('ssm', region_name=region)
        self.key_prefix = "/ec2/keypairs"

    def upload_key(self, key_name: str, private_key_content: str, description: str = "") -> bool:
        """
        Upload a private key to Parameter Store

        Args:
            key_name: Name of the key (e.g., "chanhyeok")
            private_key_content: The PEM file content
            description: Optional description

        Returns:
            bool: True if successful
        """
        parameter_name = f"{self.key_prefix}/{key_name}"

        # Check size (Parameter Store Standard tier: 4KB limit)
        size_kb = len(private_key_content.encode('utf-8')) / 1024
        if size_kb > 4:
            logger.warning(f"Key {key_name} is {size_kb:.2f}KB, using Advanced tier")
            tier = "Advanced"
        else:
            tier = "Standard"

        try:
            self.ssm_client.put_parameter(
                Name=parameter_name,
                Description=description or f"SSH private key for EC2: {key_name}",
                Value=private_key_content,
                Type='SecureString',
                Tier=tier,
                Overwrite=True,
                Tags=[
                    {'Key': 'Type', 'Value': 'SSH-PrivateKey'},
                    {'Key': 'ManagedBy', 'Value': 'WebUI'},
                    {'Key': 'KeyName', 'Value': key_name}
                ]
            )
            logger.info(f"Uploaded key {key_name} to Parameter Store ({tier} tier)")
            return True

        except ClientError as e:
            logger.error(f"Failed to upload key {key_name}: {e}")
            raise

    def get_key(self, key_name: str) -> Optional[str]:
        """
        Retrieve a private key from Parameter Store

        Args:
            key_name: Name of the key

        Returns:
            str: The private key content, or None if not found
        """
        parameter_name = f"{self.key_prefix}/{key_name}"

        try:
            response = self.ssm_client.get_parameter(
                Name=parameter_name,
                WithDecryption=True
            )
            return response['Parameter']['Value']

        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                logger.debug(f"Key {key_name} not found in Parameter Store")
                return None
            logger.error(f"Failed to get key {key_name}: {e}")
            raise

    def list_keys(self) -> List[Dict[str, any]]:
        """
        List all SSH keys stored in Parameter Store

        Returns:
            List of key metadata
        """
        keys = []

        try:
            paginator = self.ssm_client.get_paginator('describe_parameters')
            page_iterator = paginator.paginate(
                ParameterFilters=[
                    {
                        'Key': 'Name',
                        'Option': 'BeginsWith',
                        'Values': [self.key_prefix]
                    }
                ]
            )

            for page in page_iterator:
                for param in page['Parameters']:
                    key_name = param['Name'].replace(f"{self.key_prefix}/", "")
                    keys.append({
                        "name": key_name,
                        "full_path": param['Name'],
                        "description": param.get('Description', ''),
                        "last_modified": param.get('LastModifiedDate'),
                        "version": param.get('Version', 1),
                        "tier": param.get('Tier', 'Standard')
                    })

            return keys

        except ClientError as e:
            logger.error(f"Failed to list keys: {e}")
            raise

    def delete_key(self, key_name: str) -> bool:
        """
        Delete a key from Parameter Store

        Args:
            key_name: Name of the key

        Returns:
            bool: True if successful
        """
        parameter_name = f"{self.key_prefix}/{key_name}"

        try:
            self.ssm_client.delete_parameter(Name=parameter_name)
            logger.info(f"Deleted key {key_name} from Parameter Store")
            return True

        except ClientError as e:
            if e.response['Error']['Code'] == 'ParameterNotFound':
                logger.warning(f"Key {key_name} not found, nothing to delete")
                return False
            logger.error(f"Failed to delete key {key_name}: {e}")
            raise

    def key_exists(self, key_name: str) -> bool:
        """Check if a key exists in Parameter Store"""
        parameter_name = f"{self.key_prefix}/{key_name}"

        try:
            self.ssm_client.describe_parameters(
                ParameterFilters=[
                    {
                        'Key': 'Name',
                        'Values': [parameter_name]
                    }
                ]
            )
            return True

        except ClientError:
            return False

    def get_key_info(self, key_name: str) -> Optional[Dict[str, any]]:
        """Get metadata about a key without retrieving the actual value"""
        parameter_name = f"{self.key_prefix}/{key_name}"

        try:
            response = self.ssm_client.describe_parameters(
                ParameterFilters=[
                    {
                        'Key': 'Name',
                        'Values': [parameter_name]
                    }
                ]
            )

            if response['Parameters']:
                param = response['Parameters'][0]
                return {
                    "name": key_name,
                    "full_path": param['Name'],
                    "description": param.get('Description', ''),
                    "last_modified": param.get('LastModifiedDate'),
                    "version": param.get('Version', 1),
                    "tier": param.get('Tier', 'Standard')
                }

            return None

        except ClientError as e:
            logger.error(f"Failed to get key info for {key_name}: {e}")
            return None

    def update_key_description(self, key_name: str, description: str) -> bool:
        """Update the description of a key"""
        parameter_name = f"{self.key_prefix}/{key_name}"

        try:
            # Get current value
            current = self.get_key(key_name)
            if not current:
                return False

            # Update with new description
            info = self.get_key_info(key_name)
            tier = info.get('tier', 'Standard') if info else 'Standard'

            self.ssm_client.put_parameter(
                Name=parameter_name,
                Description=description,
                Value=current,
                Type='SecureString',
                Tier=tier,
                Overwrite=True
            )

            logger.info(f"Updated description for key {key_name}")
            return True

        except ClientError as e:
            logger.error(f"Failed to update description for {key_name}: {e}")
            return False


# Fallback to local file system (for development/testing)
class LocalKeyManager:
    """Manages keys from local file system (fallback)"""

    def __init__(self, keys_dir: str = "./keys"):
        from pathlib import Path
        self.keys_dir = Path(keys_dir)
        self.keys_dir.mkdir(exist_ok=True)

    def get_key(self, key_name: str) -> Optional[str]:
        """Get key from local file system"""
        key_file = self.keys_dir / f"{key_name}.pem"
        if key_file.exists():
            return key_file.read_text(encoding='utf-8')
        return None

    def list_keys(self) -> List[Dict[str, any]]:
        """List keys from local file system"""
        keys = []
        for pem_file in self.keys_dir.glob("*.pem"):
            keys.append({
                "name": pem_file.stem,
                "source": "local",
                "path": str(pem_file)
            })
        return keys

    def upload_key(self, key_name: str, private_key_content: str, description: str = "") -> bool:
        """Save key to local file system"""
        key_file = self.keys_dir / f"{key_name}.pem"
        key_file.write_text(private_key_content, encoding='utf-8')
        key_file.chmod(0o600)
        logger.info(f"Saved key {key_name} to local file system")
        return True
