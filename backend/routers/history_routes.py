# routers/history_routes.py
from typing import Optional, Union, Any, Dict
from fastapi import APIRouter, Depends, Header, Body, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db
from models import HistoryEvent

# Canonical: /api/history/...
router = APIRouter(prefix="/api/history", tags=["history"])
# Legacy/compat: /history/...
router_compat = APIRouter(tags=["history-compat"])


# ---- Models ----
class HistoryIn(BaseModel):
    kind: Optional[str] = None          # 'insights_generated' | 'snapshot_loaded' | 'action_executed' | ...
    message: Optional[str] = None       # free text
    key: Optional[str] = None           # upload/history key
    user: Optional[str] = None          # optional override

    # Tolerate alternative field names coming from UI
    type: Optional[str] = None          # alias for kind
    title: Optional[str] = None         # fallback for message
    ts: Optional[int] = None            # ignored for now (db sets created_at)


class HistoryEnvelope(BaseModel):
    event: HistoryIn


# ---- Helpers ----
def _coerce_event(payload: Union[HistoryIn, HistoryEnvelope, Dict[str, Any]]) -> HistoryIn:
    """
    Accept:
      - bare HistoryIn
      - { "event": HistoryIn }
      - dict (from axios) possibly with alternate keys (type/title)
    """
    if isinstance(payload, HistoryEnvelope):
        return payload.event

    if isinstance(payload, HistoryIn):
        return payload

    # dict case
    if isinstance(payload, dict):
        if "event" in payload and isinstance(payload["event"], dict):
            d = payload["event"]
        else:
            d = payload

        # map tolerant keys -> HistoryIn
        return HistoryIn(
            kind=d.get("kind") or d.get("type") or "event",
            message=d.get("message") or d.get("title"),
            key=d.get("key"),
            user=d.get("user") or d.get("user_email"),
            ts=d.get("ts"),
        )

    # Fallback to empty HistoryIn (should not happen)
    return HistoryIn(kind="event", message=None, key=None, user=None)


def _add_history_core(evt: HistoryIn, db: Session, x_user_email: Optional[str]):
    user = evt.user or x_user_email or "anonymous@demo.local"

    # Final field coercion / defaults
    kind = (evt.kind or evt.type or "event").strip()
    message = (evt.message or evt.title or "").strip() or "(no message)"
    key = evt.key

    row = HistoryEvent(user=user, kind=kind, message=message, key=key)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


def _recent(db: Session, limit: int):
    rows = (
        db.query(HistoryEvent)
        .order_by(HistoryEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "ts": int(r.created_at.timestamp()),
                "kind": r.kind,
                "title": r.message,        # for UI that shows title
                "message": r.message,
                "key": r.key,
                "user_email": r.user,
            }
            for r in rows
        ]
    }


# ---- Canonical routes (/api/history/...) ----
@router.post("/add")
def add_history(
    payload: Union[HistoryIn, HistoryEnvelope, Dict[str, Any]] = Body(...),
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None),
):
    evt = _coerce_event(payload)
    return _add_history_core(evt, db, x_user_email)


@router.get("/recent")
def recent(db: Session = Depends(get_db), limit: int = Query(10, ge=1, le=200)):
    return _recent(db, limit)


# ---- Legacy compat (/history/...) ----
@router_compat.post("/history/add")
def add_history_compat(
    payload: Union[HistoryIn, HistoryEnvelope, Dict[str, Any]] = Body(...),
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None),
):
    evt = _coerce_event(payload)
    return _add_history_core(evt, db, x_user_email)


@router_compat.get("/history/recent")
def recent_compat(db: Session = Depends(get_db), limit: int = Query(10, ge=1, le=200)):
    return _recent(db, limit)
