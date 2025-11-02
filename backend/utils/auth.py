# backend/utils/auth.py
import os
import json
import time
import logging
from typing import Optional, Dict, Any

import requests
from fastapi import HTTPException, Header

logger = logging.getLogger("finops-auth")
logger.setLevel(logging.INFO)

COGNITO_JWKS_URL = os.getenv("COGNITO_JWKS_URL")  # e.g. https://cognito-idp.<region>.amazonaws.com/<userPoolId>/.well-known/jwks.json
COGNITO_AUDIENCE = os.getenv("COGNITO_AUDIENCE")  # your app client id
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() in ("1", "true", "yes")

_jwks_cache: Dict[str, Any] = {}
_jwks_expiry: float = 0.0

def _get_jwks() -> Optional[Dict[str, Any]]:
    global _jwks_cache, _jwks_expiry
    if not COGNITO_JWKS_URL:
        return None
    now = time.time()
    if _jwks_cache and now < _jwks_expiry:
        return _jwks_cache
    try:
        # Accept both the issuer root and direct jwks url
        url = COGNITO_JWKS_URL
        if url.endswith("/.well-known/jwks.json"):
            jwks_url = url
        else:
            jwks_url = url.rstrip("/") + "/.well-known/jwks.json"
        r = requests.get(jwks_url, timeout=10)
        r.raise_for_status()
        _jwks_cache = r.json()
        _jwks_expiry = now + 3600
        return _jwks_cache
    except Exception as e:
        logger.warning("JWKS fetch failed: %s", e)
        return None

def cognito_optional_user(authorization: Optional[str] = Header(default=None)) -> Optional[Dict[str, Any]]:
    """
    If Cognito env vars are configured AND a Bearer token is provided,
    verify it. Otherwise:
      - if REQUIRE_AUTH=true and no valid token -> 401
      - if REQUIRE_AUTH=false -> allow anonymous
    """
    if not COGNITO_JWKS_URL:
        # auth disabled
        if REQUIRE_AUTH:
            raise HTTPException(status_code=401, detail="Auth required but COGNITO_JWKS_URL not set")
        return None

    if not authorization or not authorization.lower().startswith("bearer "):
        if REQUIRE_AUTH:
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        return None

    token = authorization.split(" ", 1)[1].strip()
    # light validation via python-jose if installed; otherwise accept (unless REQUIRE_AUTH)
    try:
        from jose import jwk, jwt
        from jose.utils import base64url_decode
    except Exception:
        logger.warning("python-jose not installed; skipping JWT verification")
        if REQUIRE_AUTH:
            raise HTTPException(status_code=401, detail="Server missing JWT verifier")
        return {"sub": "anonymous-unverified"}

    try:
        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid")
        jwks = _get_jwks()
        if not jwks:
            if REQUIRE_AUTH:
                raise HTTPException(status_code=401, detail="JWKS unavailable")
            return {"sub": "anonymous-unverified"}
        keys = jwks.get("keys", [])
        key = next((k for k in keys if k.get("kid") == kid), None)
        if not key:
            raise HTTPException(status_code=401, detail="Signing key not found")

        public_key = jwk.construct(key)
        message, encoded_sig = token.rsplit(".", 1)
        decoded_sig = base64url_decode(encoded_sig.encode("utf-8"))
        if not public_key.verify(message.encode("utf-8"), decoded_sig):
            raise HTTPException(status_code=401, detail="Invalid signature")

        claims = jwt.get_unverified_claims(token)
        now = int(time.time())
        if claims.get("exp") and now > int(claims["exp"]):
            raise HTTPException(status_code=401, detail="Token expired")
        if COGNITO_AUDIENCE and claims.get("aud") != COGNITO_AUDIENCE:
            raise HTTPException(status_code=401, detail="Invalid audience")

        return claims
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("JWT verify failed: %s", e)
        if REQUIRE_AUTH:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"sub": "anonymous-unverified"}
