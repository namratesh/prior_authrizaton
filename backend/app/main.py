import logging
import os
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import router
from app.core.fixtures import ensure_demo_users
from app.core.rate_limit import limiter
from app.db.session import SessionLocal
from app.utils.policy_ingest import ensure_policies_ingested

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# DEMO-REAL
app = FastAPI(title="AgenticPA")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
def _seed_demo_users():
    with SessionLocal() as db:
        ensure_demo_users(db)


@app.on_event("startup")
def _seed_aarp_policies():
    # Fresh machines start with an empty Qdrant volume, so the aarp_policies
    # collection is otherwise never created/populated until someone manually
    # runs policy_ingest.py. This is a no-op once the collection has points.
    #
    # Runs in a background thread, not inline: embedding-model downloads +
    # encoding ~800 chunks can take well past the healthcheck's 50s budget,
    # which blocked /health and made the container (and, via depends_on, the
    # frontend) report unhealthy. A failure here (missing PDFs, Qdrant
    # hiccup) must degrade RAG search, not take the whole backend down.
    def _run():
        try:
            count = ensure_policies_ingested()
            if count:
                logger.info("Ingested %d chunks into aarp_policies", count)
        except Exception:
            logger.exception(
                "Failed to ensure aarp_policies are ingested; "
                "RAG policy search will return no results until this is resolved"
            )

    threading.Thread(target=_run, daemon=True).start()

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
