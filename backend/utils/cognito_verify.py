# backend/utils/cognito_verify.py
import os
import time
from typing import Optional, Dict, Any

import httpx
from jose import jwt
from fastapi import HTTPException, status
from dotenv import load_dotenv

# load .env early (so values are visible even on StatReload)
load_dotenv()

def _env_or_none(key: str) -> Optional[str]:
    val = os.getenv(key)
    return val.strip() if val else None

REGION = _env_or_none("COGNITO_REGION")
USER_POOL_ID = _env_or_none("COGNITO_USER_POOL_ID")
AUDIENCE = _env_or_none("COGNITO_AUDIENCE")

ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}" if REGION and USER_POOL_ID else None
JWKS_URL = f"{ISSUER}/.well-known/jwks.json" if ISSUER else None

_cached_jwks: Optional[Dict[str, Any]] = None
_cached_at: float = 0.0
_CACHE_TTL = 3600  # seconds

async def _get_jwks() -> Dict[str, Any]:
    """Fetch JWKS and cache for 1 hour."""
    global _cached_jwks, _cached_at
    now = time.time()
    if _cached_jwks and (now - _cached_at) < _CACHE_TTL:
        return _cached_jwks
    if not JWKS_URL:
        raise HTTPException(status_code=500, detail="COGNITO_REGION or USER_POOL_ID not set")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(JWKS_URL)
            r.raise_for_status()
            data = r.json()
            if "keys" not in data:
                raise ValueError("JWKS has no 'keys' field")
            _cached_jwks = data
            _cached_at = now
            return _cached_jwks
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load JWKS from Cognito: {e}"
        )

async def verify_bearer(token: str) -> Dict[str, Any]:
    """Verify a Cognito ID token (signature, issuer, audience, token_use)."""
    if not REGION or not USER_POOL_ID or not AUDIENCE:
        raise HTTPException(status_code=500, detail="Cognito environment variables missing")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        alg = header.get("alg")
        if not kid or not alg:
            raise HTTPException(status_code=401, detail="Invalid token header")

        jwks = await _get_jwks()
        key = next((k for k in jwks["keys"] if k.get("kid") == kid), None)
        if not key:
            raise HTTPException(status_code=401, detail="Signing key not found in JWKS")

        claims = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"verify_aud": True, "verify_iss": True, "verify_at_hash": False},
        )

        if claims.get("token_use") != "id":
            raise HTTPException(status_code=401, detail="Expected ID token")

        return claims
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {e}")
