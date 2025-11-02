# routers/actions_routes.py
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, Header, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db
from models import ActionLog, HistoryEvent

# ---------------- Canonical router (/api/actions/...) ----------------
router = APIRouter(prefix="/api/actions", tags=["actions"])

# ---------------- Legacy router (no prefix: /actions, /actions/execute) ----
# This lets older frontend code keep working.
router_compat = APIRouter(tags=["actions-compat"])


# ---------------- Models ----------------
class ActionPayload(BaseModel):
    title: str = Field(..., description="Action title")
    targets: Optional[List[str]] = None
    # be lenient with naming from UI
    estImpact: Optional[float] = None
    est_impact_usd: Optional[float] = None
    source: str = "finops-agent"
    user: Optional[str] = None  # optional explicit user override

    # extra fields tolerated from LLM JSON, not stored
    confidence: Optional[float] = None
    risk: Optional[str] = None
    current_cost: Optional[float] = None
    projected_cost: Optional[float] = None


class ExecuteEnvelope(BaseModel):
    action: ActionPayload


def _unwrap_envelope(payload: Union[ExecuteEnvelope, ActionPayload]) -> ActionPayload:
    return payload.action if isinstance(payload, ExecuteEnvelope) else payload


def _persist_action_and_history(
    action: ActionPayload, db: Session, x_user_email: Optional[str]
):
    user = action.user or x_user_email or "anonymous@demo.local"
    est = action.est_impact_usd if action.est_impact_usd is not None else action.estImpact

    arow = ActionLog(
        user=user,
        title=action.title,
        targets=", ".join(action.targets or []),
        est_impact=est,
        source=action.source or "finops-agent",
    )
    db.add(arow)
    db.commit()
    db.refresh(arow)

    # Best-effort history entry
    try:
        msg = f"Executed: {action.title}"
        if action.targets:
            msg += f" → {', '.join(action.targets)}"
        h = HistoryEvent(user=user, kind="action_executed", message=msg, key=None)
        db.add(h)
        db.commit()
    except Exception:
        db.rollback()  # don't break the main request

    return {
        "ok": True,
        "executed": True,
        "stored": True,
        "preview": False,
        "actionId": arow.id,
        "superops_result": None,
    }


# ---------------- Endpoints: canonical ----------------
@router.post("/execute")
def execute_action(
    payload: Union[ExecuteEnvelope, ActionPayload] = Body(...),
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None),
):
    action = _unwrap_envelope(payload)
    return _persist_action_and_history(action, db, x_user_email)


@router.get("")
def list_actions(db: Session = Depends(get_db), limit: int = 50):
    q = db.query(ActionLog).order_by(ActionLog.time.desc()).limit(limit).all()
    items = []
    for r in q:
        items.append(
            {
                "id": r.id,
                "ts": int(r.time.timestamp()),
                "user_email": r.user,
                "source": r.source,
                "action": {
                    "title": r.title,
                    "targets": [t.strip() for t in (r.targets or "").split(",") if t.strip()],
                    "est_impact_usd": r.est_impact,
                },
            }
        )
    return {"items": items}


# ---------------- Endpoints: legacy (no /api prefix) ----------------
@router_compat.post("/actions/execute")
def execute_action_compat(
    payload: Union[ExecuteEnvelope, ActionPayload] = Body(...),
    db: Session = Depends(get_db),
    x_user_email: Optional[str] = Header(default=None),
):
    action = _unwrap_envelope(payload)
    return _persist_action_and_history(action, db, x_user_email)


@router_compat.get("/actions")
def list_actions_compat(db: Session = Depends(get_db), limit: int = 50):
    return list_actions(db=db, limit=limit)
