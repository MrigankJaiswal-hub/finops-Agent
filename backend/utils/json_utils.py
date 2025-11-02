# backend/utils/json_utils.py
import json
import re
from typing import Any, Optional

FENCE = re.compile(r"```(?:json)?(.*?)```", re.DOTALL | re.IGNORECASE)

def extract_json(text: str) -> Optional[Any]:
    """
    Try to coerce JSON from LLM output:
    - fenced ```json blocks
    - first {...} or [...]
    """
    if not text:
        return None

    m = FENCE.search(text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass

    # fallback: find first balanced { } or [ ]
    brace = _slice_brackets(text, "{", "}")
    if brace:
        try:
            return json.loads(brace)
        except Exception:
            pass
    brack = _slice_brackets(text, "[", "]")
    if brack:
        try:
            return json.loads(brack)
        except Exception:
            pass
    return None

def _slice_brackets(s: str, open_c: str, close_c: str) -> Optional[str]:
    depth = 0
    start = -1
    for i, ch in enumerate(s):
        if ch == open_c:
            if depth == 0:
                start = i
            depth += 1
        elif ch == close_c and depth > 0:
            depth -= 1
            if depth == 0 and start != -1:
                return s[start:i+1]
    return None
