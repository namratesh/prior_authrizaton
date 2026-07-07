from datetime import datetime

from app.utils.case_number import format_case_number


def test_format_case_number_pads_and_uses_year():
    assert format_case_number(4, datetime(2026, 3, 1)) == "PA-2026-0004"


def test_format_case_number_handles_large_sequence():
    assert format_case_number(12345, datetime(2027, 1, 1)) == "PA-2027-12345"
