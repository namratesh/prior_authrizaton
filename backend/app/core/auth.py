"""Shared-secret gate for /api/v1 — the whole router (including admin/*)
had zero auth: any client that could reach the container could pull the
audit export, flip admin settings, or claim reviewer queues.

// DEMO-REAL: not per-role auth (see app/db/models.py's User stub docstring
and frontend/src/store/auth.ts) — one shared secret checked via the
X-API-Key header, same key used for every role. If API_KEY isn't set in the
environment, the check is skipped (logged once) so local dev without a .env
still works.
"""
import logging
import os

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("API_KEY")
_warned = False


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    global _warned
    if not API_KEY:
        if not _warned:
            logger.warning("API_KEY is not set — /api/v1 is running without auth")
            _warned = True
        return
    if x_api_key != API_KEY:
        raise HTTPException(401, "Missing or invalid API key")
