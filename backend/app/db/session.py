"""
Engine + session factory.

// MVP-REAL
"""
import os
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://agentic_pa:agentic_pa@localhost:5432/agentic_pa"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
