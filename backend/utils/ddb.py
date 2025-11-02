# backend/utils/ddb.py
import os
import boto3
import logging
from decimal import Decimal

logger = logging.getLogger("finops-ddb")

def _to_decimal(obj):
    """
    Recursively convert floats to Decimal (DynamoDB does not accept float).
    Also ensures lists/dicts are traversed.
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_decimal(x) for x in obj]
    return obj

def _make_ddb_resource():
    # Priority: DDB_REGION > AWS_REGION > AWS_DEFAULT_REGION > us-east-1
    region = (
        os.getenv("DDB_REGION")
        or os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
        or "us-east-1"
    )
    profile = os.getenv("AWS_PROFILE")  # optional

    # Use a session if a profile is specified (SSO-friendly).
    if profile:
        logger.info("[ddb] using profile=%s region=%s", profile, region)
        session = boto3.Session(profile_name=profile, region_name=region)
        return session.resource("dynamodb", region_name=region)
    else:
        logger.info("[ddb] using default creds region=%s", region)
        return boto3.resource("dynamodb", region_name=region)

def put_action_item(table_name: str, item: dict) -> str | None:
    """
    Put an action event into DynamoDB. Returns the item id on success, else None.
    """
    try:
        ddb = _make_ddb_resource()
        table = ddb.Table(table_name)
        safe_item = _to_decimal(item)
        table.put_item(Item=safe_item)
        return str(item.get("id"))
    except Exception as e:
        logger.error("DDB put_item failed: %s", e, exc_info=True)
        return None
