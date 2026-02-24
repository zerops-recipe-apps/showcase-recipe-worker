import boto3
from botocore.config import Config as BotoConfig
from config import config
import structlog

log = structlog.get_logger()


class S3Storage:
    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=config.S3_ENDPOINT,
            aws_access_key_id=config.S3_ACCESS_KEY,
            aws_secret_access_key=config.S3_SECRET_KEY,
            region_name="us-east-1",
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )
        self.bucket = config.S3_BUCKET

    async def download(self, key: str) -> bytes:
        """Download a file from Object Storage."""
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        data = response["Body"].read()
        log.info("s3.download", key=key, size=len(data))
        return data

    async def upload(self, key: str, data: bytes, content_type: str):
        """Upload a file to Object Storage."""
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        log.info("s3.upload", key=key, size=len(data), content_type=content_type)
