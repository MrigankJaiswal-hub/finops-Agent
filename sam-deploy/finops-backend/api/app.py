# backend/app.py
import os
import io
import re
import json
import csv
import time
import math
import logging
import tempfile
from decimal import Decimal
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from fastapi import FastAPI

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Query,
    Request,
    Depends,
    Header,
    Body,
    Response
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from starlette.responses import PlainTextResponse
from starlette.responses import Response, FileResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# --- reportlab for PDF export ---
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader

# --- Utilities ---
from utils.analyze import analyze_csv_rows
from utils.s3_utils import (
    read_s3_file,
    use_s3,
    put_s3_object,
    list_s3_objects,
    delete_s3_object,
    generate_presigned_get_url,
)
from utils.bedrock_client import get_ai_json
from utils.kiros_mock import get_mock_kiros_clients
from utils.cognito_verify import verify_bearer  # strict JWKS verify

from utils.superops import run_superops_action
from utils.ddb import put_action_item
import uuid
from db import Base, engine
from routers import actions_routes, history_routes
from sqlalchemy.orm import Session
from db import get_db
from routers.history_routes import router as history_router, router_compat as history_router_compat
from routers.mockclients_routes import router as mockclients_router
from db import init_db
init_db()

# --- Load env ---
load_dotenv()

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("finops-backend")

# --- Env prints ---
PROVIDER = os.getenv("PROVIDER")
AWS_REGION_EFFECTIVE = (
    os.getenv("BEDROCK_REGION")
    or os.getenv("AWS_REGION")
    or os.getenv("AWS_DEFAULT_REGION")
)

COGNITO_ENABLED = os.getenv("COGNITO_ENABLED", "false").lower() == "true"
COGNITO_REGION = os.getenv("COGNITO_REGION")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_AUDIENCE = os.getenv("COGNITO_AUDIENCE")

# allow public POST /execute_action and public budgets for demo
ALLOW_PUBLIC_ACTIONS = os.getenv("ALLOW_PUBLIC_ACTIONS", "false").lower() == "true"

# admin controls
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
ADMIN_GROUP = os.getenv("ADMIN_GROUP", "").strip()

# budgets / multi-tenant
S3_BUDGETS_PREFIX = os.getenv("S3_BUDGETS_PREFIX", "budgets/").strip() or "budgets/"
BUDGETS_TENANTED = os.getenv("BUDGETS_TENANTED", "false").lower() == "true"
BUDGETS_TENANT_DEFAULT = os.getenv("BUDGETS_TENANT_DEFAULT", "default").strip() or "default"
PUBLIC_BUDGET_SUB = os.getenv("PUBLIC_BUDGET_SUB", "default").strip() or "default"

# alert thresholds
ALERT_WARN_PCT = float(os.getenv("ALERT_WARN_PCT", "0.9"))
ALERT_BREACH_PCT = float(os.getenv("ALERT_BREACH_PCT", "1.0"))

# PDF branding
PDF_BRAND = os.getenv("PDF_BRAND", "FinOps+ Agent")
PDF_TAGLINE = os.getenv("PDF_TAGLINE", "AI-Driven Financial Operations Insights")
PDF_WATERMARK = os.getenv("PDF_WATERMARK", "FinOps Prototype")
PDF_LOGO_PATH = os.getenv(
    "PDF_LOGO_PATH",
    os.path.join(os.path.dirname(__file__), "data", "logo.png")
)

# create tables on startup
Base.metadata.create_all(bind=engine)

print("DEBUG: Provider =", PROVIDER)
print("DEBUG: AWS Region (effective) =", AWS_REGION_EFFECTIVE)
print("DEBUG: Model ID =", os.getenv("BEDROCK_MODEL_ID"))
print("DEBUG: Access Key Present =", bool(os.getenv("AWS_ACCESS_KEY_ID")))
print("DEBUG: AWS_PROFILE =", os.getenv("AWS_PROFILE"))
print("DEBUG: COGNITO_ENABLED =", COGNITO_ENABLED)
print("DEBUG: ADMIN_EMAILS =", ADMIN_EMAILS)
print("DEBUG: ADMIN_GROUP =", ADMIN_GROUP or "(none)")
print("DEBUG: BUDGETS_TENANTED =", BUDGETS_TENANTED)
print("DEBUG: BUDGETS_TENANT_DEFAULT =", BUDGETS_TENANT_DEFAULT)
print("DEBUG: PUBLIC_BUDGET_SUB =", PUBLIC_BUDGET_SUB)
print("DEBUG: ALLOW_PUBLIC_ACTIONS =", ALLOW_PUBLIC_ACTIONS)
print("DEBUG: ALERT_WARN_PCT =", ALERT_WARN_PCT, " ALERT_BREACH_PCT =", ALERT_BREACH_PCT)



# --- FastAPI app ---
app = FastAPI(title="FinOps+ Agent - Backend (Prototype)")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "https://d2gc5d8166vwh1.cloudfront.net")

ALLOWED_ORIGINS = [
    os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
    "http://localhost:5173",
]



app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  # keep false since we use Authorization header, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["content-disposition","content-type"],
    max_age=600,
)

@app.get("/health")
def health():
    return {"status": "ok", "message": "FinOps+ backend running successfully"}

# --- Lazy mount routers so /health is safe even if a router import fails ---
def _mount_routers():
    try:
        from routers import actions_routes, history_routes
        app.include_router(actions_routes.router)        # /api/actions/...
        app.include_router(actions_routes.router_compat) # /actions/...
        app.include_router(history_routes.router)        # /api/history/...
        app.include_router(history_routes.router_compat) # /history/...
    except Exception as e:
        # Don't crash the whole app; you can inspect logs in CloudWatch
        import logging
        logging.getLogger(__name__).exception("Router import/mount failed: %s", e)

_mount_routers()

app.include_router(actions_routes.router)         # /api/actions/...
app.include_router(actions_routes.router_compat)  # /actions...
app.include_router(history_routes.router)         # /api/history/...
app.include_router(history_routes.router_compat)  # /history...
app.include_router(mockclients_router)

# --------- Ensure no accidental compression/encoding on PDFs ----------
class NoZipPDFMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = [(k.lower(), v) for k, v in message.get("headers", [])]
                headers = [(k, v) for (k, v) in headers if k != b"content-encoding"]
                message["headers"] = headers
            await send(message)
        await self.app(scope, receive, send_wrapper)

app.add_middleware(NoZipPDFMiddleware)

@app.middleware("http")
async def add_security_headers(request, call_next):
    resp: Response = await call_next(request)
    resp.headers.setdefault("Cache-Control", "no-store")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    return resp

@app.middleware("http")
async def add_cors_on_error(request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        # If your endpoint crashes, still return CORS so browsers can read the error
        response = PlainTextResponse("Internal Server Error", status_code=500)

    origin = request.headers.get("origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"

    return response

# ===========================================================
# Tiny Rate Limit
# ===========================================================
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_WINDOW_SEC = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "15"))
_rate_log: Dict[str, List[float]] = {}

async def rate_limit(request: Request):
    if not RATE_LIMIT_ENABLED:
        return
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _rate_log.setdefault(ip, [])
    cutoff = now - RATE_LIMIT_WINDOW_SEC
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Too many requests, slow down.")
    bucket.append(now)

# ===========================================================
# Cognito dependencies
# ===========================================================
async def get_current_user(authorization: str = Header(None)) -> Dict[str, Any]:
    """
    Strict Cognito validation (used for protected routes).
    """
    if not COGNITO_ENABLED:
        raise HTTPException(status_code=401, detail="Cognito is disabled on server")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.split(" ", 1)[1].strip()
    return await verify_bearer(token)

def _is_admin(user: Dict[str, Any]) -> bool:
    email = (user.get("email") or user.get("username") or "").lower()
    if email and email in ADMIN_EMAILS:
        return True
    groups = user.get("cognito:groups") or user.get("groups") or []
    if isinstance(groups, str):
        groups = [groups]
    if ADMIN_GROUP and ADMIN_GROUP in groups:
        return True
    return False

async def get_admin_user(authorization: str = Header(None)) -> Dict[str, Any]:
    user = await get_current_user(authorization)
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

async def get_user_optional(authorization: str = Header(None)) -> Dict[str, Any]:
    """
    For public-friendly routes, allow:
      - real Cognito user if Authorization is present (strict verify)
      - or a 'public-demo' identity if ALLOW_PUBLIC_ACTIONS=true
      - or {} (unauth) when neither applies
    """
    if COGNITO_ENABLED:
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
            return await verify_bearer(token)
        if ALLOW_PUBLIC_ACTIONS:
            return {"sub": "public-demo", "email": "public@demo.local"}
        return {}
    else:
        if ALLOW_PUBLIC_ACTIONS:
            return {"sub": "public-demo", "email": "public@demo.local"}
        return {}

# ===========================================================
# Models
# ===========================================================
class ClientInsight(BaseModel):
    client: str
    revenue: float
    cost: float
    margin: float
    license_waste_pct: float
    health: str

class AlertItem(BaseModel):
    client: str
    budget: float
    spend: float
    pct: float
    status: str  # "ok" | "warn" | "breach"

class AnalyzeResponse(BaseModel):
    total_revenue: float
    total_cost: float
    total_profit: float
    client_insights: List[ClientInsight]
    meta: Optional[Dict[str, Any]] = None
    alerts: Optional[List[AlertItem]] = None

class RecommendJSONAction(BaseModel):
    title: str
    reason: str
    est_impact_usd: float = 0.0
    targets: List[str] = []
    confidence: Optional[float] = None
    risk: Optional[str] = None
    current_cost: Optional[float] = None
    projected_cost: Optional[float] = None
    savings_pct: Optional[float] = None

class RecommendJSON(BaseModel):
    actions: List[RecommendJSONAction]

class RecommendResponse(BaseModel):
    ai_recommendation: str
    source: str
    parsed_json: Optional[RecommendJSON] = None

class UploadAnalyzeResponse(AnalyzeResponse):
    stored_key: Optional[str] = None

class ExecuteActionItem(BaseModel):
    title: str
    reason: Optional[str] = ""
    est_impact_usd: Optional[float] = 0.0
    targets: List[str] = []
    action_type: str = "optimize_license"
    key: Optional[str] = None

class ExecuteActionRequest(BaseModel):
    action: ExecuteActionItem

class ExecuteActionResponse(BaseModel):
    executed: bool
    id: str
    stored: str
    preview: Dict[str, Any]
    superops_result: Optional[Dict[str, Any]] = None

class BenchmarkResponse(BaseModel):
    source: str = "api"
    industry: str = "MSP"
    industry_waste_pct: float
    industry_avg_waste_pct: float
    your_waste_pct: float
    potential_savings_usd: float
    method: str = "cost-weighted license_waste_pct; recoverable_factor=0.8"
    notes: Optional[str] = None

# ===========================================================
# Helpers
# ===========================================================
def _get(obj: Any, field: str, default=None):
    if hasattr(obj, field):
        return getattr(obj, field)
    if isinstance(obj, dict):
        return obj.get(field, default)
    return default

def _float(v: Any) -> float:
    try:
        return float(v or 0)
    except Exception:
        return 0.0

def _rows_from_text(csv_text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = [r for r in reader]
    fields = [f.lower() for f in (reader.fieldnames or [])]
    return rows, fields

def _analyze_text(csv_text: str) -> Tuple[List[Dict[str, Any]], AnalyzeResponse]:
    rows, fieldnames = _rows_from_text(csv_text)
    if not rows:
        raise HTTPException(status_code=400, detail="No rows found in CSV.")
    has_revenue_cost = ("revenue" in fieldnames) and ("cost" in fieldnames)

    if has_revenue_cost:
        total_revenue = sum(_float(r.get("revenue")) for r in rows)
        total_cost = sum(_float(r.get("cost")) for r in rows)
        client_insights = analyze_csv_rows(rows)
        return rows, AnalyzeResponse(
            total_revenue=round(total_revenue, 2),
            total_cost=round(total_cost, 2),
            total_profit=round(total_revenue - total_cost, 2),
            client_insights=client_insights,
        )

    total_cost = sum(_float(r.get("Cost")) for r in rows if "Cost" in r)
    total_revenue = total_cost
    by_service: Dict[str, float] = {}
    for r in rows:
        svc = r.get("Service") or r.get("UsageType") or "Unknown"
        by_service[svc] = by_service.get(svc, 0.0) + _float(r.get("Cost"))
    client_insights2: List[ClientInsight] = []
    for svc, cst in sorted(by_service.items(), key=lambda kv: kv[1], reverse=True):
        client_insights2.append(ClientInsight(
            client=str(svc), revenue=round(cst, 2), cost=round(cst, 2),
            margin=0.0, license_waste_pct=0.0, health="Unknown"
        ))
    return rows, AnalyzeResponse(
        total_revenue=round(total_revenue, 2),
        total_cost=round(total_cost, 2),
        total_profit=0.0,
        client_insights=client_insights2,
    )

def _summarize_for_prompt(rows: List[Dict[str, Any]], client_insights: List[ClientInsight]) -> str:
    top_waste = sorted(client_insights, key=lambda c: c.license_waste_pct, reverse=True)[:3]
    low_margin = sorted(client_insights, key=lambda c: c.margin)[:3]
    lines = []
    lines.append("Top license waste (3): " + "; ".join(
        f"{c.client}({c.license_waste_pct:.1f}% waste)" for c in top_waste
    ))
    lines.append("Lowest margins (3): " + "; ".join(
        f"{c.client}(margin ${c.margin:.2f})" for c in low_margin
    ))
    total_revenue = sum(_float(r.get("revenue")) for r in rows)
    total_cost = sum(_float(r.get("cost")) for r in rows)
    lines.append(f"Totals: revenue=${total_revenue:.2f}, cost=${total_cost:.2f}, profit=${(total_revenue-total_cost):.2f}")
    return "\n".join(lines)

JSON_SCHEMA_HINT = r"""
Return ONLY valid JSON (no prose, no code fences) with this schema:
{
  "actions": [
    {
      "title": "short label",
      "reason": "why this helps",
      "est_impact_usd": 0,
      "targets": ["ClientA","ClientB"],
      "confidence": 0.0,
      "risk": "low|medium|high",
      "current_cost": 0,
      "projected_cost": 0,
      "savings_pct": 0
    }
  ]
}
"""

def _build_grounded_prompt(context_text: str) -> str:
    return (
        "You are FinOps+ Assistant for MSPs. Use the data to output 3 prioritized, "
        "actionable recommendations with savings & impact details.\n\n"
        f"FACTS:\n{context_text}\n\n"
        "Rules:\n"
        "- Think silently; OUTPUT ONLY JSON matching the schema.\n"
        "- Provide realistic est_impact_usd and confidence(0..1).\n"
        "- Fill current_cost/projected_cost if you can estimate; otherwise leave 0.\n\n"
        f"{JSON_SCHEMA_HINT}\n"
    )

def _extract_json(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r"```json\s*(\{.*?\})\s*```", s, flags=re.DOTALL | re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    i = s.find("{")
    j = s.rfind("}")
    if i != -1 and j != -1 and j > i:
        try:
            return json.loads(s[i:j+1])
        except Exception:
            pass
    raise ValueError("No valid JSON found in model output")

def _read_billing_csv_text(force_source: Optional[str] = None) -> str:
    csv_text: Optional[str] = None
    if force_source != "local" and use_s3():
        bucket = os.environ.get("S3_BUCKET")
        key = os.environ.get("S3_KEY", "billing_data.csv")
        logger.info("Reading billing CSV from S3: %s/%s", bucket, key)
        csv_text = read_s3_file(bucket, key)
        if csv_text is None:
            logger.warning("S3 read failed; falling back to local file.")

    if csv_text is None:
        local_path = os.path.join(os.path.dirname(__file__), "data", "billing_data.csv")
        logger.info("Reading billing CSV from local file: %s", local_path)
        if not os.path.exists(local_path):
            raise HTTPException(status_code=404, detail="Billing data not found (S3 failed and local missing).")
        with open(local_path, "r", encoding="utf-8") as f:
            csv_text = f.read()
    return csv_text

def _read_history_csv_text(key: str) -> str:
    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    if not use_s3():
        raise HTTPException(status_code=400, detail="S3 not configured")
    bucket = os.environ.get("S3_BUCKET")
    logger.info("Reading S3 historical file: %s/%s", bucket, key)
    csv_text = read_s3_file(bucket, key)
    if csv_text is None:
        raise HTTPException(status_code=404, detail="Historical key not found")
    return csv_text

def _key_allowed_for_user(key: str, user_sub: str, prefix: str) -> bool:
    if not key or not user_sub:
        return False
    if ".." in key:
        return False
    expected_prefix = f"{prefix}{user_sub}/"
    return key.startswith(expected_prefix)

def _decode_csv_bytes(upload_bytes: bytes) -> Tuple[str, str]:
    attempts = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
    last_err = None
    for enc in attempts:
        try:
            text = upload_bytes.decode(enc)
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            return text, enc
        except UnicodeDecodeError as e:
            last_err = e
            continue
    logger.error("Upload decode failed; tried encodings=%s; error=%s", attempts, last_err)
    raise HTTPException(status_code=400, detail="Invalid encoding: please upload UTF-8/UTF-8-BOM/Latin-1 CSV.")

def _attach_meta(ar: "AnalyzeResponse", meta: Dict[str, Any]) -> "AnalyzeResponse":
    try:
        ar.meta = meta
        return ar
    except Exception:
        data = ar.dict()
        data["meta"] = meta
        return AnalyzeResponse(**data)

ACTIONS_LOG_PATH = os.path.join(os.path.dirname(__file__), "data", "actions_log.jsonl")
DDB_TABLE = os.getenv("DDB_TABLE", "").strip()

def _to_ddb(obj: Any) -> Any:
    if isinstance(obj, float):
        if math.isfinite(obj):
            return Decimal(str(obj))
        return Decimal(0)
    if isinstance(obj, int):
        return Decimal(obj)
    if isinstance(obj, dict):
        return {k: _to_ddb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_ddb(v) for v in obj]
    return obj

def _persist_action_event(event: Dict[str, Any]) -> Tuple[bool, str, str]:
    event_id = event.get("id") or str(uuid.uuid4())
    event["id"] = event_id
    event.setdefault("ts", int(time.time()))
    if DDB_TABLE:
        try:
            ddb_item = _to_ddb(event)
            action_id = put_action_item(DDB_TABLE, ddb_item)
            if action_id:
                return True, f"ddb:{DDB_TABLE}", action_id
        except Exception:
            logger.exception("DDB persist failed; will fallback to file")
    try:
        os.makedirs(os.path.dirname(ACTIONS_LOG_PATH), exist_ok=True)
        with open(ACTIONS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
        return True, f"file:{ACTIONS_LOG_PATH}", event_id
    except Exception:
        logger.exception("file persist failed")
        return False, "error", event_id

def _format_actions_pretty(actions: list) -> str:
    lines = []
    for i, a in enumerate(actions[:3]):
        title = a.get("title", "")
        reason = a.get("reason", "")
        impact = a.get("est_impact_usd", 0)
        targets = a.get("targets", [])
        lines.append(f"{i+1}) {title}: {reason} (≈${impact}) targets={targets}")
    return "\n".join(lines) if lines else "No actions."

def _rule_based_actions(ar: "AnalyzeResponse") -> Dict[str, Any]:
    actions = []
    clients = list(ar.client_insights or [])
    all_zero_waste = all((c.license_waste_pct or 0) <= 0.1 for c in clients)
    if all_zero_waste:
        actions.append({
            "title": "Commit to Savings Plans / Reserved Instances",
            "reason": "Waste is minimal; use pricing commitments for steady workloads to reduce unit cost.",
            "est_impact_usd": 3000,
            "targets": [c.client for c in clients],
        })
    else:
        top_waste = sorted(clients, key=lambda x: (x.license_waste_pct or 0), reverse=True)[:2]
        actions.append({
            "title": "Right-size & reclaim unused licenses",
            "reason": "Reduce recurring waste by rightsizing or reclaiming entitlements.",
            "est_impact_usd": 2500,
            "targets": [c.client for c in top_waste],
        })
    low_margin = sorted(clients, key=lambda x: x.margin)[:2] if clients else []
    actions.append({
        "title": "Reprice low-margin contracts",
        "reason": "Underpriced workloads detected; re-negotiate/adjust SKUs to recover margin.",
        "est_impact_usd": 2000,
        "targets": [c.client for c in low_margin],
    })
    actions.append({
        "title": "Upsell higher-margin bundles (security/backup)",
        "reason": "Increase ARPU and retention with managed add-ons.",
        "est_impact_usd": 1500,
        "targets": [c.client for c in clients],
    })
    return {"actions": actions}

def _weighted_avg_waste(clients: List[ClientInsight]) -> float:
    if not clients:
        return 0.0
    total_cost = 0.0
    weighted = 0.0
    for c in clients:
        cost = float(getattr(c, "cost", 0.0) or 0.0)
        waste_pct = float(getattr(c, "license_waste_pct", 0.0) or 0.0)
        if cost > 0:
            total_cost += cost
            weighted += cost * waste_pct
    if total_cost <= 0:
        return 0.0
    return weighted / total_cost

def _rightsizing_simulator(ar: "AnalyzeResponse", recoverable_factor: float = 0.8) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for c in ar.client_insights or []:
        cost = float(c.cost or 0.0)
        waste_pct = float(c.license_waste_pct or 0.0) / 100.0
        if cost <= 0 or waste_pct <= 0:
            continue
        savings = max(0.0, cost * waste_pct * recoverable_factor)
        projected = max(0.0, cost - savings)
        out[c.client] = {
            "savings_usd": round(savings, 2),
            "current_cost": round(cost, 2),
            "projected_cost": round(projected, 2),
        }
    return out

def _detect_anomalies_llm(rows: List[Dict[str, Any]], ar: AnalyzeResponse, max_find: int = 3):
    try:
        by_client = {c.client: float(c.cost or 0) for c in ar.client_insights}
        lines = [f"{k}={v:.2f}" for k, v in sorted(by_client.items(), key=lambda kv: kv[1], reverse=True)]
        facts = " | ".join(lines)

        prompt = (
            "You are a FinOps anomaly detector. From the latest cost snapshot below, "
            "flag up to 3 items that look anomalously high relative to peers (z-score or >+20%). "
            "Return ONLY JSON with fields: title, reason, est_impact_usd, targets, confidence(0..1), risk.\n"
            f"SNAPSHOT: {facts}\n\n"
            "Schema:\n"
            "{ \"actions\": [ {"
            "\"title\": \"Spike in <Service/Client>\", "
            "\"reason\": \"why this looks anomalous\", "
            "\"est_impact_usd\": 0, "
            "\"targets\": [\"<Client>\"] , "
            "\"confidence\": 0.75, "
            "\"risk\": \"medium\" } ] }"
        )
        parsed, source = get_ai_json(prompt, max_tokens=500, retries=1)
        if parsed and isinstance(parsed, dict) and parsed.get("actions"):
            parsed["actions"] = parsed["actions"][:max_find]
            return parsed
    except Exception:
        pass
    return {"actions": []}

async def _recommend_from_rows(rows, ar: "AnalyzeResponse"):
    context_text = _summarize_for_prompt(rows, ar.client_insights)
    prompt = _build_grounded_prompt(context_text)
    parsed, source = get_ai_json(prompt, max_tokens=700, retries=1)
    if not (parsed and isinstance(parsed, dict) and "actions" in parsed):
        parsed = _rule_based_actions(ar)
        source = "rule-fallback"

    try:
        anomalies = _detect_anomalies_llm(rows, ar)
        if anomalies.get("actions"):
            parsed["actions"].extend(anomalies["actions"])
    except Exception:
        pass

    sims = _rightsizing_simulator(ar, recoverable_factor=0.8)

    for a in parsed.get("actions", []):
        a.setdefault("targets", [])
        a.setdefault("confidence", 0.6)
        a.setdefault("risk", "medium")

        cur = 0.0; proj = 0.0; sav = 0.0
        for t in a["targets"]:
            s = sims.get(t)
            if not s:
                continue
            cur += s.get("current_cost", 0.0)
            proj += s.get("projected_cost", 0.0)
            sav += s.get("savings_usd", 0.0)

        if cur > 0:
            a["current_cost"] = round(cur, 2)
            a["projected_cost"] = round(proj, 2)
            if sav > 0:
                a["est_impact_usd"] = max(float(a.get("est_impact_usd") or 0), round(sav, 2))
                a["savings_pct"] = round((sav/cur)*100.0, 1)

    pretty = _format_actions_pretty(parsed.get("actions", []))
    return parsed, pretty, source

# ===========================================================
# Budgets storage helpers
# ===========================================================
def _tenant_or_default(q_tenant: Optional[str]) -> str:
    if not BUDGETS_TENANTED:
        return ""
    t = (q_tenant or BUDGETS_TENANT_DEFAULT or "default").strip()
    t = t.replace("..", "_").replace("/", "_")
    return t

def _budgets_local_path(sub: str, tenant: Optional[str]) -> str:
    base = os.path.join(os.path.dirname(__file__), "data", "budgets")
    if BUDGETS_TENANTED:
        base = os.path.join(base, _tenant_or_default(tenant))
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"{sub}.json")

def _s3_budgets_key(sub: str, tenant: Optional[str]) -> str:
    if BUDGETS_TENANTED:
        return f"{S3_BUDGETS_PREFIX}{_tenant_or_default(tenant)}/{sub}.json"
    return f"{S3_BUDGETS_PREFIX}{sub}.json"

def _is_valid_number(v: Any) -> bool:
    try:
        x = float(v)
        return math.isfinite(x)
    except Exception:
        return False

def _load_budgets_for_user(sub: str, tenant: Optional[str]) -> Dict[str, float]:
    if not sub:
        return {}
    if use_s3():
        bucket = os.environ.get("S3_BUCKET")
        key = _s3_budgets_key(sub, tenant)
        txt = read_s3_file(bucket, key)
        if txt:
            try:
                obj = json.loads(txt)
                if isinstance(obj, dict):
                    return {str(k): float(v) for k, v in obj.items() if _is_valid_number(v)}
            except Exception:
                logger.warning("Failed to parse S3 budgets JSON for sub=%s", sub)
        return {}
    path = _budgets_local_path(sub, tenant)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
                if isinstance(obj, dict):
                    return {str(k): float(v) for k, v in obj.items() if _is_valid_number(v)}
        except Exception:
            logger.warning("Failed to read local budgets JSON for sub=%s", sub)
    return {}

def _save_budgets_for_user(sub: str, budgets: Dict[str, float], tenant: Optional[str]) -> bool:
    if not sub:
        return False
    cleaned = {str(k): max(0.0, float(v)) for k, v in (budgets or {}).items() if _is_valid_number(v)}
    payload_txt = json.dumps(cleaned)
    if use_s3():
        bucket = os.environ.get("S3_BUCKET")
        key = _s3_budgets_key(sub, tenant)
        ok = put_s3_object(bucket, key, payload_txt.encode("utf-8"), content_type="application/json")
        if ok:
            logger.info("Saved budgets to s3://%s/%s", bucket, key)
            return True
        logger.warning("Failed to put budgets to S3; will attempt local fallback")
    try:
        path = _budgets_local_path(sub, tenant)
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload_txt)
        logger.info("Saved budgets to local file: %s", path)
        return True
    except Exception:
        logger.exception("Saving budgets locally failed")
        return False

def _list_budgets_users(tenant: Optional[str]) -> List[str]:
    users: List[str] = []
    if use_s3():
        bucket = os.environ.get("S3_BUCKET")
        prefix = S3_BUDGETS_PREFIX
        if BUDGETS_TENANTED:
            prefix = f"{S3_BUDGETS_PREFIX}{_tenant_or_default(tenant)}/"
        objs = list_s3_objects(bucket, prefix, max_keys=1000)
        for o in objs:
            key = o.get("key") or o.get("Key") or ""
            if key.endswith(".json"):
                name = os.path.basename(key)[:-5]
                if name:
                    users.append(name)
        return sorted(list(set(users)))
    base = os.path.join(os.path.dirname(__file__), "data", "budgets")
    if BUDGETS_TENANTED:
        base = os.path.join(base, _tenant_or_default(tenant))
    if not os.path.isdir(base):
        return []
    for fn in os.listdir(base):
        if fn.endswith(".json"):
            users.append(fn[:-5])
    return sorted(list(set(users)))

# ===========================================================
# Alerts (server-side governance)
# ===========================================================
def _compute_alerts(client_insights: List[ClientInsight], budgets: Dict[str, float],
                    warn_pct: float = ALERT_WARN_PCT, breach_pct: float = ALERT_BREACH_PCT) -> List[AlertItem]:
    out: List[AlertItem] = []
    budgets = budgets or {}
    for c in client_insights or []:
        b = float(budgets.get(c.client, 0) or 0)
        if b <= 0:
            continue
        spend = float(c.cost or 0)
        pct = (spend / b) if b > 0 else 0.0
        status = "ok"
        if pct >= breach_pct:
            status = "breach"
        elif pct >= warn_pct:
            status = "warn"
        out.append(AlertItem(client=c.client, budget=b, spend=spend, pct=round(pct * 100.0, 1), status=status))
    return out

def _attach_alerts(ar: AnalyzeResponse, budgets: Dict[str, float]) -> AnalyzeResponse:
    try:
        ar.alerts = _compute_alerts(ar.client_insights, budgets)
        return ar
    except Exception:
        data = ar.dict()
        data["alerts"] = [a.dict() for a in _compute_alerts(ar.client_insights, budgets)]
        return AnalyzeResponse(**data)

# ===========================================================
# PDF helpers
# ===========================================================
_styles = getSampleStyleSheet()
_styles.add(ParagraphStyle(name="KPIHeading", fontName="Helvetica-Bold", fontSize=11, textColor=colors.HexColor("#111827")))
_styles.add(ParagraphStyle(name="SmallNote", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#6B7280")))

def _money(n):
    try:
        v = float(n)
        return f"${v:,.2f}"
    except Exception:
        return "—"

def _pct(n):
    try:
        v = float(n)
        return f"{v:.1f}%"
    except Exception:
        return "—"

def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4

    if os.path.exists(PDF_LOGO_PATH):
        try:
            img = ImageReader(PDF_LOGO_PATH)
            canvas.drawImage(img, 1.2*cm, h - 2.0*cm, width=1.2*cm, height=1.2*cm, mask='auto')
        except Exception:
            pass

    canvas.setFont("Helvetica-Bold", 11)
    canvas.setFillColor(colors.HexColor("#111827"))
    canvas.drawString(2.7*cm, h - 1.2*cm, PDF_BRAND)

    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawRightString(w - 1.2*cm, h - 1.2*cm, datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))

    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawRightString(w - 1.2*cm, 1.2*cm, f"Page {doc.page}")
    canvas.restoreState()

def _draw_watermark(canvas, text: str = PDF_WATERMARK):
    w, h = A4
    canvas.saveState()
    canvas.setFillColor(colors.Color(0.85, 0.85, 0.85, alpha=0.20))
    canvas.setFont("Helvetica-Bold", 60)
    canvas.translate(w/2, h/2)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, text)
    canvas.restoreState()

def _draw_cover(canvas, brand: str, tagline: str, logo_path: str):
    w, h = A4
    canvas.saveState()

    canvas.setFillColor(colors.HexColor("#1D4ED8"))
    canvas.rect(0, h - 2.2*cm, w, 2.2*cm, fill=1, stroke=0)

    if os.path.exists(logo_path):
        try:
            img = ImageReader(logo_path)
            canvas.drawImage(img, w/2 - 32, h - 1.8*cm, width=18, height=18, mask='auto')
        except Exception:
            pass

    canvas.setFillColor(colors.HexColor("#111827"))
    canvas.setFont("Helvetica-Bold", 22)
    canvas.drawCentredString(w/2, h - 4.0*cm, f"{brand} — Executive Report")

    canvas.setFont("Helvetica", 11)
    canvas.setFillColor(colors.HexColor("#374151"))
    canvas.drawCentredString(w/2, h - 4.9*cm, "AWS + Kiros | Hackathon Prototype")

    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.setFont("Helvetica", 9)
    canvas.drawCentredString(w/2, h - 5.7*cm, datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))

    canvas.restoreState()

def _kpi_table(ar):
    kpi_data = [
        ["Total Revenue", _money(ar.total_revenue)],
        ["Total Cost", _money(ar.total_cost)],
        ["Total Profit", _money(ar.total_profit)],
    ]
    t = Table(kpi_data, colWidths=[6.0*cm, 8.0*cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ("LINEBELOW", (0,0), (-1,0), 0.6, colors.HexColor("#D1D5DB")),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F9FAFB")]),
        ("BOX", (0,0), (-1,-1), 0.6, colors.HexColor("#D1D5DB")),
        ("INNERGRID", (0,0), (-1,-1), 0.3, colors.HexColor("#E5E7EB")),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
    ]))
    return t

def _clients_table(ar, budgets):
    header = ["Client", "Revenue", "Cost", "Margin", "Waste %", "Budget", "Status"]
    rows = [header]
    budgets = budgets or {}
    alerts_map = {a.client: a for a in (ar.alerts or [])}

    for c in ar.client_insights:
        b = budgets.get(c.client, 0.0) or 0.0
        a = alerts_map.get(c.client)
        status = a.status.upper() if a else ("OK" if b > 0 else "—")
        rows.append([
            c.client, _money(c.revenue), _money(c.cost), _money(c.margin),
            _pct(c.license_waste_pct), (_money(b) if b > 0 else "—"), status
        ])

    t = Table(rows, colWidths=[4.0*cm, 2.4*cm, 2.4*cm, 2.4*cm, 2.2*cm, 2.6*cm, 2.0*cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 10),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F3F4F6")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#111827")),

        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,1), (-1,-1), 9.5),
        ("ALIGN", (1,1), (5,-1), "RIGHT"),
        ("ALIGN", (6,1), (6,-1), "CENTER"),

        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#FAFAFA")]),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#E5E7EB")),
        ("BOX", (0,0), (-1,-1), 0.4, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    return t

def _alerts_table(ar):
    alerts = list(ar.alerts or [])
    title = Paragraph("<b>Budget Alerts</b>", _styles["Heading2"])

    if not alerts:
        note = Paragraph("No alerts for current budgets.", _styles["Normal"])
        return [title, Spacer(1, 0.2*cm), note]

    header = ["Client", "Budget", "Spend", "% of Budget", "Status"]
    rows = [header]
    for a in alerts:
        rows.append([a.client, _money(a.budget), _money(a.spend), f"{a.pct:.1f}%", a.status.upper()])

    t = Table(rows, colWidths=[4.0*cm, 3.0*cm, 3.0*cm, 3.0*cm, 2.0*cm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,0), 10),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#FEF3C7")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#111827")),

        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,1), (-1,-1), 9.5),
        ("ALIGN", (1,1), (3,-1), "RIGHT"),
        ("ALIGN", (4,1), (4,-1), "CENTER"),

        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#FFFBEB")]),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#FCD34D")),
        ("BOX", (0,0), (-1,-1), 0.4, colors.HexColor("#F59E0B")),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    return [title, Spacer(1, 0.2*cm), t]

def _build_pdf_bytes(brand: str, tagline: str, logo_path: str,
                     ar: "AnalyzeResponse", budgets: Dict[str, float]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.7*cm, rightMargin=1.7*cm,
        topMargin=2.6*cm, bottomMargin=2.0*cm
    )

    story = []

    def _on_cover(canvas, doc):
        _draw_cover(canvas, brand, tagline, logo_path)
        _draw_watermark(canvas, PDF_WATERMARK)

    story.append(Spacer(1, 10*cm))
    story.append(PageBreak())

    story.append(Paragraph("Executive Summary", _styles["Title"]))
    story.append(Paragraph(tagline, _styles["SmallNote"]))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Key Metrics", _styles["KPIHeading"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(_kpi_table(ar))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Client Profitability & Budgets", _styles["Heading2"]))
    story.append(_clients_table(ar, budgets))
    story.append(Spacer(1, 0.5*cm))

    for blk in _alerts_table(ar):
        story.append(blk)

    def _on_later(canvas, doc):
        _header_footer(canvas, doc)
        _draw_watermark(canvas, PDF_WATERMARK)

    doc.build(story, onFirstPage=_on_cover, onLaterPages=_on_later)

    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes

def _build_pdf_bytes_simple(title: str, subtitle: str) -> bytes:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(w/2, h - 3*cm, title)
    c.setFont("Helvetica", 12)
    c.drawCentredString(w/2, h - 3.8*cm, subtitle)
    c.showPage()
    c.save()
    return buf.getvalue()

# ===========================================================
# Routes
# ===========================================================
@app.get("/")
def root():
    return {"service": "FinOps+ Agent backend", "status": "ok"}

@app.get("/health")
def health():
    return {"status": "ok", "message": "FinOps+ backend running successfully"}

# alias for your tests
@app.get("/healthz")
def healthz_alias():
    return {"ok": True}

@app.get("/debug-config")
def debug_config():
    return {
        "provider": os.getenv("PROVIDER"),
        "region": os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
        "bedrock_model": os.getenv("BEDROCK_MODEL_ID"),
        "s3_bucket": os.getenv("S3_BUCKET"),
        "s3_key": os.getenv("S3_KEY") or "billing_data.csv",
        "aws_profile_env": os.getenv("AWS_PROFILE"),
        "cognito": {
            "enabled": COGNITO_ENABLED,
            "region": COGNITO_REGION,
            "user_pool_id": COGNITO_USER_POOL_ID,
            "audience": COGNITO_AUDIENCE,
        },
        "ddb": {
            "table": os.getenv("DDB_TABLE"),
            "region": os.getenv("DDB_REGION") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
        },
        "allow_public_actions": os.getenv("ALLOW_PUBLIC_ACTIONS", "false"),
        "budgets": {
            "prefix": S3_BUDGETS_PREFIX,
            "tenanted": BUDGETS_TENANTED,
            "tenant_default": BUDGETS_TENANT_DEFAULT,
            "public_budget_sub": PUBLIC_BUDGET_SUB,
        },
        "alerts": {"warn": ALERT_WARN_PCT, "breach": ALERT_BREACH_PCT},
        "admin": {
            "emails": list(ADMIN_EMAILS),
            "group": ADMIN_GROUP or None,
        },
        "pdf": {
            "brand": PDF_BRAND,
            "tagline": PDF_TAGLINE,
            "watermark": PDF_WATERMARK,
            "logo_path": PDF_LOGO_PATH,
        }
    }

# ---------- Budgets endpoints (user; auth-optional) ----------
@app.get("/budgets")
async def get_budgets(
    tenant: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(get_user_optional),
):
    sub = (user.get("sub") if isinstance(user, dict) else None) or PUBLIC_BUDGET_SUB
    if sub == "public-demo":
        sub = PUBLIC_BUDGET_SUB
    return _load_budgets_for_user(sub, tenant)

@app.post("/budgets")
async def save_budgets(
    payload: Dict[str, Any] = Body(...),
    tenant: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(get_user_optional),
):
    if not ((COGNITO_ENABLED and user) or ALLOW_PUBLIC_ACTIONS):
        raise HTTPException(status_code=401, detail="Unauthorized")

    sub = (user.get("sub") if isinstance(user, dict) else None) or PUBLIC_BUDGET_SUB
    if sub == "public-demo":
        sub = PUBLIC_BUDGET_SUB

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be an object map of client->budget")
    cleaned: Dict[str, float] = {}
    for k, v in payload.items():
        if _is_valid_number(v):
            cleaned[str(k)] = max(0.0, float(v))
    ok = _save_budgets_for_user(sub, cleaned, tenant)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save budgets")
    return {"ok": True, "count": len(cleaned), "sub": sub}

# ---------- Budgets endpoints (admin) ----------
@app.get("/budgets/admin")
async def admin_list_budgets(
    tenant: Optional[str] = Query(default=None),
    include: int = Query(default=0, ge=0, le=1),
    _admin: Dict[str, Any] = Depends(get_admin_user),
):
    subs = _list_budgets_users(tenant)
    if include != 1:
        return {"tenant": _tenant_or_default(tenant) if BUDGETS_TENANTED else None, "users": subs}
    items = {}
    for s in subs:
        items[s] = _load_budgets_for_user(s, tenant)
    return {"tenant": _tenant_or_default(tenant) if BUDGETS_TENANTED else None, "items": items}

@app.get("/budgets/admin/{sub}")
async def admin_get_budgets_for_sub(
    sub: str,
    tenant: Optional[str] = Query(default=None),
    _admin: Dict[str, Any] = Depends(get_admin_user),
):
    return _load_budgets_for_user(sub, tenant)

@app.post("/budgets/admin/{sub}")
async def admin_set_budgets_for_sub(
    sub: str,
    tenant: Optional[str] = Query(default=None),
    payload: Dict[str, Any] = Body(...),
    _admin: Dict[str, Any] = Depends(get_admin_user),
):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be an object map of client->budget")
    cleaned: Dict[str, float] = {}
    for k, v in payload.items():
        if _is_valid_number(v):
            cleaned[str(k)] = max(0.0, float(v))
    ok = _save_budgets_for_user(sub, cleaned, tenant)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save budgets")
    return {"ok": True, "count": len(cleaned), "sub": sub}

# ---- Samples for judges ----
SAMPLE_MAP = {
    "balanced": "demo_upload_balanced.csv",
    "waste": "demo_upload_waste.csv",
    "aws": "demo_upload_aws_fallback.csv",
}

@app.get("/sample-csv/{sample_name}")
def sample_csv(sample_name: str):
    filename = SAMPLE_MAP.get(sample_name.lower())
    if not filename:
        raise HTTPException(status_code=404, detail="Sample not found")
    path = os.path.join(os.path.dirname(__file__), "data", filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Sample file missing on server")
    return FileResponse(path, media_type="text/csv", filename=filename)

def _read_sample_csv_text(sample: str) -> str:
    fname = SAMPLE_MAP.get(sample.lower())
    if not fname:
        raise HTTPException(status_code=400, detail="Unknown sample")
    path = os.path.join(os.path.dirname(__file__), "data", fname)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Sample file missing on server")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/demo/analyze", response_model=AnalyzeResponse)
def demo_analyze(sample: str, tenant: Optional[str] = Query(default=None),
                 user: Dict[str, Any] = Depends(get_user_optional)):
    csv_text = _read_sample_csv_text(sample)
    _, ar = _analyze_text(csv_text)
    sub = (user.get("sub") if isinstance(user, dict) else None) or PUBLIC_BUDGET_SUB
    if sub == "public-demo":
        sub = PUBLIC_BUDGET_SUB
    budgets = _load_budgets_for_user(sub, tenant)
    ar = _attach_alerts(ar, budgets)
    ar = _attach_meta(ar, {"source": "sample", "sample": sample, "budgets_sub": sub})
    return ar

@app.get("/demo/recommend", response_model=RecommendResponse)
async def demo_recommend(
    sample: str,
    _rl: Any = Depends(rate_limit),
    user: Dict[str, Any] = Depends(get_current_user),
):
    csv_text = _read_sample_csv_text(sample)
    rows, ar = _analyze_text(csv_text)
    parsed, pretty, source = await _recommend_from_rows(rows, ar)
    parsed_model = RecommendJSON(**parsed)
    return RecommendResponse(ai_recommendation=pretty, source=source, parsed_json=parsed_model)

DEFAULT_ANALYZE_SOURCE = os.getenv("ANALYZE_DEFAULT_SOURCE", "").strip().lower()

@app.get("/analyze", response_model=AnalyzeResponse)
def analyze(
    source: Optional[str] = Query(default=None),
    key: Optional[str] = Query(default=None),
    tenant: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(get_user_optional),
):
    if key:
        csv_text = _read_history_csv_text(key)
        _, ar = _analyze_text(csv_text)
        sub = (user.get("sub") if isinstance(user, dict) else None) or PUBLIC_BUDGET_SUB
        if sub == "public-demo":
            sub = PUBLIC_BUDGET_SUB
        budgets = _load_budgets_for_user(sub, tenant)
        ar = _attach_alerts(ar, budgets)
        meta = {"source": "history", "key": key, "budgets_sub": sub}
        ar = _attach_meta(ar, meta)
        return ar

    eff_source = (source or DEFAULT_ANALYZE_SOURCE or None)
    if eff_source and eff_source not in ("s3", "local"):
        eff_source = None

    csv_text = _read_billing_csv_text(force_source=eff_source)
    _, ar = _analyze_text(csv_text)

    sub = (user.get("sub") if isinstance(user, dict) else None) or PUBLIC_BUDGET_SUB
    if sub == "public-demo":
        sub = PUBLIC_BUDGET_SUB
    budgets = _load_budgets_for_user(sub, tenant)
    ar = _attach_alerts(ar, budgets)

    meta = {
        "source": ("local" if eff_source == "local" or not use_s3() else "s3"),
        "key": (os.getenv("S3_KEY", "billing_data.csv") if use_s3() and eff_source != "local"
                else "data/billing_data.csv"),
        "budgets_sub": sub,
        "tenant_resolved": (_tenant_or_default(tenant) if BUDGETS_TENANTED else None),
    }
    ar = _attach_meta(ar, meta)
    return ar

@app.post("/upload", response_model=UploadAnalyzeResponse)
async def upload_csv(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
):
    raw_bytes = await file.read()
    if not raw_bytes or len(raw_bytes) < 3:
        raise HTTPException(status_code=400, detail="Empty or invalid file")

    text, enc_used = _decode_csv_bytes(raw_bytes)
    logger.info("Upload decode successful using encoding=%s; bytes=%d", enc_used, len(raw_bytes))

    _, ar = _analyze_text(text)

    stored_key: Optional[str] = None
    if use_s3():
        bucket = os.environ.get("S3_BUCKET")
        prefix = os.environ.get("S3_UPLOAD_PREFIX", "uploads/")
        sub = user.get("sub", "anon")
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        safe_name = os.path.basename(file.filename or "upload.csv")
        key = f"{prefix}{sub}/{ts}_{safe_name}"
        ok = put_s3_object(bucket, key, raw_bytes, content_type="text/csv")
        if ok:
            stored_key = key
            logger.info("Stored uploaded CSV → s3://%s/%s", bucket, key)

    return UploadAnalyzeResponse(
        total_revenue=ar.total_revenue,
        total_cost=ar.total_cost,
        total_profit=ar.total_profit,
        client_insights=ar.client_insights,
        stored_key=stored_key,
        meta={"source": "upload", "key": stored_key} if stored_key else {"source": "upload"},
    )

# ===========================================================
# History + analyze/recommend by historical key
# ===========================================================
@app.get("/history")
async def history(user: Dict[str, Any] = Depends(get_current_user)):
    if not use_s3():
        return {"items": [], "note": "S3 not configured"}
    bucket = os.environ.get("S3_BUCKET")
    prefix = os.environ.get("S3_UPLOAD_PREFIX", "uploads/")
    sub = user.get("sub")
    if not sub:
        raise HTTPException(status_code=400, detail="Missing user.sub in token")

    user_prefix = f"{prefix}{sub}/"
    items = list_s3_objects(bucket, user_prefix, max_keys=500)
    items.sort(key=lambda x: x.get("last_modified") or "", reverse=True)
    return {"items": items, "bucket": bucket, "prefix": user_prefix}

@app.get("/history/latest")
async def history_latest(user: Dict[str, Any] = Depends(get_current_user)):
    if not use_s3():
        return {"item": None, "note": "S3 not configured"}
    bucket = os.environ.get("S3_BUCKET")
    prefix = os.environ.get("S3_UPLOAD_PREFIX", "uploads/")
    sub = user.get("sub")
    if not sub:
        raise HTTPException(status_code=400, detail="Missing user.sub in token")

    user_prefix = f"{prefix}{sub}/"
    items = list_s3_objects(bucket, user_prefix, max_keys=100)
    items.sort(key=lambda x: x.get("last_modified") or "", reverse=True)
    return {"item": items[0] if items else None}

@app.get("/history/presign")
async def history_presign(
    key: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    if not use_s3():
        raise HTTPException(status_code=400, detail="S3 not configured")
    bucket = os.environ.get("S3_BUCKET")
    prefix = os.environ.get("S3_UPLOAD_PREFIX", "uploads/")
    sub = user.get("sub")
    if not _key_allowed_for_user(key, sub, prefix):
        raise HTTPException(status_code=403, detail="Key not allowed")
    url = generate_presigned_get_url(bucket, key, expires_in=900)
    if not url:
        raise HTTPException(status_code=500, detail="Failed to generate URL")
    return {"url": url}

@app.delete("/history")
async def history_delete(
    key: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    if not use_s3():
        raise HTTPException(status_code=400, detail="S3 not configured")
    bucket = os.environ.get("S3_BUCKET")
    prefix = os.environ.get("S3_UPLOAD_PREFIX", "uploads/")
    sub = user.get("sub")
    if not _key_allowed_for_user(key, sub, prefix):
        raise HTTPException(status_code=403, detail="Key not allowed")
    ok = delete_s3_object(bucket, key)
    if not ok:
        raise HTTPException(status_code=500, detail="Delete failed")
    return {"deleted": True, "key": key}

@app.get("/analyze/by-key", response_model=AnalyzeResponse)
async def analyze_by_key(
    key: str,
    tenant: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(get_current_user),
):
    if not use_s3():
        raise HTTPException(status_code=400, detail="S3 not configured")
    bucket = os.environ.get("S3_BUCKET")
    prefix = os.environ.get("S3_UPLOAD_PREFIX", "uploads/")
    sub = user.get("sub")
    if not _key_allowed_for_user(key, sub, prefix):
        raise HTTPException(status_code=403, detail="Key not allowed")

    csv_text = read_s3_file(bucket, key)
    if csv_text is None:
        raise HTTPException(status_code=404, detail="Could not read specified key")
    _, ar = _analyze_text(csv_text)

    budgets = _load_budgets_for_user(sub, tenant)
    ar = _attach_alerts(ar, budgets)

    ar = _attach_meta(ar, {"source": "history", "key": key, "budgets_sub": sub})
    return ar

@app.get("/recommend/by-key", response_model=RecommendResponse)
async def recommend_by_key(
    key: str,
    _rl: Any = Depends(rate_limit),
    user: Dict[str, Any] = Depends(get_current_user),
):
    if not use_s3():
        raise HTTPException(status_code=400, detail="S3 not configured")
    bucket = os.environ.get("S3_BUCKET")
    prefix = os.environ.get("S3_UPLOAD_PREFIX", "uploads/")
    sub = user.get("sub")
    if not _key_allowed_for_user(key, sub, prefix):
        raise HTTPException(status_code=403, detail="Key not allowed")

    csv_text = read_s3_file(bucket, key)
    if csv_text is None:
        raise HTTPException(status_code=404, detail="Could not read specified key")

    rows, ar = _analyze_text(csv_text)
    parsed, pretty, source = await _recommend_from_rows(rows, ar)
    parsed_model = RecommendJSON(**parsed)
    return RecommendResponse(ai_recommendation=pretty, source=source, parsed_json=parsed_model)

# ===========================================================
# Existing recommend (most recent source S3/local)
# ===========================================================
@app.get("/recommend", response_model=RecommendResponse)
async def recommend(
    _rl: Any = Depends(rate_limit),
    user: Dict[str, Any] = Depends(get_current_user),
):
    csv_text = _read_billing_csv_text()
    rows, ar = _analyze_text(csv_text)
    parsed, pretty, source = await _recommend_from_rows(rows, ar)
    parsed_model = RecommendJSON(**parsed)
    return RecommendResponse(ai_recommendation=pretty, source=source, parsed_json=parsed_model)

# ===========================================================
# NEW: Industry Benchmarks API (dynamic)
# ===========================================================
@app.get("/benchmarks", response_model=BenchmarkResponse)
def get_benchmarks(
    industry: str = Query(default="msp"),
    source: Optional[str] = Query(default=None, description="s3|local|auto"),
    key: Optional[str] = Query(default=None, description="history key (optional)"),
    tenant: Optional[str] = Query(default=None),
):
    if key:
        csv_text = _read_history_csv_text(key)
    else:
        eff_source = (source or DEFAULT_ANALYZE_SOURCE or None)
        if eff_source and eff_source not in ("s3", "local"):
            eff_source = None
        csv_text = _read_billing_csv_text(force_source=eff_source)

    _, ar = _analyze_text(csv_text)

    your_waste_pct = _weighted_avg_waste(ar.client_insights)

    industry = (industry or "msp").strip().lower()
    base_map = {
        "msp": 22.0,
        "saas": 18.0,
        "it": 25.0,
        "general": 20.0,
    }
    industry_avg = float(base_map.get(industry, base_map["msp"]))

    sims = _rightsizing_simulator(ar)
    potential_savings = sum(v.get("savings_usd", 0.0) for v in sims.values())

    return BenchmarkResponse(
        source="api",
        industry=industry.upper(),
        industry_waste_pct=round(industry_avg, 1),
        industry_avg_waste_pct=round(industry_avg, 1),
        your_waste_pct=round(your_waste_pct, 1),
        potential_savings_usd=round(potential_savings, 2),
        method="cost-weighted license_waste_pct; recoverable_factor=0.8",
        notes="Industry average is mocked; wire to real dataset for production.",
    )

# ===========================================================
# Execute Action + Actions Log
# ===========================================================
@app.post("/execute_action", response_model=ExecuteActionResponse)
async def execute_action(
    payload: ExecuteActionRequest,
    user: Dict[str, Any] = Depends(get_user_optional),
):
    action = payload.action.dict()
    sub = user.get("sub", "anon") if isinstance(user, dict) else "anon"
    email = (user.get("email") if isinstance(user, dict) else None) or \
            (user.get("username") if isinstance(user, dict) else None) or "unknown"

    so_result = run_superops_action({
        "user": {"sub": sub, "email": email},
        "action": action,
    })

    event = {
        "id": str(uuid.uuid4()),
        "user_sub": sub,
        "user_email": email,
        "action": action,
        "superops": so_result,
        "ts": int(time.time()),
        "source": "finops-agent",
        "auth": ("public" if (not COGNITO_ENABLED or ALLOW_PUBLIC_ACTIONS) and (sub in ("public-demo", "anon")) else "cognito"),
    }
    ok, stored_where, action_id = _persist_action_event(event)

    return ExecuteActionResponse(
        executed=True,
        id=action_id,
        stored=stored_where,
        preview={
            "title": action.get("title"),
            "targets": action.get("targets", []),
            "impact": action.get("est_impact_usd", 0),
            "key": action.get("key"),
        },
        superops_result=so_result,
    )

@app.get("/actions")
def list_actions():
    out = []
    if os.path.exists(ACTIONS_LOG_PATH):
        with open(ACTIONS_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except:
                    pass
    return {"items": out[-50:][::-1], "store": ACTIONS_LOG_PATH, "ddb_table": DDB_TABLE or None}

@app.get("/mockclients")
def mockclients():
    if os.getenv("MOCK_CLIENTS_ENABLED", "true").lower() == "true":
        return get_mock_kiros_clients()
    return []

# ===========================================================
# PDF Export endpoint
# ===========================================================
@app.get("/export/pdf")
async def export_pdf(
    source: Optional[str] = Query(default=None, description="s3 | local | auto"),
    key: Optional[str] = Query(default=None, description="history key if exporting a specific upload"),
    tenant: Optional[str] = Query(default=None),
    include_reco: int = Query(default=0, ge=0, le=1),
    simple: int = Query(default=0, ge=0, le=1),
    user: Dict[str, Any] = Depends(get_user_optional),
):
    if key:
        csv_text = _read_history_csv_text(key)
        _, ar = _analyze_text(csv_text)
        sub_for_budgets = (user.get("sub") if isinstance(user, dict) else None) or PUBLIC_BUDGET_SUB
        if sub_for_budgets == "public-demo":
            sub_for_budgets = PUBLIC_BUDGET_SUB
        budgets = _load_budgets_for_user(sub_for_budgets, tenant)
        ar = _attach_alerts(ar, budgets)
        ar = _attach_meta(ar, {"source": "history", "key": key, "budgets_sub": sub_for_budgets})
    else:
        eff_source = (source or DEFAULT_ANALYZE_SOURCE or None)
        if eff_source and eff_source not in ("s3", "local"):
            eff_source = None
        csv_text = _read_billing_csv_text(force_source=eff_source)
        _, ar = _analyze_text(csv_text)
        sub_for_budgets = (user.get("sub") if isinstance(user, dict) else None) or PUBLIC_BUDGET_SUB
        if sub_for_budgets == "public-demo":
            sub_for_budgets = PUBLIC_BUDGET_SUB
        budgets = _load_budgets_for_user(sub_for_budgets, tenant)
        ar = _attach_alerts(ar, budgets)
        ar = _attach_meta(ar, {
            "source": ("local" if eff_source == "local" or not use_s3() else "s3"),
            "key": (os.getenv("S3_KEY", "billing_data.csv") if use_s3() and eff_source != "local"
                    else "data/billing_data.csv"),
            "budgets_sub": sub_for_budgets
        })

    if simple == 1:
        pdf_bytes = _build_pdf_bytes_simple("FinOps+ Report", "Simple canvas smoke test")
    else:
        pdf_bytes = _build_pdf_bytes(PDF_BRAND, PDF_TAGLINE, PDF_LOGO_PATH, ar, budgets)

    if not isinstance(pdf_bytes, (bytes, bytearray)) or len(pdf_bytes) < 8 or not bytes(pdf_bytes).startswith(b"%PDF-"):
        return JSONResponse({"detail": "PDF build failed"}, status_code=500)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        tmp.write(pdf_bytes)
        tmp.flush()
        tmp.close()
        filename = f'finops_report_{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}.pdf'
        return FileResponse(
            path=tmp.name,
            media_type="application/pdf",
            filename=filename,
            headers={"Cache-Control": "no-store"}
        )
    except Exception:
        try:
            tmp.close()
        except:
            pass
        raise

# ===========================================================
# Convenience Aliases under /api/* (so UI and curl both work)
# ===========================================================
@app.get("/api/health")
def api_health_alias():
    return health()

@app.get("/api/mockclients")
def api_mockclients_alias():
    return mockclients()

@app.get("/api/analyze", response_model=AnalyzeResponse)
def api_analyze_alias(
    source: Optional[str] = Query(default=None),
    key: Optional[str] = Query(default=None),
    tenant: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(get_user_optional),
):
    return analyze(source=source, key=key, tenant=tenant, user=user)

@app.get("/api/benchmarks", response_model=BenchmarkResponse)
def api_benchmarks_alias(
    industry: str = Query(default="msp"),
    source: Optional[str] = Query(default=None),
    key: Optional[str] = Query(default=None),
    tenant: Optional[str] = Query(default=None),
):
    return get_benchmarks(industry=industry, source=source, key=key, tenant=tenant)

@app.post("/api/upload", response_model=UploadAnalyzeResponse)
async def api_upload_alias(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
):
    return await upload_csv(file=file, user=user)

@app.get("/api/history")
async def api_history_alias(user: Dict[str, Any] = Depends(get_current_user)):
    return await history(user=user)

@app.get("/api/history/latest")
async def api_history_latest_alias(user: Dict[str, Any] = Depends(get_current_user)):
    return await history_latest(user=user)

@app.get("/api/history/presign")
async def api_history_presign_alias(
    key: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    return await history_presign(key=key, user=user)

@app.delete("/api/history")
async def api_history_delete_alias(
    key: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    return await history_delete(key=key, user=user)

@app.get("/api/analyze/by-key", response_model=AnalyzeResponse)
async def api_analyze_by_key_alias(
    key: str,
    tenant: Optional[str] = Query(default=None),
    user: Dict[str, Any] = Depends(get_current_user),
):
    return await analyze_by_key(key=key, tenant=tenant, user=user)

@app.get("/api/recommend/by-key", response_model=RecommendResponse)
async def api_recommend_by_key_alias(
    key: str,
    _rl: Any = Depends(rate_limit),
    user: Dict[str, Any] = Depends(get_current_user),
):
    return await recommend_by_key(key=key, _rl=_rl, user=user)

@app.get("/api/recommend", response_model=RecommendResponse)
async def api_recommend_alias(
    _rl: Any = Depends(rate_limit),
    user: Dict[str, Any] = Depends(get_current_user),
):
    return await recommend(_rl=_rl, user=user)

@app.get("/api/export/pdf")
async def api_export_pdf_alias(
    source: Optional[str] = Query(default=None),
    key: Optional[str] = Query(default=None),
    tenant: Optional[str] = Query(default=None),
    include_reco: int = Query(default=0, ge=0, le=1),
    simple: int = Query(default=0, ge=0, le=1),
    user: Dict[str, Any] = Depends(get_user_optional),
):
    return await export_pdf(
        source=source, key=key, tenant=tenant, include_reco=include_reco, simple=simple, user=user
    )

# ---------- optional: quick route listing ----------
@app.get("/_routes")
def list_routes():
    return [{"path": r.path, "methods": list(r.methods)} for r in app.router.routes]

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.options("/{rest_of_path:path}")
def options_cors(rest_of_path: str = ""):
    # Return 204 quickly; CORSMiddleware will add headers
    return Response(status_code=204)

from mangum import Mangum
handler = Mangum(app)
