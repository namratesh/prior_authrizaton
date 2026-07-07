from app.agents.peer_review_agent import (
    FINANCIAL_EXCEPTION,
    LOW_CONFIDENCE_EXTRACTION,
    POLICY_AMBIGUOUS,
    RATE_UNAVAILABLE,
    evaluate_hard_gates,
)
from app.core.state import AgenticPAState, ClinicalPayload, FinancialPayload, PolicyPayload, RoutingPayload


def _state(**overrides) -> AgenticPAState:
    defaults = dict(
        clinical=ClinicalPayload(extraction_confidence=0.95),
        financial=FinancialPayload(is_overcharge=False),
        policy=PolicyPayload(policy_ambiguous=False),
        routing=RoutingPayload(relevant_agents=["cost", "rag", "alternative"]),
    )
    defaults.update(overrides)
    return AgenticPAState(**defaults)


def test_clean_case_fires_no_flags():
    assert evaluate_hard_gates(_state()) == []


def test_low_confidence_fires_below_threshold():
    state = _state(clinical=ClinicalPayload(extraction_confidence=0.5))
    assert LOW_CONFIDENCE_EXTRACTION in evaluate_hard_gates(state, confidence_threshold=0.85)


def test_low_confidence_respects_custom_threshold():
    state = _state(clinical=ClinicalPayload(extraction_confidence=0.5))
    assert LOW_CONFIDENCE_EXTRACTION not in evaluate_hard_gates(state, confidence_threshold=0.3)


def test_missing_confidence_fires_low_confidence():
    state = _state(clinical=ClinicalPayload(extraction_confidence=None))
    assert LOW_CONFIDENCE_EXTRACTION in evaluate_hard_gates(state)


def test_overcharge_fires_financial_exception_when_cost_relevant():
    state = _state(financial=FinancialPayload(is_overcharge=True))
    assert FINANCIAL_EXCEPTION in evaluate_hard_gates(state)


def test_missing_benchmark_rate_fires_rate_unavailable():
    state = _state(financial=FinancialPayload(is_overcharge=None))
    assert RATE_UNAVAILABLE in evaluate_hard_gates(state)


def test_cost_flags_skipped_when_cost_not_relevant():
    state = _state(
        financial=FinancialPayload(is_overcharge=None),
        routing=RoutingPayload(relevant_agents=["rag"]),
    )
    flags = evaluate_hard_gates(state)
    assert RATE_UNAVAILABLE not in flags
    assert FINANCIAL_EXCEPTION not in flags


def test_policy_ambiguous_fires_when_rag_relevant():
    state = _state(policy=PolicyPayload(policy_ambiguous=True))
    assert POLICY_AMBIGUOUS in evaluate_hard_gates(state)


def test_policy_ambiguous_skipped_when_rag_not_relevant():
    state = _state(
        policy=PolicyPayload(policy_ambiguous=True),
        routing=RoutingPayload(relevant_agents=["cost"]),
    )
    assert POLICY_AMBIGUOUS not in evaluate_hard_gates(state)
