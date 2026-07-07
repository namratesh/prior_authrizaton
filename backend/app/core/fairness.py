"""Real (not illustrative) cohort bucketing for the Admin Portal's Bias &
Fairness gauge, computed from fields that already exist on every case
(patient_dob, patient_zip) instead of a synthetic age/region dataset.

// DEMO-REAL: replaces AdminPortal.tsx's previous BIAS_GAUGE_DATA constant,
which was hardcoded and explicitly marked DEMO-MOCKED. Cohorts below the
MIN_COHORT_SIZE sample threshold are dropped rather than shown with a
misleadingly precise rate — small-N cohorts are exactly what causes fairness
dashboards to be misread.
"""
from datetime import date, datetime

MIN_COHORT_SIZE = 3

AGE_BUCKETS = [
    (0, 64, "Under 65"),
    (65, 74, "Age 65-74"),
    (75, 84, "Age 75-84"),
    (85, 200, "Age 85+"),
]

# First-digit-of-ZIP -> US Census-style region, matching USPS ZIP prefix
# conventions. Coarse by design: fine enough to surface a real regional
# skew, coarse enough that a handful of demo cases still land in >1 bucket.
ZIP_PREFIX_REGION = {
    "0": "Northeast", "1": "Northeast",
    "2": "South", "3": "South",
    "4": "Midwest", "5": "Midwest", "6": "Midwest",
    "7": "South",
    "8": "West", "9": "West",
}


def bucket_age(patient_dob: str | None, as_of: date | None = None) -> str | None:
    if not patient_dob:
        return None
    try:
        dob = datetime.fromisoformat(patient_dob).date()
    except ValueError:
        return None
    today = as_of or date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    for lo, hi, label in AGE_BUCKETS:
        if lo <= age <= hi:
            return label
    return None


def bucket_region(patient_zip: str | None) -> str | None:
    if not patient_zip:
        return None
    digits = "".join(c for c in patient_zip if c.isdigit())
    if not digits:
        return None
    return ZIP_PREFIX_REGION.get(digits[0])


def compute_fairness_cohorts(rows: list[dict]) -> list[dict]:
    """rows: [{"patient_dob", "patient_zip", "outcome_is_denied": bool}, ...]
    for finalized cases only. Returns cohorts with >= MIN_COHORT_SIZE cases,
    each: {"cohort": str, "total": int, "approval_rate": float}."""
    buckets: dict[str, list[bool]] = {}
    for row in rows:
        for label in (bucket_age(row.get("patient_dob")), bucket_region(row.get("patient_zip"))):
            if label:
                buckets.setdefault(label, []).append(not row.get("outcome_is_denied", False))

    cohorts = []
    for label, outcomes in buckets.items():
        if len(outcomes) < MIN_COHORT_SIZE:
            continue
        cohorts.append(
            {
                "cohort": label,
                "total": len(outcomes),
                "approval_rate": round(sum(outcomes) / len(outcomes), 4),
            }
        )
    return sorted(cohorts, key=lambda c: c["cohort"])
