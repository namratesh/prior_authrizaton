"""
LangGraph wiring for AgenticPA.

// DEMO-REAL

Graph shape:

    intake --[query-routed]--> cost   --\\
                          \\--> rag    ---+--> alternative --> peer_review --> [conditional] --> human_review --> summarizer --> END
                                                                                      |                 ^  |
                                                                                      |                 |  | (still awaiting: clarify/
                                                                                      +-----------------+  |  provider_responded loops
                                                                                (needs_human_review=False)  |  back to itself)
                                                                                        goes straight to    |
                                                                                        summarizer          v
                                                                                                    (approve/modify/deny:
                                                                                                     final_status set, falls
                                                                                                     through to summarizer)

`intake --[query-routed]-->` (route_after_intake): the patient's claim query
(ClinicalPayload.patient_query) is classified by Intake's LLM call into
routing.relevant_agents — a subset of {cost, rag, alternative} — so a case
that doesn't ask a cost question skips the Cost agent, etc. This is a routing
HINT only, never a hard gate (CLAUDE.md rule 1): on any classification
failure it fails safe to ALL_AGENTS (run everything), and
peer_review_agent.evaluate_hard_gates only evaluates FINANCIAL_EXCEPTION/
RATE_UNAVAILABLE/POLICY_AMBIGUOUS for checks that actually ran.

`human_review` is a REAL LangGraph interrupt (langgraph.types.interrupt), not
a UI-faked pause (CLAUDE.md rule 2): the graph literally cannot reach
`summarizer` while `needs_human_review=True` and no reviewer decision has
been recorded. State is checkpointed to Postgres via PostgresSaver, keyed by
case_id as the thread_id, so the pause survives across separate HTTP
requests/process restarts.

"Request Clarification" (CLAUDE.md's previously-undefined graph behavior):
handled entirely inside `human_review_node` as a self-loop — the reviewer's
free-text question is folded into `interrupt_reason` and the SAME interrupt
point re-fires, per the CLAUDE.md spec ("pauses at the same interrupt point,
not a new node"). The "Provider Responded" stub is DEMO-MOCKED: it clears the
"awaiting provider" framing and re-pauses at the same point for the reviewer,
with no real provider-facing notification system behind it.
"""
import os
from datetime import datetime, timezone

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import interrupt

from app.agents.alternative_agent import run_alternative_mapper
from app.agents.cost_agent import run_cost_agent
from app.agents.intake_agent import run_intake_agent
from app.agents.peer_review_agent import run_peer_review_agent
from app.agents.rag_agent import run_rag_agent
from app.agents.summarizer_agent import run_summarizer_agent
from app.core.state import AgenticPAState
from app.core.settings_store import get_settings
from app.core.supervisor import compute_sla_deadline
from app.db.session import SessionLocal

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://agentic_pa:agentic_pa@localhost:5432/agentic_pa"
)


def _trace(state: AgenticPAState, agent: str, **details) -> dict:
    entry = {"agent": agent, "at": datetime.now(timezone.utc).isoformat(), **details}
    return {"agent_trace": state.audit.agent_trace + [entry]}


def intake_node(state: AgenticPAState) -> dict:
    with SessionLocal() as db:
        clinical, relevant_agents, classification_reason = run_intake_agent(
            state.clinical.raw_document_text or "",
            db,
            case_id=state.clinical.case_id,
            patient_query=state.clinical.patient_query or "",
        )
        settings = get_settings(db)
    # Admin-disabled agents (Admin Portal's System Configuration panel) are
    # subtracted from Intake's query-driven relevant_agents — an agent that's
    # off can't be "relevant" regardless of what the query classifier said.
    relevant_agents = [a for a in relevant_agents if settings.agents_enabled.get(a, True)]
    routing = state.routing.model_copy(
        update={
            "current_phase": "cost_check",
            "sla_deadline": state.routing.sla_deadline or compute_sla_deadline(sla_hours=settings.sla_hours),
            "relevant_agents": relevant_agents,
            "query_classification_reason": classification_reason,
        }
    )
    audit = state.audit.model_copy(
        update=_trace(
            state,
            "intake",
            extraction_confidence=clinical.extraction_confidence,
            relevant_agents=relevant_agents,
            query_classification_reason=classification_reason,
        )
    )
    return {"clinical": clinical, "routing": routing, "audit": audit}


def route_after_intake(state: AgenticPAState) -> list[str]:
    """Query-driven fan-out: only run the checks Intake's classification
    marked relevant. Never a hard gate itself (rule 1) — worst case on a bad
    classification is ALL_AGENTS (see run_intake_agent's fail-safe), so this
    only ever skips work that was judged unnecessary, never a safety check."""
    targets = [t for t in ("cost", "rag") if t in state.routing.relevant_agents]
    return targets or ["alternative"]


def cost_node(state: AgenticPAState) -> dict:
    """No audit write here: cost and rag run in the same superstep (parallel
    fan-out from intake), and a Pydantic LastValue channel can only accept one
    write per step. Both nodes' trace entries are folded in by the join node
    (alternative_node) instead, which runs after both complete."""
    with SessionLocal() as db:
        cpt = state.clinical.cpt_codes[0] if state.clinical.cpt_codes else ""
        financial = run_cost_agent(
            billed_amount=state.clinical.billed_amount or 0.0,
            cpt=cpt,
            zip_code=state.clinical.patient_zip or "",
            db=db,
        )
    return {"financial": financial}


def rag_node(state: AgenticPAState) -> dict:
    policy = run_rag_agent(state.clinical)
    return {"policy": policy}


def alternative_node(state: AgenticPAState) -> dict:
    """Join node for the cost/rag fan-out — also where their audit trace
    entries get folded in, since only one node may write `audit` per step.
    cost/rag/alternative each only ran if Intake's query classification
    (route_after_intake / relevant_agents) marked them relevant; skipped
    checks are traced explicitly rather than silently showing None, so the
    Admin trace view and audit log stay honest about what actually ran."""
    relevant = state.routing.relevant_agents
    trace_updates = []
    if "cost" in relevant:
        trace_updates.append(
            {
                "agent": "cost_intelligence",
                "at": datetime.now(timezone.utc).isoformat(),
                "variance_percent": state.financial.variance_percent,
                "is_overcharge": state.financial.is_overcharge,
            }
        )
    else:
        trace_updates.append(
            {"agent": "cost_intelligence", "at": datetime.now(timezone.utc).isoformat(), "skipped": True}
        )

    if "rag" in relevant:
        trace_updates.append(
            {
                "agent": "aarp_rag",
                "at": datetime.now(timezone.utc).isoformat(),
                "policy_match_confidence": state.policy.policy_match_confidence,
                "policy_ambiguous": state.policy.policy_ambiguous,
            }
        )
    else:
        trace_updates.append(
            {"agent": "aarp_rag", "at": datetime.now(timezone.utc).isoformat(), "skipped": True}
        )

    financial = state.financial
    if "alternative" in relevant:
        with SessionLocal() as db:
            mapping = run_alternative_mapper(
                icd10_codes=state.clinical.icd10_codes,
                cpt_codes=state.clinical.cpt_codes,
                zip_code=state.clinical.patient_zip,
                db=db,
            )

        if mapping is None:
            trace_updates.append({"agent": "alternative_mapper", "fired": False})
        else:
            savings = None
            if mapping["alternative_cost"] is not None and state.financial.cms_benchmark_rate is not None:
                savings = round(state.financial.cms_benchmark_rate - mapping["alternative_cost"], 2)
            financial = state.financial.model_copy(
                update={
                    "alternative_therapy_suggestion": mapping["description"],
                    "alternative_therapy_savings": savings,
                }
            )
            trace_updates.append(
                {"agent": "alternative_mapper", "fired": True, "alternative_cpt": mapping["alternative_cpt"]}
            )
    else:
        trace_updates.append({"agent": "alternative_mapper", "fired": False, "skipped": True})

    audit = state.audit.model_copy(update={"agent_trace": state.audit.agent_trace + trace_updates})
    routing = state.routing.model_copy(update={"current_phase": "peer_review"})
    return {"financial": financial, "audit": audit, "routing": routing}


def peer_review_node(state: AgenticPAState) -> dict:
    with SessionLocal() as db:
        confidence_threshold = get_settings(db).confidence_threshold
    routing, trace_entry = run_peer_review_agent(state, confidence_threshold=confidence_threshold)
    audit = state.audit.model_copy(update=_trace(state, **trace_entry))
    return {"routing": routing, "audit": audit}


def route_after_peer_review(state: AgenticPAState) -> str:
    return "human_review" if state.routing.needs_human_review else "summarizer"


def human_review_node(state: AgenticPAState) -> dict:
    payload = interrupt(
        {
            "case_id": state.clinical.case_id,
            "interrupt_reason": state.routing.interrupt_reason,
        }
    )
    action = payload.get("action")

    if action == "clarify":
        routing = state.routing.model_copy(
            update={
                "interrupt_reason": f"Awaiting Provider Response: {payload.get('question', '')}",
                "case_status": "awaiting_provider_response",
            }
        )
        return {"routing": routing}

    if action == "provider_responded":
        routing = state.routing.model_copy(
            update={
                "interrupt_reason": payload.get("original_reason") or state.routing.interrupt_reason,
                "case_status": "needs_reviewer_decision",
            }
        )
        return {"routing": routing}

    # approve / modify / deny
    diffs = payload.get("diffs") or {}
    clinical = state.clinical.model_copy(update=diffs.get("clinical", {})) if diffs.get("clinical") else state.clinical
    financial = state.financial.model_copy(update=diffs.get("financial", {})) if diffs.get("financial") else state.financial

    final_status = "Denied" if action == "deny" else "Approved"
    reason = payload.get("reason")
    routing = state.routing.model_copy(
        update={
            "reviewer_id": payload.get("reviewer_id"),
            "reviewer_decision": action,
            "reviewer_diffs": diffs,
            "reviewer_reason": reason,
            "final_status": final_status,
            "needs_human_review": False,
            "case_status": final_status.lower(),
        }
    )
    audit = state.audit.model_copy(
        update=_trace(state, "reviewer", action=action, diffs=diffs, reason=reason)
    )
    return {"clinical": clinical, "financial": financial, "routing": routing, "audit": audit}


def route_after_human_review(state: AgenticPAState) -> str:
    return "human_review" if state.routing.final_status is None else "summarizer"


def summarizer_node(state: AgenticPAState) -> dict:
    result = run_summarizer_agent(state)
    routing = state.routing.model_copy(update={"current_phase": "complete"})
    # decision_letter/fhir_stub are included directly in the trace entry (not
    # just the top-level audit.decision_letter field) because case_runner
    # only persists agent_trace entries into the queryable audit_logs table —
    # the API layer reads the letter back out of the "summarizer" trace row.
    trace_update = _trace(
        state,
        "summarizer",
        flesch_score=result["flesch_score"],
        used_fallback=result["used_fallback"],
        decision_letter=result["decision_letter"],
        fhir_stub=result["fhir_stub"],
    )
    audit = state.audit.model_copy(
        update={
            **trace_update,
            "decision_letter": result["decision_letter"],
            "fhir_stub": result["fhir_stub"],
        }
    )
    return {"routing": routing, "audit": audit}


def build_graph():
    graph = StateGraph(AgenticPAState)
    graph.add_node("intake", intake_node)
    graph.add_node("cost", cost_node)
    graph.add_node("rag", rag_node)
    graph.add_node("alternative", alternative_node)
    graph.add_node("peer_review", peer_review_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("summarizer", summarizer_node)

    graph.add_edge(START, "intake")
    graph.add_conditional_edges(
        "intake", route_after_intake, {"cost": "cost", "rag": "rag", "alternative": "alternative"}
    )
    graph.add_edge("cost", "alternative")
    graph.add_edge("rag", "alternative")
    graph.add_edge("alternative", "peer_review")
    graph.add_conditional_edges(
        "peer_review", route_after_peer_review, {"human_review": "human_review", "summarizer": "summarizer"}
    )
    graph.add_conditional_edges(
        "human_review", route_after_human_review, {"human_review": "human_review", "summarizer": "summarizer"}
    )
    graph.add_edge("summarizer", END)
    return graph


_checkpointer_cm = None
_compiled_graph = None


def get_compiled_graph():
    """Compile once per process, backed by PostgresSaver so interrupts survive
    across separate API requests."""
    global _checkpointer_cm, _compiled_graph
    if _compiled_graph is None:
        _checkpointer_cm = PostgresSaver.from_conn_string(DATABASE_URL)
        checkpointer = _checkpointer_cm.__enter__()
        checkpointer.setup()
        # Explicitly allow our own state.py Pydantic models through msgpack —
        # future langgraph versions block unregistered types by default.
        checkpointer.serde = JsonPlusSerializer(
            allowed_msgpack_modules=[
                ("app.core.state", "ClinicalPayload"),
                ("app.core.state", "FinancialPayload"),
                ("app.core.state", "PolicyPayload"),
                ("app.core.state", "RoutingPayload"),
                ("app.core.state", "AuditPayload"),
                ("app.core.state", "AgenticPAState"),
            ]
        )
        _compiled_graph = build_graph().compile(checkpointer=checkpointer)
    return _compiled_graph
