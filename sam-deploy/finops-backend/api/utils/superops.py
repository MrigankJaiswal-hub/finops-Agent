# backend/utils/superops.py
import os
import json
import logging
import requests
from typing import Dict, Any

logger = logging.getLogger("finops-superops")

SUPEROPS_BASE = os.getenv("SUPEROPS_BASE", "https://api.superops.ai")
SUPEROPS_API_KEY = os.getenv("SUPEROPS_API_KEY")

def run_superops_action(action: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send an action to SuperOps (if API key provided).
    If not configured, returns a dry-run response.
    """
    if not SUPEROPS_API_KEY:
        return {
            "mode": "dry-run",
            "message": "SUPEROPS_API_KEY not set; no live call performed.",
            "echo": action,
        }

    try:
        # NOTE: Replace with the actual SuperOps endpoint when available.
        url = f"{SUPEROPS_BASE.rstrip('/')}/v1/agent/actions"
        headers = {
            "Authorization": f"Bearer {SUPEROPS_API_KEY}",
            "Content-Type": "application/json",
        }
        resp = requests.post(url, headers=headers, data=json.dumps(action), timeout=15)
        resp.raise_for_status()
        return {"mode": "live", "status": resp.status_code, "data": resp.json()}
    except Exception as e:
        logger.exception("SuperOps call failed")
        return {"mode": "live", "error": str(e), "echo": action}
