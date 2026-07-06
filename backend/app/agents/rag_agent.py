"""
AARP Medicare RAG agent.

// DEMO-REAL

Retrieval only: calls the hybrid (dense+sparse) Qdrant search built in
app/core/policy_search.py against the ingested EOC/SOB policy chunks. No LLM
call anywhere in this module (rule 1 in CLAUDE.md — decisions are RAG
retrieval + math + hardcoded rules, never a model). Flags POLICY_AMBIGUOUS
when the top match's dense cosine score falls below AMBIGUITY_THRESHOLD,
signaling the Supervisor/Peer-Review Auditor that the policy match is too
weak to support an automated decision.
"""
from app.core.policy_search import hybrid_search
from app.core.state import ClinicalPayload, PolicyPayload

AMBIGUITY_THRESHOLD = 0.70
STEP_THERAPY_KEYWORD = "step therapy"


def _build_query(clinical: ClinicalPayload) -> str:
    parts = []
    if clinical.diagnosis_summary:
        parts.append(clinical.diagnosis_summary)
    if clinical.icd10_codes:
        parts.append(" ".join(clinical.icd10_codes))
    if clinical.cpt_codes:
        parts.append(" ".join(clinical.cpt_codes))
    return " ".join(parts) or "prior authorization requirement"


def run_rag_agent(clinical: ClinicalPayload, top_k: int = 3) -> PolicyPayload:
    """Retrieve the top matching EOC/SOB policy chunks for a case's clinical payload.

    Sets policy_ambiguous=True (POLICY_AMBIGUOUS) when the top hit's score is
    below AMBIGUITY_THRESHOLD, or when there are no hits at all — the caller
    (Peer-Review Auditor / Supervisor) is responsible for turning that into a
    routing interrupt, not this function.
    """
    query = _build_query(clinical)
    results = hybrid_search(query, top_k=top_k)

    if not results:
        return PolicyPayload(policy_match_confidence=0.0, policy_ambiguous=True)

    top_score = results[0]["score"]
    is_ambiguous = top_score < AMBIGUITY_THRESHOLD

    eoc_citations = [f"{r['source']} p.{r['page']}" for r in results]
    matched_policy_clauses = [r["text"] for r in results]
    step_therapy_required = any(
        STEP_THERAPY_KEYWORD in r["text"].lower() for r in results
    )

    return PolicyPayload(
        eoc_citations=eoc_citations,
        matched_policy_clauses=matched_policy_clauses,
        step_therapy_required=step_therapy_required,
        policy_match_confidence=round(top_score, 4),
        policy_ambiguous=is_ambiguous,
    )


if __name__ == "__main__":
    import sys

    clinical = ClinicalPayload(
        diagnosis_summary=" ".join(sys.argv[1:]) or "durable medical equipment coverage",
    )
    payload = run_rag_agent(clinical)
    print(payload.model_dump_json(indent=2))
