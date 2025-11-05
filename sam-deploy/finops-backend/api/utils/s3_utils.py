# backend/utils/s3_utils.py
import os
import logging
from typing import Optional, List, Dict, Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger("finops-s3")

def _is_lambda() -> bool:
    # True inside AWS Lambda
    return bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

def _region() -> str:
    # Prefer Lambda's injected AWS_REGION, then env, then default
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"

def _s3_client():
    # IMPORTANT: Do NOT pass creds or profile. Let the default chain (incl. Lambda env) work.
    return boto3.client(
        "s3",
        region_name=_region(),
        config=Config(retries={"max_attempts": 3, "mode": "standard"})
    )

def use_s3() -> bool:
    """
    Return True if S3 usage is intended.
    We require at least S3_BUCKET to be set (S3_KEY optional).
    """
    return bool(os.environ.get("S3_BUCKET"))

def read_s3_file(bucket: str, key: str = "billing_data.csv") -> Optional[str]:
    """
    Read an object from S3 and return its content as UTF-8 text.
    Returns None on any error.
    """
    if not bucket:
        logger.error("S3 bucket not provided.")
        return None
    try:
        s3 = _s3_client()
        obj = s3.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read().decode("utf-8")
    except ClientError as e:
        logger.error("Error reading S3 object %s/%s: %s", bucket, key, e, exc_info=True)
        return None
    except Exception as e:
        logger.error("Unexpected error reading S3 object %s/%s: %s", bucket, key, e, exc_info=True)
        return None

def put_s3_object(
    bucket: str,
    key: str,
    content_bytes: bytes,
    content_type: str = "application/octet-stream",
) -> bool:
    """
    Write bytes to S3. Returns True on success.
    """
    try:
        s3 = _s3_client()
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=content_bytes,
            ContentType=content_type,
        )
        logger.info("Wrote S3 object %s/%s (%d bytes)", bucket, key, len(content_bytes))
        return True
    except Exception as e:
        logger.error("Error writing S3 object %s/%s: %s", bucket, key, e, exc_info=True)
        return False

def list_s3_objects(bucket: str, prefix: str, max_keys: int = 100) -> List[Dict[str, Any]]:
    """
    List objects under prefix. Returns a simplified list of dicts:
    [{ key, size, last_modified }, ...]
    """
    try:
        s3 = _s3_client()
        paginator = s3.get_paginator("list_objects_v2")
        items: List[Dict[str, Any]] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix, MaxKeys=max_keys):
            for obj in page.get("Contents", []):
                items.append({
                    "key": obj.get("Key"),
                    "size": obj.get("Size"),
                    "last_modified": obj.get("LastModified").isoformat() if obj.get("LastModified") else None,
                })
        return items
    except Exception as e:
        logger.error("Error listing S3 prefix %s/%s: %s", bucket, prefix, e, exc_info=True)
        return []

def delete_s3_object(bucket: str, key: str) -> bool:
    """
    Delete a single object. Returns True on success.
    """
    try:
        s3 = _s3_client()
        s3.delete_object(Bucket=bucket, Key=key)
        logger.info("Deleted S3 object %s/%s", bucket, key)
        return True
    except Exception as e:
        logger.error("Error deleting S3 object %s/%s: %s", bucket, key, e, exc_info=True)
        return False

def generate_presigned_get_url(bucket: str, key: str, expires_in: int = 900) -> Optional[str]:
    """
    Generate a presigned GET URL for an object.
    Returns the URL string or None on failure.
    """
    try:
        s3 = _s3_client()
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=int(expires_in),
        )
        return url
    except Exception as e:
        logger.error("Error generating presigned URL for %s/%s: %s", bucket, key, e, exc_info=True)
        return None

# --- Wrapper used by FastAPI route (/history/presign) ---
def get_presigned_url(bucket: str, key: str, expires: int = 300) -> str:
    url = generate_presigned_get_url(bucket, key, expires_in=expires)
    if not url:
        raise RuntimeError(f"Failed to generate presigned URL for {bucket}/{key}")
    return url
