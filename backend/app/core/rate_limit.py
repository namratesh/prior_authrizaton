"""Shared slowapi Limiter instance, keyed by client IP.

// MVP-REAL: previously there was no rate limiting anywhere in the API —
/upload and /adjudicate are the two endpoints with real cost (LLM calls,
disk writes) and are the ones an unauthenticated MVP deployment is most
exposed on.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
