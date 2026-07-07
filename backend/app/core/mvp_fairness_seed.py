"""
Seeds a batch of synthetic finalized cases so the Admin Portal's Bias &
Fairness Gauge (`backend/app/core/fairness.py`), accuracy-drift chart, and
leakage tile all have enough real rows to render on a brand-new machine —
instead of showing "not enough data yet" until someone manually runs 20+
cases through the live pipeline.

// MVP-MOCKED: unlike `scripts/seed_hero_cases.py`, these rows are inserted
directly into `cases` (bypassing the LangGraph pipeline entirely) — there is
no LLM extraction/adjudication behind them, just hand-authored clinical/
financial payloads. This is disclosed via `patient_name` ("MVP Patient NN")
so they're never mistaken for real or hero-case data in the UI.

The age/region split is deliberately skewed (90% -> 80% -> 60% -> 40%
approval as age bucket increases) so the fairness gauge actually has a
disparity worth looking at on a fresh machine, rather than four flat bars.

Idempotent: every row uses a deterministic uuid5 id and the insert is
`ON CONFLICT (id) DO NOTHING`, so re-running on every startup never
duplicates rows or fights with the `case_number` identity sequence.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

NAMESPACE = uuid.UUID("87654321-4321-8765-4321-876543218765")

# (icd10, cpt, service description, base billed amount)
SERVICE_CATALOG = [
    ("J45.909", "31626", "Diagnostic bronchoscopy with fiducial marker placement", 900.0),
    ("E11.9", "0446T", "Implantable continuous glucose sensor insertion", 11500.0),
    ("I10", "93784", "Ambulatory blood pressure monitoring", 65.0),
    ("M17.9", "27447", "Total knee arthroplasty", 8200.0),
    ("M54.5", "72148", "Lumbar spine MRI without contrast", 1450.0),
    ("N18.3", "90940", "Hemodialysis vascular access flow study", 340.0),
]

# region -> representative ZIPs (first digit drives bucket_region in fairness.py)
REGION_ZIPS = {
    "Northeast": ["02138", "10001", "19104", "07302"],
    "South": ["30301", "33101", "77001", "20001"],
    "Midwest": ["60601", "48201", "55401", "63101"],
    "West": ["90210", "94105", "85001", "98101"],
}
REGIONS = list(REGION_ZIPS.keys())

# age bucket label -> (representative age to encode in patient_dob, denied local-indices out of 10)
AGE_BUCKETS = [
    ("Under 65", 52, {5}),
    ("Age 65-74", 69, {2, 7}),
    ("Age 75-84", 79, {1, 4, 6, 9}),
    ("Age 85+", 88, {0, 1, 3, 4, 6, 8}),
]

CASES_PER_BUCKET = 10


def _dob_for_age(age: int, today: date) -> str:
    return date(today.year - age, 6, 15).isoformat()


def _case_id(i: int) -> str:
    return str(uuid.uuid5(NAMESPACE, f"MVP-FAIRNESS-{i}"))


def ensure_mvp_fairness_cases(db: Session) -> None:
    marker_id = _case_id(0)
    already_seeded = db.execute(
        text("SELECT 1 FROM cases WHERE id = :id"), {"id": marker_id}
    ).first()
    if already_seeded:
        return

    today = datetime.now(timezone.utc).date()
    i = 0
    for bucket_idx, (_, age, denied_local_indices) in enumerate(AGE_BUCKETS):
        dob = _dob_for_age(age, today)
        for local_idx in range(CASES_PER_BUCKET):
            region = REGIONS[i % len(REGIONS)]
            zip_code = REGION_ZIPS[region][i % len(REGION_ZIPS[region])]
            icd10, cpt, description, base_amount = SERVICE_CATALOG[i % len(SERVICE_CATALOG)]
            denied = local_idx in denied_local_indices

            billed_amount = base_amount * (1.15 if denied else 1.0)
            cms_benchmark_rate = base_amount * 0.85
            variance_amount = round(billed_amount - cms_benchmark_rate, 2)
            variance_percent = round(variance_amount / cms_benchmark_rate, 4) if cms_benchmark_rate else None
            is_overcharge = variance_percent is not None and variance_percent > 0.20

            case_id = _case_id(i)
            decided_at = datetime.now(timezone.utc) - timedelta(days=i % 7, hours=i)
            created_at = decided_at - timedelta(hours=6)

            clinical_payload = {
                "case_id": case_id,
                "patient_name": f"MVP Patient {i + 1:02d}",
                "patient_dob": dob,
                "patient_zip": zip_code,
                "icd10_codes": [icd10],
                "cpt_codes": [cpt],
                "diagnosis_summary": description,
                "prescribing_physician": "Dr. MVP Seed",
                "provider_npi": f"19{i:08d}",
                "requested_service_description": description,
                "billed_amount": billed_amount,
                "extraction_confidence": 0.95,
            }
            financial_payload = {
                "billed_amount": billed_amount,
                "cms_benchmark_rate": cms_benchmark_rate,
                "variance_amount": variance_amount,
                "variance_percent": variance_percent,
                "is_overcharge": is_overcharge,
            }
            routing_payload = {
                "current_phase": "complete",
                "needs_human_review": False,
                "final_status": "Denied" if denied else "Approved",
                "case_status": "closed",
            }

            db.execute(
                text(
                    """
                    INSERT INTO cases (
                        id, patient_name, current_phase, final_status, decided_at,
                        needs_human_review, clinical_payload, financial_payload,
                        policy_payload, routing_payload, created_at, updated_at
                    ) VALUES (
                        :id, :patient_name, 'complete', :final_status, :decided_at,
                        false, CAST(:clinical_payload AS JSONB), CAST(:financial_payload AS JSONB),
                        '{}', CAST(:routing_payload AS JSONB), :created_at, :decided_at
                    )
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "id": case_id,
                    "patient_name": clinical_payload["patient_name"],
                    "final_status": "Denied" if denied else "Approved",
                    "decided_at": decided_at,
                    "clinical_payload": _as_json(clinical_payload),
                    "financial_payload": _as_json(financial_payload),
                    "routing_payload": _as_json(routing_payload),
                    "created_at": created_at,
                },
            )

            db.execute(
                text(
                    """
                    INSERT INTO audit_logs (id, case_id, agent_name, action, details, created_at)
                    VALUES (:id, :case_id, 'peer_review_auditor', 'auto_decision', CAST(:details AS JSONB), :created_at)
                    """
                ),
                {
                    "id": str(uuid.uuid5(NAMESPACE, f"MVP-FAIRNESS-AUDIT-{i}")),
                    "case_id": case_id,
                    "details": _as_json(
                        {
                            "hard_gate_flags": ["FINANCIAL_EXCEPTION"] if is_overcharge else [],
                            "rationale": "MVP seed case — synthetic data for dashboard cohort "
                            "population, not adjudicated by the live pipeline.",
                        }
                    ),
                    "created_at": created_at,
                },
            )
            i += 1

    db.commit()


def _as_json(payload: dict) -> str:
    import json

    return json.dumps(payload)
