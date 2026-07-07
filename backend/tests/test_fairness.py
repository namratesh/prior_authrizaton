from datetime import date

from app.core.fairness import bucket_age, bucket_region, compute_fairness_cohorts


def test_bucket_age_buckets_by_year():
    as_of = date(2026, 7, 7)
    assert bucket_age("1955-01-01", as_of=as_of) == "Age 65-74"
    assert bucket_age("1945-01-01", as_of=as_of) == "Age 75-84"
    assert bucket_age("1930-01-01", as_of=as_of) == "Age 85+"
    assert bucket_age("1980-01-01", as_of=as_of) == "Under 65"


def test_bucket_age_handles_missing_or_malformed():
    assert bucket_age(None) is None
    assert bucket_age("not-a-date") is None


def test_bucket_region_maps_zip_prefix():
    assert bucket_region("90210") == "West"
    assert bucket_region("10001") == "Northeast"
    assert bucket_region("60601") == "Midwest"
    assert bucket_region(None) is None
    assert bucket_region("") is None


def test_compute_fairness_cohorts_drops_small_samples():
    rows = [
        {"patient_dob": "1955-01-01", "patient_zip": "90210", "outcome_is_denied": False},
        {"patient_dob": "1955-01-01", "patient_zip": "90210", "outcome_is_denied": True},
    ]
    # Only 2 cases share "Age 65-74"/"West" — below MIN_COHORT_SIZE of 3.
    assert compute_fairness_cohorts(rows) == []


def test_compute_fairness_cohorts_computes_real_approval_rate():
    rows = [
        {"patient_dob": "1955-01-01", "patient_zip": "90210", "outcome_is_denied": False},
        {"patient_dob": "1956-01-01", "patient_zip": "90211", "outcome_is_denied": False},
        {"patient_dob": "1957-01-01", "patient_zip": "90212", "outcome_is_denied": True},
    ]
    cohorts = {c["cohort"]: c for c in compute_fairness_cohorts(rows)}
    assert cohorts["West"]["total"] == 3
    assert cohorts["West"]["approval_rate"] == round(2 / 3, 4)
