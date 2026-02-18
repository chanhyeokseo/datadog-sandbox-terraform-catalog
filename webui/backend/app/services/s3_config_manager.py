"""
S3 Config Manager for storing/loading terraform configuration files
Stores tfvars files in S3 for persistence across container restarts
"""
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class S3ConfigManager:
    """Manages terraform configuration files in S3"""

    def __init__(self, bucket_name: str, region: str = None):
        self.bucket_name = bucket_name
        self.region = region or os.environ.get('AWS_REGION', 'ap-northeast-2')
        self._s3_client = None

    @property
    def s3_client(self):
        """Lazy load boto3 S3 client"""
        if self._s3_client is None:
            try:
                import boto3
                self._s3_client = boto3.client('s3', region_name=self.region)
            except Exception as e:
                logger.warning(f"Failed to create S3 client: {e}")
                return None
        return self._s3_client

    def upload_file(self, local_path: Path, s3_key: str) -> bool:
        """
        Upload a file to S3

        Args:
            local_path: Local file path
            s3_key: S3 object key (e.g., "config/terraform.tfvars")

        Returns:
            True if successful, False otherwise
        """
        if not self.s3_client:
            logger.warning("S3 client not available")
            return False

        if not local_path.exists():
            logger.warning(f"Local file does not exist: {local_path}")
            return False

        try:
            with open(local_path, 'rb') as f:
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=f.read()
                )
            logger.info(f"✓ Uploaded {local_path.name} to s3://{self.bucket_name}/{s3_key}")
            return True
        except self.s3_client.exceptions.NoSuchBucket:
            logger.debug(f"S3 bucket does not exist yet: {self.bucket_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to upload {local_path} to S3: {e}")
            return False

    def download_file(self, s3_key: str, local_path: Path) -> bool:
        """
        Download a file from S3

        Args:
            s3_key: S3 object key
            local_path: Local destination path

        Returns:
            True if successful, False otherwise
        """
        if not self.s3_client:
            logger.warning("S3 client not available")
            return False

        try:
            # Create parent directories if needed
            local_path.parent.mkdir(parents=True, exist_ok=True)

            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )

            with open(local_path, 'wb') as f:
                f.write(response['Body'].read())

            logger.info(f"✓ Downloaded s3://{self.bucket_name}/{s3_key} to {local_path}")
            return True
        except self.s3_client.exceptions.NoSuchKey:
            logger.debug(f"S3 key not found: {s3_key}")
            return False
        except Exception as e:
            logger.error(f"Failed to download {s3_key} from S3: {e}")
            return False

    def list_files(self, prefix: str) -> List[str]:
        """
        List files in S3 with given prefix

        Args:
            prefix: S3 key prefix (e.g., "config/instances/")

        Returns:
            List of S3 keys
        """
        if not self.s3_client:
            logger.warning("S3 client not available")
            return []

        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            if 'Contents' not in response:
                return []

            return [obj['Key'] for obj in response['Contents']]
        except self.s3_client.exceptions.NoSuchBucket:
            logger.debug(f"S3 bucket does not exist yet: {self.bucket_name}")
            return []
        except Exception as e:
            logger.error(f"Failed to list S3 objects with prefix {prefix}: {e}")
            return []

    def file_exists(self, s3_key: str) -> bool:
        """Check if file exists in S3"""
        if not self.s3_client:
            return False

        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return True
        except:
            return False

    def upload_root_tfvars(self, terraform_dir: Path) -> bool:
        """
        Upload root terraform.tfvars to S3

        Args:
            terraform_dir: Terraform directory path

        Returns:
            True if successful
        """
        tfvars_path = terraform_dir / "terraform.tfvars"
        if not tfvars_path.exists():
            logger.warning("Root terraform.tfvars does not exist")
            return False

        return self.upload_file(tfvars_path, "config/terraform.tfvars")

    def upload_instance_tfvars(self, instance_dir: Path, instance_name: str) -> bool:
        """
        Upload instance terraform.tfvars to S3

        Args:
            instance_dir: Instance directory path
            instance_name: Instance name (for S3 key)

        Returns:
            True if successful
        """
        tfvars_path = instance_dir / "terraform.tfvars"
        if not tfvars_path.exists():
            logger.debug(f"Instance tfvars does not exist: {tfvars_path}")
            return False

        s3_key = f"config/instances/{instance_name}/terraform.tfvars"
        return self.upload_file(tfvars_path, s3_key)

    def download_root_tfvars(self, terraform_dir: Path) -> bool:
        """
        Download root terraform.tfvars from S3

        Args:
            terraform_dir: Terraform directory path

        Returns:
            True if successful
        """
        tfvars_path = terraform_dir / "terraform.tfvars"
        return self.download_file("config/terraform.tfvars", tfvars_path)

    def download_instance_tfvars(self, instance_dir: Path, instance_name: str) -> bool:
        """
        Download instance terraform.tfvars from S3

        Args:
            instance_dir: Instance directory path
            instance_name: Instance name

        Returns:
            True if successful
        """
        tfvars_path = instance_dir / "terraform.tfvars"
        s3_key = f"config/instances/{instance_name}/terraform.tfvars"
        return self.download_file(s3_key, tfvars_path)

    def sync_all_instances_from_s3(self, instances_dir: Path) -> Dict[str, bool]:
        """
        Download all instance tfvars from S3

        Args:
            instances_dir: Instances directory path

        Returns:
            Dictionary mapping instance_name -> success status
        """
        results = {}

        # List all instance tfvars in S3
        s3_keys = self.list_files("config/instances/")

        for s3_key in s3_keys:
            if not s3_key.endswith("/terraform.tfvars"):
                continue

            # Extract instance name from key: "config/instances/{name}/terraform.tfvars"
            parts = s3_key.split('/')
            if len(parts) != 4:
                continue

            instance_name = parts[2]
            instance_dir = instances_dir / instance_name

            if not instance_dir.exists():
                logger.warning(f"Instance directory does not exist: {instance_dir}")
                results[instance_name] = False
                continue

            success = self.download_instance_tfvars(instance_dir, instance_name)
            results[instance_name] = success

        return results

    def sync_all_instances_to_s3(self, instances_dir: Path) -> Dict[str, bool]:
        """
        Upload all instance tfvars to S3

        Args:
            instances_dir: Instances directory path

        Returns:
            Dictionary mapping instance_name -> success status
        """
        results = {}

        if not instances_dir.exists():
            logger.warning(f"Instances directory does not exist: {instances_dir}")
            return results

        for instance_dir in instances_dir.iterdir():
            if not instance_dir.is_dir():
                continue

            instance_name = instance_dir.name
            success = self.upload_instance_tfvars(instance_dir, instance_name)
            results[instance_name] = success

        return results
