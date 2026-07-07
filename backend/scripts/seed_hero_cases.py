"""
Seeds the 5 Hero Cases from CLAUDE.md through the real, wired LangGraph.

// MVP-REAL

Safe to re-run: each Hero Case gets a deterministic case_id (uuid5 of a fixed
namespace + "PA-00N"), and `start_case`/`case_runner._persist` upsert on that
id — re-running never double-inserts a case row or double-processes a case
that already reached a terminal phase.

Order matters: PA-005 is designed to demonstrate the feedback loop reusing a
correction recorded against PA-001, so PA-001 must run (and be adjudicated)
before PA-005.

The feedback-loop correction on PA-001 is captured via whichever path is live:
  - If PA-001 genuinely interrupts (e.g. POLICY_AMBIGUOUS — observed in
    testing against the real ingested EOC docs, even though CLAUDE.md's Hero
    Case table describes PA-001 as a clean auto-approve), the script resumes
    it with a real "modify" adjudication that corrects cpt_codes, exercising
    the actual reviewer path.
  - If PA-001 auto-approves with no interrupt (matching the Hero Case table's
    documented behavior), there's no reviewer pause to correct through —
    the script falls back to inserting the correction directly via
    core.feedback.record_correction, documented here as a seed fixture rather
    than a live reviewer action, so the PA-005 few-shot walkthrough still has
    something to inject regardless of which path fired this run.
"""
import sys
import uuid
from pathlib import Path

from fpdf import FPDF

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.case_runner import resume_case, start_case  # noqa: E402
from app.core.feedback import record_correction  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402

NAMESPACE = uuid.UUID("12345678-1234-5678-1234-567812345678")
UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

HERO_CASES = [
    {
        "key": "PA-001",
        "text": (
            "Prior Authorization Request\n\n"
            "Patient Name: Eleanor Vance\nDate of Birth: 1952-03-14\nPatient Zip: 90210\n\n"
            "Clinical Note:\nDiagnosis: J45.909 (asthma, unspecified, uncontrolled)\n"
            "Requested Service: Diagnostic bronchoscopy with placement of fiducial markers "
            "for planned radiation therapy targeting, medically necessary durable "
            "medical equipment adjacent procedure (CPT 31626)\n\n"
            "Billing Sheet:\nBilled Amount: $850.00\n"
            "Prescribing Physician: Dr. Miriam Okafor\nProvider NPI: 1002003000\n"
        ),
        "query": "Please check whether this bronchoscopy procedure is covered under my "
        "plan and whether the billed amount is reasonable.",
    },
    {
        "key": "PA-002",
        "text": (
            "Prior Authorization Request\n\n"
            "Patient Name: Robert Ellison\nDate of Birth: 1948-11-02\nPatient Zip: 36104\n\n"
            "Clinical Note:\nDiagnosis: E11.9 (type 2 diabetes mellitus without complications)\n"
            "Requested Service: Implantable continuous glucose sensor insertion (CPT 0446T)\n\n"
            "Billing Sheet:\nBilled Amount: $12000.00\n"
            "Prescribing Physician: Dr. Linda Cho\nProvider NPI: 1002003001\n"
        ),
        "query": "Is this glucose sensor insertion covered, and does the billed cost "
        "look right compared to what Medicare usually pays?",
    },
    {
        "key": "PA-003",
        "text": (
            "Prior Auth Req (handwritten intake, low legibility)\n\n"
            "Pt: T. Nguyen?  dob approx 1955  zip 10001\n\n"
            "note: htn (I10) pt needs monitor thing thats worn for bp check ambulatory "
            "cpt maybe 93784 not fully sure billing unclear\n\n"
            "billed: ~$60  npi: illegible  physician: Dr. R.?\n"
        ),
        "query": "Is this ambulatory blood pressure monitor covered by my plan?",
    },
    {
        "key": "PA-004",
        "text": (
            "Prior Authorization Request\n\n"
            "Patient Name: Harold Whitfield\nDate of Birth: 1945-06-20\nPatient Zip: 60601\n\n"
            "Clinical Note:\nDiagnosis: M17.9 (osteoarthritis of knee, unspecified)\n"
            "Requested Service: Total knee arthroplasty (CPT 27447)\n\n"
            "Billing Sheet:\nBilled Amount: $8000.00\n"
            "Prescribing Physician: Dr. Susan Ibarra\nProvider NPI: 1002003003\n"
        ),
        "query": "Please review whether this knee replacement is covered, whether the "
        "billed cost is fair, and whether there's a lower-cost alternative I should "
        "try first.",
    },
    {
        "key": "PA-005",
        "text": (
            "Prior Authorization Request\n\n"
            "Patient Name: Carol Jennings\nDate of Birth: 1958-09-09\nPatient Zip: 30301\n\n"
            "Clinical Note:\nDiagnosis: J45.909 (asthma, unspecified, uncontrolled)\n"
            "Requested Service: Diagnostic bronchoscopy with placement of fiducial markers "
            "for planned radiation therapy targeting (CPT 31626)\n\n"
            "Billing Sheet:\nBilled Amount: $900.00\n"
            "Prescribing Physician: Dr. Ahmed Hassan\nProvider NPI: 1002003004\n"
        ),
        "query": "Please check whether this bronchoscopy procedure is covered under my "
        "plan and whether the billed amount is reasonable.",
    },
]


def case_id_for(key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, key))


def write_pdf(case_id: str, text_content: str) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in text_content.split("\n"):
        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(UPLOAD_DIR / f"{case_id}.pdf"))


def get_case_row(db, case_id: str):
    return db.execute(
        text("SELECT current_phase, final_status FROM cases WHERE id = :id"), {"id": case_id}
    ).mappings().first()


def seed_case(db, key: str, raw_text: str, query: str) -> str:
    case_id = case_id_for(key)
    row = get_case_row(db, case_id)
    if row is not None and row["current_phase"] == "complete":
        print(f"[{key}] already complete ({case_id}) — skipping")
        return case_id

    write_pdf(case_id, raw_text)
    if row is None:
        db.execute(
            text(
                "INSERT INTO cases (id, current_phase, final_status, needs_human_review, "
                "clinical_payload, financial_payload, policy_payload, routing_payload, "
                "created_at, updated_at) "
                "VALUES (:id, 'intake', NULL, false, '{}', '{}', '{}', '{}', now(), now())"
            ),
            {"id": case_id},
        )
        db.commit()

    state = start_case(db, case_id, raw_text, query)
    print(f"[{key}] {case_id}: phase={state.routing.current_phase} "
          f"needs_review={state.routing.needs_human_review} "
          f"reason={state.routing.interrupt_reason}")
    return case_id


def ensure_pa001_correction(db, pa001_case_id: str) -> None:
    row = db.execute(
        text("SELECT routing_payload, clinical_payload FROM cases WHERE id = :id"),
        {"id": pa001_case_id},
    ).mappings().first()
    routing = row["routing_payload"] or {}
    clinical = row["clinical_payload"] or {}

    if routing.get("needs_human_review") and routing.get("final_status") is None:
        print("[PA-001] interrupted — resuming with a real reviewer 'modify' correction")
        resume_case(
            db,
            pa001_case_id,
            {
                "action": "modify",
                "reviewer_id": "reviewer-1",
                "diffs": {"clinical": {"cpt_codes": ["31626"]}},
            },
        )
        record_correction(
            db,
            case_id=pa001_case_id,
            icd10_codes=clinical.get("icd10_codes") or ["J45.909"],
            cpt_codes=["31626"],
            corrected_field="cpt_codes",
            original_value=str(clinical.get("cpt_codes")),
            corrected_value="['31626']",
            reviewer_id="reviewer-1",
        )
    else:
        print("[PA-001] auto-approved with no interrupt — recording a seed-fixture "
              "correction directly (documented in this script's docstring)")
        record_correction(
            db,
            case_id=pa001_case_id,
            icd10_codes=clinical.get("icd10_codes") or ["J45.909"],
            cpt_codes=["31626"],
            corrected_field="cpt_codes",
            original_value=str(clinical.get("cpt_codes")),
            corrected_value="['31626']",
            reviewer_id="reviewer-1",
        )


def main():
    from app.core.fixtures import ensure_mvp_users

    with SessionLocal() as db:
        ensure_mvp_users(db)

        pa001_id = seed_case(db, "PA-001", HERO_CASES[0]["text"], HERO_CASES[0]["query"])
        ensure_pa001_correction(db, pa001_id)

        for case in HERO_CASES[1:]:
            seed_case(db, case["key"], case["text"], case["query"])


if __name__ == "__main__":
    main()
