"""HMAC verification and JWT utilities."""

import hashlib
import hmac
import time
from typing import Optional

import jwt

from app.core.config import get_settings


def verify_hmac(payload: bytes, signature: Optional[str], key: str) -> bool:
    """Verify HMAC-SHA512 signature of webhook payload (WAHA uses sha512)."""
    if not signature or not key:
        return False

    expected = hmac.new(key.encode(), payload, hashlib.sha512).hexdigest()

    # Support both raw hex and "sha512=hex" format
    if signature.startswith("sha512="):
        signature = signature[7:]

    return hmac.compare_digest(expected, signature)


def create_jwt_token(subject: str, expires_in: int = 86400) -> str:
    """Create a JWT token."""
    settings = get_settings()
    payload = {
        "sub": subject,
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_jwt_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token. Returns payload or None."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
