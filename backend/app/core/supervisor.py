"""
SLA-aware Supervisor helpers.

// DEMO-REAL: SLA deadline is a real, computed timestamp (not a display
fake); "expedite" is a real boolean comparison against it, evaluated fresh on
every read rather than cached, so the Reviewer Portal's pulsing badge always
reflects the true remaining time.

sla_hours/expedite_hours are admin-tunable (see settings_store.py) rather
than fixed constants — every caller with DB access reads
settings_store.get_settings(db) and passes its values through (including
routes.py's /status read). The defaults below exist only as a fallback for
call sites with genuinely no DB access, and mirror admin_settings' seeded
row.
"""
from datetime import datetime, timedelta, timezone

DEFAULT_SLA_HOURS = 48.0
DEFAULT_EXPEDITE_HOURS = 2.0


def compute_sla_deadline(submitted_at: datetime | None = None, sla_hours: float = DEFAULT_SLA_HOURS) -> datetime:
    base = submitted_at or datetime.now(timezone.utc)
    return base + timedelta(hours=sla_hours)


def is_expedite(
    sla_deadline: datetime | None,
    now: datetime | None = None,
    expedite_hours: float = DEFAULT_EXPEDITE_HOURS,
) -> bool:
    """True if within expedite_hours of the SLA deadline (or already past it)."""
    if sla_deadline is None:
        return False
    current = now or datetime.now(timezone.utc)
    if sla_deadline.tzinfo is None:
        sla_deadline = sla_deadline.replace(tzinfo=timezone.utc)
    return sla_deadline - current <= timedelta(hours=expedite_hours)
