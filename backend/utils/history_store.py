# backend/utils/history_store.py
import os
import json
import time
from typing import Dict, List

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
EVENT_LOG = os.path.join(DATA_DIR, "history.jsonl")

os.makedirs(DATA_DIR, exist_ok=True)

def append_event(evt: Dict) -> bool:
    """Append an event as a JSON line. Returns True on success."""
    try:
        with open(EVENT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(evt, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False

def read_recent(limit: int = 100, etype: str | None = None) -> List[Dict]:
    """Return most recent events (optionally filtered by type)."""
    items: List[Dict] = []
    if not os.path.exists(EVENT_LOG):
        return items
    with open(EVENT_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line.strip())
                if not obj:
                    continue
                if etype and obj.get("type") != etype:
                    continue
                items.append(obj)
            except Exception:
                continue
    # newest first
    items.sort(key=lambda x: x.get("ts", 0), reverse=True)
    return items[: max(1, limit)]
