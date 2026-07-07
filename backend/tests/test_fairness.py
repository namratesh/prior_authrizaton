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
    assert cohorts["West"]["dimension"] == "region"


def test_compute_fairness_cohorts_buckets_by_provider_and_service():
    rows = [
        {"provider_npi": "1900000001", "requested_service_description": "Lumbar spine MRI", "outcome_is_denied": False},
        {"provider_npi": "1900000001", "requested_service_description": "Lumbar spine MRI", "outcome_is_denied": True},
        {"provider_npi": "1900000001", "requested_service_description": "Lumbar spine MRI", "outcome_is_denied": False},
    ]
    cohorts = {(c["dimension"], c["cohort"]): c for c in compute_fairness_cohorts(rows)}
    assert cohorts[("provider", "Provider 1900000001")]["total"] == 3
    assert cohorts[("service", "Lumbar spine MRI")]["approval_rate"] == round(2 / 3, 4)


def test_compute_fairness_cohorts_flags_significant_disparity():
    # Overall approval rate is 50% (5/10); "Age 85+" is denied every time on
    # n=5 — its Wilson interval should exclude 0.5, so it's flagged.
    rows = (
        [{"patient_dob": "1938-01-01", "outcome_is_denied": True}] * 5
        + [{"patient_dob": "1980-01-01", "outcome_is_denied": False}] * 5
    )
    cohorts = {c["cohort"]: c for c in compute_fairness_cohorts(rows)}
    assert cohorts["Age 85+"]["significant_disparity"] is True
    assert cohorts["Under 65"]["significant_disparity"] is True
    assert cohorts["Age 85+"]["ci_low"] >= 0.0 and cohorts["Age 85+"]["ci_high"] <= 1.0
