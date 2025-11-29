"""AWS service helpers for S3, CloudFront, and SQS."""

import json
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from shared.errors import CDNInvalidationError, ConfigurationError, S3Error
from shared.logger import StructuredLogger


class S3Helper:
    """S3 operations."""

    def __init__(self, region_name: str = "us-east-1"):
        self.client = boto3.client("s3", region_name=region_name)

    def file_exists(self, bucket: str, key: str) -> bool:
        """Check if S3 object exists."""
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise S3Error(f"Error checking S3 object {bucket}/{key}: {str(e)}") from e

    def download_file(self, bucket: str, key: str, file_path: str) -> None:
        """Download file from S3."""
        try:
            StructuredLogger.info("Downloading S3 file", bucket=bucket, key=key, local_path=file_path)
            self.client.download_file(bucket, key, file_path)
        except ClientError as e:
            raise S3Error(f"Error downloading {bucket}/{key}: {str(e)}") from e

    def upload_file(
        self,
        bucket: str,
        key: str,
        file_path: str,
        content_type: str = "application/octet-stream",
        public: bool = False,
    ) -> None:
        """Upload file to S3."""
        try:
            extra_args = {"ContentType": content_type}
            if public:
                extra_args["ACL"] = "public-read"

            StructuredLogger.info("Uploading to S3", bucket=bucket, key=key, public=public)
            self.client.upload_file(file_path, bucket, key, ExtraArgs=extra_args)
        except ClientError as e:
            raise S3Error(f"Error uploading to {bucket}/{key}: {str(e)}") from e

    def put_object(
        self,
        bucket: str,
        key: str,
        body: str,
        content_type: str = "text/plain",
        public: bool = False,
    ) -> None:
        """Put object directly to S3."""
        try:
            extra_args = {"ContentType": content_type}
            if public:
                extra_args["ACL"] = "public-read"

            StructuredLogger.info("Putting object to S3", bucket=bucket, key=key, public=public)
            self.client.put_object(Bucket=bucket, Key=key, Body=body, **extra_args)
        except ClientError as e:
            raise S3Error(f"Error putting object to {bucket}/{key}: {str(e)}") from e

    def get_object(self, bucket: str, key: str) -> str:
        """Get object content from S3."""
        try:
            response = self.client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read().decode("utf-8")
        except ClientError as e:
            raise S3Error(f"Error getting object {bucket}/{key}: {str(e)}") from e

    def list_objects(self, bucket: str, prefix: str) -> List[str]:
        """List objects with prefix paginator."""
        try:
            keys = []
            paginator = self.client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        keys.append(obj["Key"])

            return keys
        except ClientError as e:
            raise S3Error(f"Error listing objects in {bucket}/{prefix}: {str(e)}") from e


class CloudFrontHelper:
    """CloudFront operations."""

    def __init__(self, region_name: str = "us-east-1"):
        self.client = boto3.client("cloudfront", region_name=region_name)

    def invalidate_paths(self, distribution_id: str, paths: List[str]) -> str:
        """Invalidate CloudFront cache for given paths."""
        try:
            if not paths:
                StructuredLogger.warning("No paths provided for CloudFront invalidation")
                return None

            StructuredLogger.info(
                "Creating CloudFront invalidation",
                distribution_id=distribution_id,
                paths_count=len(paths),
            )

            response = self.client.create_invalidation(
                DistributionId=distribution_id,
                InvalidationBatch={
                    "Paths": {"Quantity": len(paths), "Items": paths},
                    "CallerReference": str(__import__("time").time()),
                },
            )

            invalidation_id = response["Invalidation"]["Id"]
            StructuredLogger.info(
                "CloudFront invalidation created", invalidation_id=invalidation_id, distribution_id=distribution_id
            )
            return invalidation_id
        except ClientError as e:
            raise CDNInvalidationError(f"Error invalidating CloudFront: {str(e)}") from e


class SQSHelper:
    """SQS operations."""

    def __init__(self, region_name: str = "us-east-1"):
        self.client = boto3.client("sqs", region_name=region_name)

    def send_message(self, queue_url: str, message_body: Dict) -> str:
        """Send message to SQS queue."""
        try:
            if not queue_url:
                raise ConfigurationError("SQS queue URL not provided")

            StructuredLogger.info("Sending SQS message", queue_url=queue_url)

            response = self.client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message_body))

            message_id = response["MessageId"]
            StructuredLogger.info("SQS message sent", message_id=message_id, queue_url=queue_url)
            return message_id
        except ClientError as e:
            raise S3Error(f"Error sending SQS message: {str(e)}") from e

    def delete_message(self, queue_url: str, receipt_handle: str) -> None:
        """Delete message from SQS queue."""
        try:
            self.client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
            StructuredLogger.info("SQS message deleted", queue_url=queue_url)
        except ClientError as e:
            raise S3Error(f"Error deleting SQS message: {str(e)}") from e
