import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.fixtures import ensure_demo_users
from app.db.session import SessionLocal

# DEMO-REAL
app = FastAPI(title="AgenticPA")


@app.on_event("startup")
def _seed_demo_users():
    with SessionLocal() as db:
        ensure_demo_users(db)

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
