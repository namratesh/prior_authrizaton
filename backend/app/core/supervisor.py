"""
SLA-aware Supervisor helpers.

// DEMO-REAL: SLA deadline is a real, computed timestamp (not a display
fake); "expedite" is a real boolean comparison against it, evaluated fresh on
every read rather than cached, so the Reviewer Portal's pulsing badge always
reflects the true remaining time.
"""
from datetime import datetime, timedelta, timezone

SLA_WINDOW = timedelta(hours=48)
EXPEDITE_WINDOW = timedelta(hours=2)


def compute_sla_deadline(submitted_at: datetime | None = None) -> datetime:
    base = submitted_at or datetime.now(timezone.utc)
    return base + SLA_WINDOW


def is_expedite(sla_deadline: datetime | None, now: datetime | None = None) -> bool:
    """True if within EXPEDITE_WINDOW of the SLA deadline (or already past it)."""
    if sla_deadline is None:
        return False
    current = now or datetime.now(timezone.utc)
    if sla_deadline.tzinfo is None:
        sla_deadline = sla_deadline.replace(tzinfo=timezone.utc)
    return sla_deadline - current <= EXPEDITE_WINDOW
