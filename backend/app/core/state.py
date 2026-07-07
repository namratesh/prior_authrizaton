"""
AgenticPAState — the single shared state object passed through the LangGraph.

// DEMO-REAL: this is the actual state schema used by the graph, not a mock.
"""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ClinicalPayload(BaseModel):
    """Extracted by the Intake agent (LLM extraction only, no decisions)."""

    case_id: Optional[str] = None
    patient_name: Optional[str] = None
    patient_dob: Optional[str] = None
    patient_zip: Optional[str] = None
    icd10_codes: list[str] = Field(default_factory=list)
    cpt_codes: list[str] = Field(default_factory=list)
    diagnosis_summary: Optional[str] = None
    prescribing_physician: Optional[str] = None
    provider_npi: Optional[str] = None
    requested_service_description: Optional[str] = None
    billed_amount: Optional[float] = None
    extraction_confidence: Optional[float] = None
    raw_document_text: Optional[str] = None
    few_shot_corrections_used: list[str] = Field(default_factory=list)
    patient_query: Optional[str] = None


class FinancialPayload(BaseModel):
    """Populated by the Cost Intelligence & Benchmarking agent (math + rules)."""

    billed_amount: Optional[float] = None
    cms_benchmark_rate: Optional[float] = None
    variance_amount: Optional[float] = None
    variance_percent: Optional[float] = None
    is_overcharge: Optional[bool] = None
    alternative_therapy_suggestion: Optional[str] = None
    alternative_therapy_savings: Optional[float] = None


class PolicyPayload(BaseModel):
    """Populated by the AARP Medicare RAG agent (retrieval, no generation of decisions)."""

    eoc_citations: list[str] = Field(default_factory=list)
    matched_policy_clauses: list[str] = Field(default_factory=list)
    step_therapy_required: Optional[bool] = None
    step_therapy_timeline: list[str] = Field(default_factory=list)
    policy_match_confidence: Optional[float] = None
    policy_ambiguous: Optional[bool] = None


class RoutingPayload(BaseModel):
    """Drives graph edges/interrupts. Owned by the Supervisor + Peer-Review Auditor."""

    current_phase: Optional[str] = None
    needs_human_review: bool = False
    interrupt_reason: Optional[str] = None
    reviewer_id: Optional[str] = None
    reviewer_decision: Optional[Literal["approve", "modify", "deny"]] = None
    reviewer_diffs: dict[str, Any] = Field(default_factory=dict)
    final_status: Optional[str] = None
    sla_deadline: Optional[datetime] = None
    case_status: Optional[str] = None
    # Derived from the patient's claim query by Intake (rule 1: LLM used for
    # classification/routing-hint only, never as the sole gate on a hard
    # threshold — see the fail-safe default of "run everything" below and the
    # relevant_agents-aware gating in peer_review_agent.evaluate_hard_gates).
    relevant_agents: list[str] = Field(default_factory=lambda: ["cost", "rag", "alternative"])
    query_classification_reason: Optional[str] = None


class AuditPayload(BaseModel):
    """Insert-only trace of what each agent did, for the Admin trace view."""

    agent_trace: list[dict[str, Any]] = Field(default_factory=list)
    feedback_corrections_used: list[str] = Field(default_factory=list)
    decision_letter: Optional[str] = None
    fhir_stub: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AgenticPAState(BaseModel):
    """Top-level state passed between every LangGraph node."""

    clinical: ClinicalPayload = Field(default_factory=ClinicalPayload)
    financial: FinancialPayload = Field(default_factory=FinancialPayload)
    policy: PolicyPayload = Field(default_factory=PolicyPayload)
    routing: RoutingPayload = Field(default_factory=RoutingPayload)
    audit: AuditPayload = Field(default_factory=AuditPayload)
