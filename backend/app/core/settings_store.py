"""Admin-tunable thresholds, backed by the single-row `admin_settings` table.

// DEMO-REAL: replaces the hardcoded SLA_WINDOW / EXPEDITE_WINDOW /
INTAKE_CONFIDENCE_THRESHOLD constants that used to live in supervisor.py and
peer_review_agent.py — those modules now call get_settings(db) at the point
of use instead of reading module-level constants, so an Admin Portal change
takes effect on the next case without a redeploy.
"""
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

DEFAULT_SLA_HOURS = 48.0
DEFAULT_EXPEDITE_HOURS = 2.0
DEFAULT_CONFIDENCE_THRESHOLD = 0.85
DEFAULT_OVERCHARGE_THRESHOLD_PERCENT = 20.0
DEFAULT_AGENTS_ENABLED = {"cost": True, "rag": True, "alternative": True}


@dataclass
class Settings:
    sla_hours: float
    expedite_hours: float
    confidence_threshold: float
    overcharge_threshold_percent: float
    agents_enabled: dict


def get_settings(db: Session) -> Settings:
    row = db.execute(
        text(
            "SELECT sla_hours, expedite_hours, confidence_threshold, "
            "overcharge_threshold_percent, agents_enabled "
            "FROM admin_settings WHERE id = 1"
        )
    ).mappings().first()
    if row is None:
        return Settings(
            sla_hours=DEFAULT_SLA_HOURS,
            expedite_hours=DEFAULT_EXPEDITE_HOURS,
            confidence_threshold=DEFAULT_CONFIDENCE_THRESHOLD,
            overcharge_threshold_percent=DEFAULT_OVERCHARGE_THRESHOLD_PERCENT,
            agents_enabled=dict(DEFAULT_AGENTS_ENABLED),
        )
    return Settings(
        sla_hours=row["sla_hours"],
        expedite_hours=row["expedite_hours"],
        confidence_threshold=row["confidence_threshold"],
        overcharge_threshold_percent=row["overcharge_threshold_percent"],
        agents_enabled=row["agents_enabled"],
    )


def _validate(updates: dict) -> None:
    if "confidence_threshold" in updates:
        v = updates["confidence_threshold"]
        if not (0.0 < v <= 1.0):
            raise ValueError("confidence_threshold must be in (0.0, 1.0]")
    if "sla_hours" in updates and not (updates["sla_hours"] > 0):
        raise ValueError("sla_hours must be positive")
    if "expedite_hours" in updates and not (updates["expedite_hours"] > 0):
        raise ValueError("expedite_hours must be positive")
    if "overcharge_threshold_percent" in updates and not (updates["overcharge_threshold_percent"] >= 0):
        raise ValueError("overcharge_threshold_percent must be non-negative")


def update_settings(db: Session, **fields) -> Settings:
    allowed = {
        "sla_hours",
        "expedite_hours",
        "confidence_threshold",
        "overcharge_threshold_percent",
        "agents_enabled",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_settings(db)
    _validate(updates)

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    params = dict(updates)
    if "agents_enabled" in params:
        import json

        params["agents_enabled"] = json.dumps(params["agents_enabled"])
    db.execute(text(f"UPDATE admin_settings SET {set_clause}, updated_at = now() WHERE id = 1"), params)
    db.commit()
    return get_settings(db)
