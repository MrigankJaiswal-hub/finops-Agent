# api/routers/history_routes.py
from typing import Optional
from fastapi import APIRouter, Depends, Body, Header
from sqlalchemy.orm import Session

from db import get_db, engine
from models import Base, HistoryEvent

router = APIRouter(prefix="/api/history", tags=["history"])
router_compat = APIRouter(tags=["history-compat"])

_tables_ready = False
def _ensure_tables():
    global _tables_ready
    if _tables_ready:
        return
    try:
        Base.metadata.create_all(bind=engine)
        _tables_ready = True
    except Exception:
        pass

@router.post("/add")
def add_history(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None),
):
    _ensure_tables()
    user = x_user_email or "anonymous@demo.local"
    msg = payload.get("message") or payload.get("text") or "event"
    kind = payload.get("kind") or "event"
    key  = payload.get("key")
    ev = HistoryEvent(user=user, kind=kind, message=msg, key=key)
    db.add(ev)
    db.commit()
    return {"ok": True, "id": ev.id}

@router.get("")
def list_history(db: Session = Depends(get_db)):
    _ensure_tables()
    rows = db.query(HistoryEvent).order_by(HistoryEvent.time.desc()).limit(200).all()
    return {"items": [
        {"id": r.id, "time": r.time.isoformat() if r.time else None,
         "user": r.user, "kind": r.kind, "message": r.message, "key": r.key}
        for r in rows
    ]}

# legacy routes
@router_compat.post("/history/add")
def add_history_compat(payload: dict = Body(...), db: Session = Depends(get_db), x_user_email: Optional[str] = Header(default=None)):
    return add_history(payload=payload, db=db, x_user_email=x_user_email)

@router_compat.get("/history")
def list_history_compat(db: Session = Depends(get_db)):
    return list_history(db=db)
