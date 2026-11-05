"""Admin-key gate for state-changing API endpoints.

Read endpoints stay open — the price data is public. Endpoints that trigger
server-side scraping are gated behind ``ADMIN_API_KEY`` so an unauthenticated
caller cannot make the server do work (and potentially get its IP blocked or
burn proxy quota) on their behalf. When the key is not configured the gated
endpoints fail closed.
"""

from __future__ import annotations

import hmac
import os

ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "").strip()


def is_configured() -> bool:
    return bool(ADMIN_API_KEY)


def is_valid_admin_key(provided: str | None) -> bool:
    """Constant-time comparison; False when unconfigured or missing."""
    if not ADMIN_API_KEY or not provided:
        return False
    return hmac.compare_digest(provided, ADMIN_API_KEY)
