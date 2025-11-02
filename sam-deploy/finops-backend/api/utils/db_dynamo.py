# backend/utils/db_dynamo.py
import os
import json
import boto3
from datetime import datetime, timezone

_DDB_TABLE = os.environ.get("DDB_TABLE")
_DDB_REGION = os.environ.get("DDB_REGION") or os.environ.get("AWS_REGION")

_session = boto3.session.Session(region_name=_DDB_REGION)
_dynamo = _session.resource("dynamodb") if _DDB_TABLE else None
_table = _dynamo.Table(_DDB_TABLE) if _dynamo else None

def table():
    if not _table:
        raise RuntimeError("DynamoDB table not configured. Set DDB_TABLE/DDB_REGION.")
    return _table

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def put_action(user: str, title: str, targets, est_impact, source: str):
    """
    Persist an action log. Item shape:
      PK: ACTION#<uuid>
      SK: <ISO time>
      GSI1PK: USER#<email>
      GSI1SK: <ISO time>
      payload: original fields
    """
    import uuid
    t = table()
    action_id = str(uuid.uuid4())
    item = {
        "PK": f"ACTION#{action_id}",
        "SK": now_iso(),
        "Type": "ActionLog",
        "user": user,
        "title": title,
        "targets": targets or [],
        "est_impact": float(est_impact) if est_impact is not None else None,
        "source": source or "finops-agent",
        "payload": {
            "user": user,
            "title": title,
            "targets": targets or [],
            "est_impact": float(est_impact) if est_impact is not None else None,
            "source": source or "finops-agent",
        },
        "GSI1PK": f"USER#{user}",
        "GSI1SK": f"ACTION#{action_id}#{now_iso()}",
    }
    # remove None (DynamoDB can’t store None)
    item = {k: v for k, v in item.items() if v is not None}
    t.put_item(Item=item)
    return {"id": action_id, "time": item["SK"]}

def put_history(user: str, kind: str, message: str, key: str|None = None):
    import uuid
    t = table()
    event_id = str(uuid.uuid4())
    item = {
        "PK": f"HIST#{event_id}",
        "SK": now_iso(),
        "Type": "HistoryEvent",
        "user": user,
        "kind": kind or "event",
        "message": message,
        "key": key,
        "GSI1PK": f"USER#{user}",
        "GSI1SK": f"HIST#{event_id}#{now_iso()}",
    }
    item = {k: v for k, v in item.items() if v is not None}
    t.put_item(Item=item)
    return {"id": event_id, "time": item["SK"]}

def query_recent(limit: int = 50):
    """
    Simple recent scan. If you added GSIs, you can switch this to a keyed Query.
    """
    t = table()
    # Small table in hackathon setting → Scan + sort in code
    resp = t.scan(Limit=500)
    items = resp.get("Items", [])
    # Filter only our types, sort by SK desc
    items = [x for x in items if x.get("Type") in ("ActionLog", "HistoryEvent")]
    items.sort(key=lambda x: x.get("SK", ""), reverse=True)
    return items[:limit]
