import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import router
from app.core.fixtures import ensure_demo_users
from app.core.rate_limit import limiter
from app.db.session import SessionLocal
from app.utils.policy_ingest import ensure_policies_ingested

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
    count = ensure_policies_ingested()
    if count:
        print(f"Ingested {count} chunks into aarp_policies")

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
