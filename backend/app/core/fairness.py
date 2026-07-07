"""Real (not illustrative) cohort bucketing for the Admin Portal's Bias &
Fairness gauge, computed from fields that already exist on every case
(patient_dob, patient_zip, provider_npi, requested_service_description)
instead of a synthetic age/region dataset.

// MVP-REAL: replaces AdminPortal.tsx's previous BIAS_GAUGE_DATA constant,
which was hardcoded and explicitly marked MVP-MOCKED. Cohorts below the
MIN_COHORT_SIZE sample threshold are dropped rather than shown with a
misleadingly precise rate — small-N cohorts are exactly what causes fairness
dashboards to be misread.

Each cohort also carries a Wilson score interval and a `significant_disparity`
flag (its CI excludes the overall approval rate) so a gap like "60% vs 90%"
isn't asserted as real bias when it's actually just noise from a handful of
cases — the same small-N problem MIN_COHORT_SIZE guards against, just at the
comparison step instead of the display step.
"""
import math
from datetime import date, datetime

MIN_COHORT_SIZE = 3
CONFIDENCE_Z = 1.96  # ~95% two-sided normal z-score

AGE_BUCKETS = [
    (0, 64, "Under 65"),
    (65, 74, "Age 65-74"),
    (75, 84, "Age 75-84"),
    (85, 200, "Age 85+"),
]

# First-digit-of-ZIP -> US Census-style region, matching USPS ZIP prefix
# conventions. Coarse by design: fine enough to surface a real regional
# skew, coarse enough that a handful of MVP cases still land in >1 bucket.
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


def bucket_provider(provider_npi: str | None) -> str | None:
    if not provider_npi:
        return None
    return f"Provider {provider_npi}"


def bucket_service(requested_service_description: str | None) -> str | None:
    if not requested_service_description:
        return None
    return requested_service_description


DIMENSIONS = {
    "age": lambda row: bucket_age(row.get("patient_dob")),
    "region": lambda row: bucket_region(row.get("patient_zip")),
    "provider": lambda row: bucket_provider(row.get("provider_npi")),
    "service": lambda row: bucket_service(row.get("requested_service_description")),
}


def _wilson_interval(successes: int, n: int, z: float = CONFIDENCE_Z) -> tuple[float, float]:
    """95%-by-default Wilson score interval — safe at small n, unlike a
    normal-approximation interval which can go outside [0, 1]."""
    if n == 0:
        return (0.0, 0.0)
    phat = successes / n
    denom = 1 + z**2 / n
    center = phat + z**2 / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))
    lo = (center - margin) / denom
    hi = (center + margin) / denom
    return max(0.0, lo), min(1.0, hi)


def compute_fairness_cohorts(rows: list[dict]) -> list[dict]:
    """rows: [{"patient_dob", "patient_zip", "provider_npi",
    "requested_service_description", "outcome_is_denied": bool}, ...] for
    finalized cases only. Returns cohorts with >= MIN_COHORT_SIZE cases across
    four dimensions (age, region, provider, service), each:
    {"dimension": str, "cohort": str, "total": int, "approval_rate": float,
     "ci_low": float, "ci_high": float, "significant_disparity": bool}.

    significant_disparity is True when the cohort's own Wilson interval
    excludes the overall approval rate across all rows — i.e. the gap is
    unlikely to be sampling noise, not just "different from average"."""
    outcomes_all = [not row.get("outcome_is_denied", False) for row in rows]
    overall_rate = sum(outcomes_all) / len(outcomes_all) if outcomes_all else None

    buckets: dict[tuple[str, str], list[bool]] = {}
    for row in rows:
        outcome = not row.get("outcome_is_denied", False)
        for dimension, bucket_fn in DIMENSIONS.items():
            label = bucket_fn(row)
            if label:
                buckets.setdefault((dimension, label), []).append(outcome)

    cohorts = []
    for (dimension, label), outcomes in buckets.items():
        n = len(outcomes)
        if n < MIN_COHORT_SIZE:
            continue
        successes = sum(outcomes)
        rate = successes / n
        ci_low, ci_high = _wilson_interval(successes, n)
        cohorts.append(
            {
                "dimension": dimension,
                "cohort": label,
                "total": n,
                "approval_rate": round(rate, 4),
                "ci_low": round(ci_low, 4),
                "ci_high": round(ci_high, 4),
                "significant_disparity": (
                    overall_rate is not None and not (ci_low <= overall_rate <= ci_high)
                ),
            }
        )
    return sorted(cohorts, key=lambda c: (c["dimension"], c["cohort"]))
