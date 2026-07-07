"""
FastAPI routes — the 5 endpoints specified in CLAUDE.md's API table.

// DEMO-REAL
"""
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.case_runner import resume_case, start_case
from app.core.feedback import record_correction
from app.core.supervisor import is_expedite
from app.db.session import get_db
from app.utils.case_number import format_case_number
from app.utils.pdf_text import extract_full_text

router = APIRouter(prefix="/api/v1")

# Uploaded PDFs are kept on disk (outside the 5-endpoint table in CLAUDE.md)
# purely so the Reviewer Portal's react-pdf viewer has real bytes to render —
# Intake only needs the extracted text, not the file itself.
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
def upload_case(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    query: str = Form(...),
    db: Session = Depends(get_db),
):
    """Upload a PA request PDF + the patient's claim query -> create a case,
    kick off the graph asynchronously, return case_id immediately for the
    Patient Timeline to start polling /status against. The query is required:
    Intake uses it (alongside the extracted document) to decide which
    downstream checks (routing.relevant_agents) are actually relevant to the
    claim, per graph.py's route_after_intake."""
    if not query or not query.strip():
        raise HTTPException(400, "A claim query describing what you're requesting is required")
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF uploads are supported")

    pdf_bytes = file.file.read()
    raw_text = extract_full_text(pdf_bytes)
    if not raw_text:
        raise HTTPException(400, "Could not extract any text from the uploaded PDF")

    case_id = str(uuid.uuid4())
    (UPLOAD_DIR / f"{case_id}.pdf").write_bytes(pdf_bytes)
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

    def _run():
        from app.db.session import SessionLocal

        with SessionLocal() as bg_db:
            start_case(bg_db, case_id, raw_text, query.strip())

    background_tasks.add_task(_run)
    return {"case_id": case_id}


@router.get("/status/{case_id}")
def get_status(case_id: str, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT case_number, created_at, current_phase, final_status, "
            "needs_human_review, clinical_payload, financial_payload, routing_payload "
            "FROM cases WHERE id = :id"
        ),
        {"id": case_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(404, "Case not found")

    clinical = row["clinical_payload"] or {}
    financial = row["financial_payload"] or {}
    routing = row["routing_payload"] or {}
    return {
        "case_id": case_id,
        "case_number": format_case_number(row["case_number"], row["created_at"]),
        "current_phase": row["current_phase"],
        "final_status": row["final_status"],
        "needs_human_review": row["needs_human_review"],
        "case_status": routing.get("case_status"),
        "interrupt_reason": routing.get("interrupt_reason"),
        "requested_service_description": clinical.get("requested_service_description"),
        "patient_query": clinical.get("patient_query"),
        # Cost Transparency Card: CMS-derived estimate only, not the final
        # adjudicated amount — available as soon as Cost Agent completes.
        "estimated_out_of_pocket": financial.get("cms_benchmark_rate"),
        "sla_deadline": routing.get("sla_deadline"),
        "is_expedite": is_expedite(_parse_dt(routing.get("sla_deadline"))),
    }


def _parse_dt(value):
    if not value:
        return None
    from datetime import datetime

    return datetime.fromisoformat(value)


@router.get("/review/{case_id}")
def get_review(case_id: str, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            "SELECT case_number, created_at, patient_name, current_phase, final_status, "
            "needs_human_review, clinical_payload, financial_payload, policy_payload, "
            "routing_payload FROM cases WHERE id = :id"
        ),
        {"id": case_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(404, "Case not found")

    audit_rows = db.execute(
        text(
            "SELECT agent_name, details, created_at FROM audit_logs "
            "WHERE case_id = :id ORDER BY created_at ASC"
        ),
        {"id": case_id},
    ).mappings().all()

    trace = [
        {
            "agent": r["agent_name"],
            **(json.loads(r["details"]) if isinstance(r["details"], str) else r["details"]),
            "at": str(r["created_at"]),
        }
        for r in audit_rows
    ]
    summarizer_entry = next((t for t in reversed(trace) if t["agent"] == "summarizer"), None)

    return {
        "case_id": case_id,
        "case_number": format_case_number(row["case_number"], row["created_at"]),
        "patient_name": row["patient_name"],
        "current_phase": row["current_phase"],
        "final_status": row["final_status"],
        "needs_human_review": row["needs_human_review"],
        "clinical": row["clinical_payload"],
        "financial": row["financial_payload"],
        "policy": row["policy_payload"],
        "routing": row["routing_payload"],
        "decision_letter": summarizer_entry.get("decision_letter") if summarizer_entry else None,
        "agent_trace": trace,
    }


@router.get("/review/{case_id}/pdf")
def get_review_pdf(case_id: str):
    """Serves the original uploaded PDF bytes for the Reviewer Portal's
    react-pdf viewer. Not one of CLAUDE.md's 5 core endpoints — added because
    the split-screen spec requires rendering the actual document, and Intake
    only persists its extracted text, not the file."""
    path = UPLOAD_DIR / f"{case_id}.pdf"
    if not path.exists():
        raise HTTPException(404, "PDF not found for this case")
    return Response(content=path.read_bytes(), media_type="application/pdf")


@router.post("/review/{case_id}/adjudicate")
def adjudicate(case_id: str, payload: dict, db: Session = Depends(get_db)):
    """Body: {"action": "approve"|"modify"|"deny"|"clarify"|"provider_responded",
    "reviewer_id": str, "diffs": {"clinical": {...}, "financial": {...}},
    "question": str (for clarify), "original_reason": str}
    """
    action = payload.get("action")
    if action not in {"approve", "modify", "deny", "clarify", "provider_responded"}:
        raise HTTPException(400, f"Unknown action {action!r}")

    row = db.execute(
        text("SELECT clinical_payload FROM cases WHERE id = :id"), {"id": case_id}
    ).mappings().first()
    if row is None:
        raise HTTPException(404, "Case not found")

    state = resume_case(db, case_id, payload)

    # Feedback loop: every diffed field on modify/deny becomes a
    # (icd10_family, cpt_family)-keyed correction for the next matching case.
    if action in {"modify", "deny"}:
        diffs = payload.get("diffs") or {}
        original_clinical = row["clinical_payload"] or {}
        for field, corrected_value in diffs.get("clinical", {}).items():
            record_correction(
                db,
                case_id=case_id,
                icd10_codes=state.clinical.icd10_codes,
                cpt_codes=state.clinical.cpt_codes,
                corrected_field=field,
                original_value=str(original_clinical.get(field)),
                corrected_value=str(corrected_value),
                reviewer_id=payload.get("reviewer_id"),
            )

    return {
        "case_id": case_id,
        "final_status": state.routing.final_status,
        "case_status": state.routing.case_status,
        "decision_letter": state.audit.decision_letter,
    }


@router.get("/admin/metrics")
def admin_metrics(db: Session = Depends(get_db)):
    leakage = db.execute(
        text(
            """
            SELECT COALESCE(SUM(
                GREATEST((financial_payload->>'billed_amount')::float
                         - (financial_payload->>'cms_benchmark_rate')::float, 0)
                + COALESCE((financial_payload->>'alternative_therapy_savings')::float, 0)
            ), 0)
            FROM cases
            WHERE financial_payload->>'cms_benchmark_rate' IS NOT NULL
            """
        )
    ).scalar()

    drift_rows = db.execute(
        text(
            """
            SELECT date(updated_at) AS day,
                   count(*) AS total,
                   count(*) FILTER (WHERE routing_payload->>'reviewer_decision' IN ('modify','deny')) AS overrides
            FROM cases
            WHERE final_status IS NOT NULL AND updated_at > now() - interval '7 days'
            GROUP BY date(updated_at)
            ORDER BY day ASC
            """
        )
    ).mappings().all()
    accuracy_drift = [
        {
            "date": str(r["day"]),
            "accuracy": round(1 - (r["overrides"] / r["total"]), 4) if r["total"] else None,
        }
        for r in drift_rows
    ]

    case_rows = db.execute(
        text(
            """
            SELECT c.id, c.case_number, c.created_at, c.current_phase, c.final_status,
                   c.needs_human_review, c.routing_payload->>'sla_deadline' AS sla_deadline,
                   c.clinical_payload->>'requested_service_description' AS requested_service_description,
                   (SELECT details FROM audit_logs a WHERE a.case_id = c.id
                    AND a.agent_name = 'peer_review_auditor' ORDER BY a.created_at DESC LIMIT 1) AS pr_details
            FROM cases c ORDER BY c.created_at DESC LIMIT 50
            """
        )
    ).mappings().all()
    cases = []
    for r in case_rows:
        details = r["pr_details"]
        if isinstance(details, str):
            details = json.loads(details)
        flags = (details or {}).get("hard_gate_flags", [])
        cases.append(
            {
                "case_id": r["id"],
                "case_number": format_case_number(r["case_number"], r["created_at"]),
                "current_phase": r["current_phase"],
                "final_status": r["final_status"],
                "needs_human_review": r["needs_human_review"],
                "sla_deadline": r["sla_deadline"],
                "requested_service_description": r["requested_service_description"],
                "flags": flags,
            }
        )

    return {
        "leakage_prevented": round(leakage, 2),
        "accuracy_drift": accuracy_drift,
        "cases": cases,
    }
