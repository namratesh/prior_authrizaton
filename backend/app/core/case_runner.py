"""
Bridges LangGraph state <-> the `cases`/`audit_logs` Postgres tables.

// DEMO-REAL

The graph itself only persists via the PostgresSaver checkpointer (keyed by
thread_id=case_id) — that's enough to resume an interrupt, but it isn't a
queryable table the API/Admin dashboard can read cheaply. This module mirrors
every graph step's resulting state into `cases` (upsert on case_id, so
re-running is always safe) and appends any NEW agent_trace entries into the
insert-only `audit_logs` table.
"""
from datetime import datetime, timezone

from langgraph.types import Command
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.graph import get_compiled_graph
from app.core.state import AgenticPAState, ClinicalPayload


def _persist(db: Session, case_id: str, state: AgenticPAState, interrupted: bool) -> None:
    row = db.execute(text("SELECT id FROM cases WHERE id = :id"), {"id": case_id}).first()
    # A paused interrupt always means "awaiting review," regardless of
    # whichever phase last ran before the pause (current_phase is only
    # updated by intake/alternative/summarizer nodes, so it would otherwise
    # stay stuck on a stale value like "peer_review" for the entire time the
    # case is actually sitting in front of a reviewer).
    phase = "awaiting_review" if interrupted else (state.routing.current_phase or "intake")
    # final_status stays NULL until the case is truly decided (Approved/Denied)
    # — the frontend's "is this case already decided" check depends on that
    # distinction; a display label like "Needs Human Review" here would make
    # every interrupted case look permanently decided and disable the
    # Reviewer Portal's action buttons for good.
    params = {
        "id": case_id,
        "patient_name": state.clinical.patient_name,
        "current_phase": phase,
        "final_status": state.routing.final_status,
        "needs_human_review": state.routing.needs_human_review,
        "clinical_payload": state.clinical.model_dump_json(),
        "financial_payload": state.financial.model_dump_json(),
        "policy_payload": state.policy.model_dump_json(),
        "routing_payload": state.routing.model_dump_json(),
    }
    if row is None:
        db.execute(
            text(
                """
                INSERT INTO cases
                    (id, patient_name, current_phase, final_status, needs_human_review,
                     clinical_payload, financial_payload, policy_payload, routing_payload,
                     created_at, updated_at)
                VALUES
                    (:id, :patient_name, :current_phase, :final_status, :needs_human_review,
                     :clinical_payload, :financial_payload, :policy_payload, :routing_payload,
                     now(), now())
                """
            ),
            params,
        )
    else:
        db.execute(
            text(
                """
                UPDATE cases SET
                    patient_name = :patient_name,
                    current_phase = :current_phase,
                    final_status = :final_status,
                    needs_human_review = :needs_human_review,
                    clinical_payload = :clinical_payload,
                    financial_payload = :financial_payload,
                    policy_payload = :policy_payload,
                    routing_payload = :routing_payload,
                    updated_at = now()
                WHERE id = :id
                """
            ),
            params,
        )

    existing_count = db.execute(
        text("SELECT count(*) FROM audit_logs WHERE case_id = :id"), {"id": case_id}
    ).scalar()
    new_entries = state.audit.agent_trace[existing_count:]
    for entry in new_entries:
        db.execute(
            text(
                """
                INSERT INTO audit_logs (id, case_id, agent_name, action, details, created_at)
                VALUES (gen_random_uuid()::text, :case_id, :agent_name, :action, :details, now())
                """
            ),
            {
                "case_id": case_id,
                "agent_name": entry.get("agent", "unknown"),
                "action": "trace",
                "details": _json_safe(entry),
            },
        )
    db.commit()


def _json_safe(entry: dict) -> str:
    import json

    return json.dumps(entry, default=str)


def start_case(db: Session, case_id: str, raw_document_text: str, patient_query: str) -> AgenticPAState:
    """Kick off a brand-new case through the graph up to its first pause
    (interrupt or completion). Idempotent: re-running with the same case_id
    resumes/re-reads the same LangGraph thread rather than double-processing."""
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": case_id}}
    init_state = AgenticPAState(
        clinical=ClinicalPayload(
            case_id=case_id, raw_document_text=raw_document_text, patient_query=patient_query
        )
    )
    result = graph.invoke(init_state, config=config)
    state = _result_to_state(result)
    _persist(db, case_id, state, interrupted="__interrupt__" in result)
    return state


def resume_case(db: Session, case_id: str, resume_payload: dict) -> AgenticPAState:
    """Resume a paused case (approve/modify/deny/clarify/provider_responded)."""
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": case_id}}
    result = graph.invoke(Command(resume=resume_payload), config=config)
    state = _result_to_state(result)
    _persist(db, case_id, state, interrupted="__interrupt__" in result)
    return state


def _result_to_state(result: dict) -> AgenticPAState:
    return AgenticPAState(
        clinical=result["clinical"],
        financial=result["financial"],
        policy=result["policy"],
        routing=result["routing"],
        audit=result["audit"],
    )
