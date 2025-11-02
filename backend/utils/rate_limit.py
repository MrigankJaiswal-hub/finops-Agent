# backend/utils/rate_limit.py
import time
from collections import deque
from typing import Deque, Dict, Tuple

class SlidingWindowLimiter:
    """
    In-memory sliding window limiter.
    key -> deque[timestamps]
    """
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self.bucket: Dict[str, Deque[float]] = {}

    def allow(self, key: str) -> Tuple[bool, int]:
        now = time.time()
        dq = self.bucket.setdefault(key, deque())
        # drop old
        while dq and (now - dq[0]) > self.window:
            dq.popleft()
        if len(dq) < self.limit:
            dq.append(now)
            remaining = self.limit - len(dq)
            return True, remaining
        remaining = 0
        return False, remaining

# factory per-endpoint
limiters: Dict[str, SlidingWindowLimiter] = {}

def get_limiter(name: str, limit: int, window_seconds: int) -> SlidingWindowLimiter:
    key = f"{name}:{limit}:{window_seconds}"
    if key not in limiters:
        limiters[key] = SlidingWindowLimiter(limit, window_seconds)
    return limiters[key]
