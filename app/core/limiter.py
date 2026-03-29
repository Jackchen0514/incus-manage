"""
Rate limiter setup using slowapi.
Key function: limit by authenticated username when token present, else by IP.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def _get_limit_key(request: Request) -> str:
    """
    Use authenticated username as the rate-limit key when a valid
    Authorization header is present, otherwise fall back to client IP.
    This means each user has their own quota rather than sharing one per IP
    (useful behind NAT/proxies).
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[len("Bearer "):].strip()
        try:
            from app.core.security import decode_token
            payload = decode_token(token)
            if payload and payload.get("sub"):
                return f"user:{payload['sub']}"
        except Exception:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_get_limit_key, default_limits=[])
