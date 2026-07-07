"""Human-readable case number formatting — PA-<year>-<seq>.

// DEMO-REAL
"""
from datetime import datetime


def format_case_number(case_number: int, created_at: datetime) -> str:
    return f"PA-{created_at.year}-{case_number:04d}"
