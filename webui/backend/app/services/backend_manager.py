"""
Backend Infrastructure Manager
Handles automatic setup of S3 backend and DynamoDB for Terraform state management
"""
import boto3
import logging
from typing import Optional, Dict
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class BackendManager:
    def __init__(self, region: str = "ap-northeast-2"):
        self.region = region
        self.s3_client = boto3.client('s3', region_name=region)
        self.dynamodb_client = boto3.client('dynamodb', region_name=region)

    def check_backend_exists(self, bucket_name: str, table_name: str) -> Dict[str, bool]:
        """Check if S3 bucket and DynamoDB table exist"""
        return {
            "bucket_exists": self._bucket_exists(bucket_name),
            "table_exists": self._table_exists(table_name)
        }

    def setup_backend_infrastructure(
        self,
        bucket_name: str,
        table_name: str = "terraform-state-locks"
    ) -> Dict[str, any]:
        """
        Create S3 bucket and DynamoDB table for Terraform backend

        Returns:
            dict: Status and configuration details
        """
        result = {
            "success": False,
            "bucket": {"created": False, "name": bucket_name},
            "dynamodb": {"created": False, "name": table_name},
            "errors": []
        }

        # Create S3 bucket
        try:
            bucket_created = self._create_state_bucket(bucket_name)
            result["bucket"]["created"] = bucket_created
            result["bucket"]["exists"] = True
        except Exception as e:
            logger.error(f"Failed to create S3 bucket: {e}")
            result["errors"].append(f"S3 bucket error: {str(e)}")
            return result

        # Create DynamoDB table
        try:
            table_created = self._create_lock_table(table_name)
            result["dynamodb"]["created"] = table_created
            result["dynamodb"]["exists"] = True
        except Exception as e:
            logger.error(f"Failed to create DynamoDB table: {e}")
            result["errors"].append(f"DynamoDB error: {str(e)}")
            return result

        result["success"] = True
        result["config"] = {
            "bucket": bucket_name,
            "region": self.region,
            "dynamodb_table": table_name,
            "encrypt": True
        }

        return result

    def _bucket_exists(self, bucket_name: str) -> bool:
        """Check if S3 bucket exists"""
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            return True
        except ClientError:
            return False

    def _table_exists(self, table_name: str) -> bool:
        """Check if DynamoDB table exists"""
        try:
            self.dynamodb_client.describe_table(TableName=table_name)
            return True
        except ClientError:
            return False

    def _create_state_bucket(self, bucket_name: str) -> bool:
        """Create S3 bucket with proper configuration for Terraform state"""
        # Check if already exists
        if self._bucket_exists(bucket_name):
            logger.info(f"S3 bucket {bucket_name} already exists")
            return False

        # Create bucket
        try:
            if self.region == 'us-east-1':
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )
            logger.info(f"Created S3 bucket: {bucket_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
                logger.info(f"Bucket {bucket_name} already owned by you")
                return False
            raise

        # Enable versioning
        self.s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )

        # Enable encryption
        self.s3_client.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                'Rules': [{
                    'ApplyServerSideEncryptionByDefault': {
                        'SSEAlgorithm': 'AES256'
                    }
                }]
            }
        )

        # Block public access
        self.s3_client.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': True,
                'IgnorePublicAcls': True,
                'BlockPublicPolicy': True,
                'RestrictPublicBuckets': True
            }
        )

        # Add lifecycle rule
        self.s3_client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration={
                'Rules': [
                    {
                        'ID': 'delete-old-versions',
                        'Status': 'Enabled',
                        'NoncurrentVersionExpiration': {'NoncurrentDays': 90}
                    },
                    {
                        'ID': 'abort-incomplete-uploads',
                        'Status': 'Enabled',
                        'AbortIncompleteMultipartUpload': {'DaysAfterInitiation': 7}
                    }
                ]
            }
        )

        # Add tags
        self.s3_client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={
                'TagSet': [
                    {'Key': 'Name', 'Value': 'Terraform State Bucket'},
                    {'Key': 'Purpose', 'Value': 'Remote state storage'},
                    {'Key': 'ManagedBy', 'Value': 'WebUI'}
                ]
            }
        )

        logger.info(f"Configured S3 bucket {bucket_name} for Terraform state")
        return True

    def _create_lock_table(self, table_name: str) -> bool:
        """Create DynamoDB table for state locking"""
        # Check if already exists
        if self._table_exists(table_name):
            logger.info(f"DynamoDB table {table_name} already exists")
            return False

        # Create table
        self.dynamodb_client.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'LockID', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'LockID', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST',
            Tags=[
                {'Key': 'Name', 'Value': 'Terraform State Locks'},
                {'Key': 'Purpose', 'Value': 'State locking'},
                {'Key': 'ManagedBy', 'Value': 'WebUI'}
            ]
        )

        # Wait for table to be active
        waiter = self.dynamodb_client.get_waiter('table_exists')
        waiter.wait(TableName=table_name)

        logger.info(f"Created DynamoDB table: {table_name}")
        return True

    def generate_backend_config(
        self,
        bucket_name: str,
        instance_name: str,
        table_name: str = "terraform-state-locks"
    ) -> str:
        """Generate backend.tf content for an instance"""
        return f'''# S3 Backend Configuration
# Auto-generated by WebUI
# Each instance has a unique S3 key for independent locking

terraform {{
  backend "s3" {{
    bucket         = "{bucket_name}"
    key            = "instances/{instance_name}/terraform.tfstate"
    region         = "{self.region}"
    dynamodb_table = "{table_name}"
    encrypt        = true
  }}
}}
'''

    def get_backend_status(self, bucket_name: str, table_name: str) -> Dict[str, any]:
        """Get detailed status of backend infrastructure"""
        status = {
            "configured": False,
            "bucket": {"exists": False, "versioning": None, "encryption": None},
            "dynamodb": {"exists": False, "billing_mode": None},
            "region": self.region
        }

        # Check S3 bucket
        if self._bucket_exists(bucket_name):
            status["bucket"]["exists"] = True
            try:
                # Check versioning
                versioning = self.s3_client.get_bucket_versioning(Bucket=bucket_name)
                status["bucket"]["versioning"] = versioning.get('Status', 'Disabled')

                # Check encryption
                encryption = self.s3_client.get_bucket_encryption(Bucket=bucket_name)
                status["bucket"]["encryption"] = "Enabled"
            except ClientError:
                pass

        # Check DynamoDB table
        if self._table_exists(table_name):
            status["dynamodb"]["exists"] = True
            try:
                table_info = self.dynamodb_client.describe_table(TableName=table_name)
                status["dynamodb"]["billing_mode"] = table_info['Table']['BillingModeSummary']['BillingMode']
            except ClientError:
                pass

        status["configured"] = (
            status["bucket"]["exists"] and
            status["dynamodb"]["exists"]
        )

        return status
