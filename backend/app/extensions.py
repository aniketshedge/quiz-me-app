from __future__ import annotations

import ipaddress

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def _client_ip_for_rate_limit() -> str:
    """
    Prefer Cloudflare's client IP header when present (origin is only reachable via tunnel),
    and fall back to direct remote address otherwise.
    """
    candidate = (request.headers.get("CF-Connecting-IP") or "").strip()
    if candidate:
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            # Ignore malformed header values and use socket address fallback.
            pass
    return get_remote_address() or "unknown"


limiter = Limiter(key_func=_client_ip_for_rate_limit, storage_uri="memory://")
