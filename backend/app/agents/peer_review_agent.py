"""
Peer-Review Compliance Auditor.

// DEMO-REAL (deterministic hard-gate) + // DEMO-REAL (LLM rationale layer,
translation only — see rule 1 in CLAUDE.md)

Two layers, run in strict order:

1. Deterministic hard-gate (`evaluate_hard_gates`): pure rule evaluation over
   the four upstream agents' structured payloads. No LLM anywhere in this
   function. This is what actually sets `routing.needs_human_review` —
   unconditionally, before the LLM is ever invoked.

2. LLM rationale layer (`generate_rationale`): given the hard-gate's flags
   plus every upstream payload's full structured output, asks the LLM to
   write the Reviewer's Rationale Panel text and to name any *additional*
   soft escalation reasons the deterministic layer didn't catch. This layer
   can only ADD reasons/escalate further — `run_peer_review_agent` never lets
   its output clear a hard-gate flag that's already True (the LLM result is
   never consulted when computing the hard-gate boolean, only OR'd in
   afterward), and if the LLM call fails outright, hard-gate flags still win.

Hard-gate flags:
  - LOW_CONFIDENCE_EXTRACTION — Intake's extraction_confidence missing or
    below threshold.
  - FINANCIAL_EXCEPTION — Cost flagged is_overcharge=True.
  - RATE_UNAVAILABLE — Cost couldn't resolve a CMS benchmark rate at all
    (is_overcharge is None); per cost_agent.py, "rate unavailable" is a
    routing decision for the caller, made here.
  - POLICY_AMBIGUOUS — RAG's top policy match scored below its ambiguity
    threshold (or found nothing).

FINANCIAL_EXCEPTION/RATE_UNAVAILABLE and POLICY_AMBIGUOUS are only evaluated
when "cost"/"rag" are in routing.relevant_agents (Intake's query-driven
routing hint, graph.py's route_after_intake) — otherwise a case whose query
never asked a cost/policy question would always trip RATE_UNAVAILABLE just
because Cost/RAG never ran, defeating the point of skipping them.
"""
import json

from app.core.llm_client import generate_text
from app.core.state import AgenticPAState, RoutingPayload

DEFAULT_CONFIDENCE_THRESHOLD = 0.85

LOW_CONFIDENCE_EXTRACTION = "LOW_CONFIDENCE_EXTRACTION"
FINANCIAL_EXCEPTION = "FINANCIAL_EXCEPTION"
RATE_UNAVAILABLE = "RATE_UNAVAILABLE"
POLICY_AMBIGUOUS = "POLICY_AMBIGUOUS"

RATIONALE_SYSTEM_PROMPT = """You are drafting the Rationale Panel text shown to a human \
Prior Authorization reviewer. A separate deterministic system has ALREADY decided, \
independently of you, whether this case requires human review — you are not deciding \
that and cannot change it.

You will be given: the fired hard-gate flags (may be empty), and the full structured \
output of the Intake, Cost, RAG, and Financial payloads for this case.

Your job:
1. Write a short, specific rationale explaining WHY each fired flag applies, citing the \
   actual numbers, codes, and policy citations given to you (e.g. exact billed amount, \
   exact CMS benchmark rate, exact variance percent, exact EOC page/source, exact \
   confidence score). Never use generic language like "the cost seems high" when an \
   exact figure is available — always use the number.
2. Separately, list any ADDITIONAL soft escalation reasons you notice in the data that \
   the hard gates did not already cover (e.g. an unusual combination of facts). If none, \
   return an empty list. Never contradict or claim a fired flag did not fire.

Respond with ONLY a JSON object, no prose outside it, no markdown fences:
{"rationale": "<string>", "additional_escalation_reasons": ["<string>", ...]}
"""


def evaluate_hard_gates(
    state: AgenticPAState, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> list[str]:
    """Pure rule evaluation. Returns the list of hard-gate flags that fired (may be empty)."""
    flags: list[str] = []

    confidence = state.clinical.extraction_confidence
    if confidence is None or confidence < confidence_threshold:
        flags.append(LOW_CONFIDENCE_EXTRACTION)

    relevant_agents = state.routing.relevant_agents
    if "cost" in relevant_agents:
        if state.financial.is_overcharge is True:
            flags.append(FINANCIAL_EXCEPTION)
        elif state.financial.is_overcharge is None:
            flags.append(RATE_UNAVAILABLE)

    if "rag" in relevant_agents and state.policy.policy_ambiguous is True:
        flags.append(POLICY_AMBIGUOUS)

    return flags


def generate_rationale(state: AgenticPAState, hard_gate_flags: list[str]) -> dict:
    """LLM translation layer: structured payloads -> human-readable rationale.

    Never called to decide needs_human_review — only to explain/expand on a
    decision already made by evaluate_hard_gates. Raises on API failure; the
    caller decides how to degrade.
    """
    user_payload = {
        "hard_gate_flags_already_fired": hard_gate_flags,
        "clinical": state.clinical.model_dump(),
        "financial": state.financial.model_dump(),
        "policy": state.policy.model_dump(),
    }
    text = generate_text(
        system_prompt=RATIONALE_SYSTEM_PROMPT,
        user_content=json.dumps(user_payload, default=str),
        max_tokens=2048,
    )
    return json.loads(_strip_markdown_fence(text))


def _strip_markdown_fence(text: str) -> str:
    """Some providers wrap JSON in ```json fences despite instructions not to."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        stripped = stripped.rsplit("```", 1)[0]
    return stripped.strip()


def run_peer_review_agent(
    state: AgenticPAState, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
) -> tuple[RoutingPayload, dict]:
    """Run both layers. Returns (updated RoutingPayload, audit trace entry)."""
    hard_gate_flags = evaluate_hard_gates(state, confidence_threshold=confidence_threshold)
    needs_human_review = bool(hard_gate_flags)

    try:
        llm_result = generate_rationale(state, hard_gate_flags)
        rationale = llm_result.get("rationale", "")
        additional_reasons = llm_result.get("additional_escalation_reasons") or []
    except Exception as exc:  # LLM unavailable/malformed — hard gates still stand.
        rationale = f"(LLM rationale unavailable: {exc})"
        additional_reasons = []

    # LLM can only add escalation, never suppress an already-fired hard gate.
    if additional_reasons:
        needs_human_review = True

    all_reasons = hard_gate_flags + additional_reasons
    routing = state.routing.model_copy(
        update={
            "needs_human_review": needs_human_review,
            "interrupt_reason": "; ".join(all_reasons) if all_reasons else None,
        }
    )

    trace_entry = {
        "agent": "peer_review_auditor",
        "hard_gate_flags": hard_gate_flags,
        "additional_escalation_reasons": additional_reasons,
        "rationale": rationale,
    }
    return routing, trace_entry
