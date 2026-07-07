"""
MVP user fixtures.

// MVP-MOCKED: Auth is hardcoded (no real login, per CLAUDE.md), but
feedback_corrections.reviewer_id has a real FK to `users` — so the two
hardcoded roles still need one real row each, or any reviewer adjudication
that records a correction (modify/deny) fails with a ForeignKeyViolation.
Idempotent: safe to call on every app startup.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

MVP_REVIEWER_ID = "reviewer-1"
MVP_REVIEWER_2_ID = "reviewer-2"
MVP_PATIENT_ID = "patient-1"


def ensure_mvp_users(db: Session) -> None:
    db.execute(
        text(
            """
            INSERT INTO users (id, name, role, created_at)
            VALUES (:id, :name, :role, now())
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": MVP_REVIEWER_ID, "name": "MVP Reviewer", "role": "reviewer"},
    )
    db.execute(
        text(
            """
            INSERT INTO users (id, name, role, created_at)
            VALUES (:id, :name, :role, now())
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": MVP_REVIEWER_2_ID, "name": "MVP Reviewer 2", "role": "reviewer"},
    )
    db.execute(
        text(
            """
            INSERT INTO users (id, name, role, created_at)
            VALUES (:id, :name, :role, now())
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": MVP_PATIENT_ID, "name": "Jane Doe", "role": "patient"},
    )
    db.commit()
