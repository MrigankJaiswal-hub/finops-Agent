# backend/routers/history_routes.py
from typing import Optional
from fastapi import APIRouter, Body, Header, Query
from pydantic import BaseModel, Field

from utils.db_dynamo import put_history, query_recent

router = APIRouter(prefix="/api/history", tags=["history"])
router_compat = APIRouter(tags=["history-compat"])  # for /history without prefix

class HistoryEventIn(BaseModel):
    kind: Optional[str] = Field(default="event")
    message: str
    key: Optional[str] = None
    user: Optional[str] = None

def _user(x_user_email: Optional[str], explicit: Optional[str]) -> str:
    return explicit or x_user_email or "anonymous@demo.local"

@router.get("")
def history_list(_ts: Optional[int] = Query(default=None), limit: int = 50):
    items = query_recent(limit=limit)
    # Return a simple shape compatible with your UI’s normalizeHistoryList
    keys = []
    for it in items:
        if it.get("Type") == "HistoryEvent" and it.get("key"):
            keys.append(it["key"])
    return {"items": keys}

@router.get("/recent")
def history_recent(limit: int = 50, _ts: Optional[int] = Query(default=None)):
    items = query_recent(limit=limit)
    out = []
    for it in items:
        if it.get("Type") != "HistoryEvent":
            continue
        out.append({
            "id": it.get("PK", ""),
            "time": it.get("SK"),
            "kind": it.get("kind"),
            "message": it.get("message"),
            "key": it.get("key"),
        })
    return {"items": out}

@router.post("/add")
def history_add(
    event: HistoryEventIn = Body(...),
    x_user_email: Optional[str] = Header(default=None),
):
    u = _user(x_user_email, event.user)
    res = put_history(user=u, kind=event.kind or "event", message=event.message, key=event.key)
    return {"ok": True, "id": res["id"]}

# ----- legacy mounts -----
@router_compat.get("/history")
def history_list_compat(_ts: Optional[int] = Query(default=None), limit: int = 50):
    return history_list(_ts=_ts, limit=limit)

@router_compat.get("/history/recent")
def history_recent_compat(limit: int = 50, _ts: Optional[int] = Query(default=None)):
    return history_recent(limit=limit, _ts=_ts)

@router_compat.post("/history/add")
def history_add_compat(
    event: HistoryEventIn = Body(...),
    x_user_email: Optional[str] = Header(default=None),
):
    return history_add(event=event, x_user_email=x_user_email)
