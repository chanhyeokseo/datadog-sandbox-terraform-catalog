import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class S3ConfigManager:

    def __init__(self, bucket_name: str, region: str = None):
        self.bucket_name = bucket_name
        self.region = region or 'ap-northeast-2'
        self._s3_client = None

    @property
    def s3_client(self):
        if self._s3_client is None:
            try:
                import boto3
                self._s3_client = boto3.client('s3', region_name=self.region)
            except Exception as e:
                logger.warning(f"Failed to create S3 client: {e}")
                return None
        return self._s3_client

    def upload_file(self, local_path: Path, s3_key: str) -> bool:
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
            logger.info(f"Uploaded {local_path.name} to s3://{self.bucket_name}/{s3_key}")
            return True
        except self.s3_client.exceptions.NoSuchBucket:
            logger.debug(f"S3 bucket does not exist yet: {self.bucket_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to upload {local_path} to S3: {e}")
            return False

    def download_file(self, s3_key: str, local_path: Path) -> bool:
        if not self.s3_client:
            logger.warning("S3 client not available")
            return False
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            with open(local_path, 'wb') as f:
                f.write(response['Body'].read())
            logger.info(f"Downloaded s3://{self.bucket_name}/{s3_key} to {local_path}")
            return True
        except self.s3_client.exceptions.NoSuchKey:
            logger.debug(f"S3 key not found: {s3_key}")
            return False
        except Exception as e:
            logger.error(f"Failed to download {s3_key} from S3: {e}")
            return False

    def list_files(self, prefix: str) -> List[str]:
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

    def upload_text(self, s3_key: str, text: str) -> bool:
        if not self.s3_client:
            logger.warning("S3 client not available")
            return False
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=text.encode("utf-8")
            )
            logger.info(f"Uploaded text to s3://{self.bucket_name}/{s3_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload text to {s3_key}: {e}")
            return False

    def download_text(self, s3_key: str) -> str:
        if not self.s3_client:
            return ""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return response["Body"].read().decode("utf-8")
        except Exception as e:
            logger.debug(f"Failed to download text from {s3_key}: {e}")
            return ""

    def file_exists(self, s3_key: str) -> bool:
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
