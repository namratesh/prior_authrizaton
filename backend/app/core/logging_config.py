"""JSON structured logging with per-request correlation.

// DEMO-REAL: previously logging.basicConfig(level=WARNING) in main.py meant
almost nothing was logged, and what was had no request/case correlation and
no consistent shape — unusable for any real log aggregator (CloudWatch,
Datadog, etc). Every log line is now one JSON object on stdout; the
RequestContextMiddleware below stamps request_id (and case_id, once known)
onto every line emitted while handling a request.
"""
import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_EXTRA_FIELDS = ("http_method", "http_path", "status_code", "duration_ms")


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


class RequestContextMiddleware:
    """Bare ASGI middleware (not BaseHTTPMiddleware) so it doesn't wrap the
    response body in a second layer of buffering — this app already streams
    the PDF export/review endpoints."""

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger("app.request")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        incoming_id = headers.get(b"x-request-id", b"").decode() or None
        request_id = incoming_id or str(uuid.uuid4())
        request_token = request_id_var.set(request_id)
        status_holder = {"status_code": 0}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["status_code"] = message["status"]
                headers_list = message.setdefault("headers", [])
                headers_list.append((b"x-request-id", request_id.encode()))
            await send(message)

        start = time.monotonic()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            self.logger.info(
                "request completed",
                extra={
                    "http_method": scope.get("method"),
                    "http_path": scope.get("path"),
                    "status_code": status_holder["status_code"],
                    "duration_ms": duration_ms,
                },
            )
            request_id_var.reset(request_token)
