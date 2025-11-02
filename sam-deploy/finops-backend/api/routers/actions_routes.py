# backend/routers/actions_routes.py
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, Header, Body, HTTPException
from pydantic import BaseModel, Field
import os

from utils.db_dynamo import put_action, put_history, query_recent

# Canonical
router = APIRouter(prefix="/api/actions", tags=["actions"])
# Legacy (no prefix)
router_compat = APIRouter(tags=["actions-compat"])

class ActionPayload(BaseModel):
    title: str = Field(..., description="Action title")
    targets: Optional[List[str]] = None
    estImpact: Optional[float] = None
    est_impact_usd: Optional[float] = None
    source: str = "finops-agent"
    user: Optional[str] = None
    # tolerated extras
    confidence: Optional[float] = None
    risk: Optional[str] = None
    current_cost: Optional[float] = None
    projected_cost: Optional[float] = None

class ExecuteEnvelope(BaseModel):
    action: ActionPayload

def _unwrap(payload: Union[ExecuteEnvelope, ActionPayload]) -> ActionPayload:
    return payload.action if isinstance(payload, ExecuteEnvelope) else payload

def _user_from_header(x_user_email: Optional[str], explicit: Optional[str]) -> str:
    return explicit or x_user_email or "anonymous@demo.local"

def _persist_action_and_history(action: ActionPayload, x_user_email: Optional[str]):
    user = _user_from_header(x_user_email, action.user)
    est = action.est_impact_usd if action.est_impact_usd is not None else action.estImpact

    # Write action
    res = put_action(
        user=user,
        title=action.title,
        targets=action.targets or [],
        est_impact=est,
        source=action.source or "finops-agent",
    )

    # Best-effort history
    try:
        msg = f"Executed: {action.title}"
        if action.targets:
            msg += f" → {', '.join(action.targets)}"
        put_history(user=user, kind="action_executed", message=msg, key=None)
    except Exception:
        pass

    return {
        "ok": True,
        "executed": True,
        "stored": True,
        "preview": False,
        "actionId": res["id"],
        "superops_result": None,
    }

@router.post("/execute")
def execute_action(
    payload: Union[ExecuteEnvelope, ActionPayload] = Body(...),
    x_user_email: Optional[str] = Header(default=None),
):
    action = _unwrap(payload)
    return _persist_action_and_history(action, x_user_email)

@router.get("")
def list_actions(limit: int = 50):
    items = query_recent(limit=limit)
    out = []
    for it in items:
        if it.get("Type") != "ActionLog":
            continue
        out.append({
            "id": it.get("PK", "").replace("ACTION#", ""),
            "ts": it.get("SK"),
            "user_email": it.get("user"),
            "source": it.get("source"),
            "action": {
                "title": it.get("title"),
                "targets": it.get("targets") or [],
                "est_impact_usd": it.get("est_impact"),
            },
        })
    return {"items": out}

# ---- legacy compatibility ----
@router_compat.post("/actions/execute")
def execute_action_compat(
    payload: Union[ExecuteEnvelope, ActionPayload] = Body(...),
    x_user_email: Optional[str] = Header(default=None),
):
    action = _unwrap(payload)
    return _persist_action_and_history(action, x_user_email)

@router_compat.get("/actions")
def list_actions_compat(limit: int = 50):
    return list_actions(limit=limit)
