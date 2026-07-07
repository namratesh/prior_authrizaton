from datetime import datetime, timedelta, timezone

from app.core.supervisor import compute_sla_deadline, is_expedite


def test_compute_sla_deadline_uses_configured_hours():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    deadline = compute_sla_deadline(submitted_at=base, sla_hours=24)
    assert deadline == base + timedelta(hours=24)


def test_compute_sla_deadline_defaults_to_48_hours():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert compute_sla_deadline(submitted_at=base) == base + timedelta(hours=48)


def test_is_expedite_none_deadline_is_false():
    assert is_expedite(None) is False


def test_is_expedite_true_within_window():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    deadline = now + timedelta(hours=1)
    assert is_expedite(deadline, now=now, expedite_hours=2) is True


def test_is_expedite_false_outside_window():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    deadline = now + timedelta(hours=5)
    assert is_expedite(deadline, now=now, expedite_hours=2) is False


def test_is_expedite_true_once_past_deadline():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    deadline = now - timedelta(hours=1)
    assert is_expedite(deadline, now=now, expedite_hours=2) is True
