"""
Dual-Output Summarizer.

// DEMO-REAL (LLM translation call + Flesch scoring)
// DEMO-MOCKED (FHIR stub — a structurally plausible Claim/ClaimResponse-shaped
dict, not a validated FHIR resource; real FHIR interop is out of scope for the
hackathon per CLAUDE.md)

LLM is used here for translation only (rule 1 in CLAUDE.md) — turning the
already-decided routing outcome + rationale into a patient-readable letter. It
never decides the outcome itself; `final_status`/`reviewer_decision` are
already fixed by the time this agent runs. Fail-safe: if the LLM call fails or
times out, or its letter scores below the Flesch target, a deterministic
template letter (guaranteed >60) is used instead — a Summarizer failure
degrades quality, it never blocks the graph or hides the decision.
"""
import textstat

from app.core.llm_client import generate_text
from app.core.state import AgenticPAState

FLESCH_TARGET = 60.0

LETTER_SYSTEM_PROMPT = """You are writing a plain-English Prior Authorization \
decision letter directly to a Medicare Advantage patient. Write at an elementary \
reading level (Flesch Reading Ease score above 60): short sentences, common words, \
no medical jargon or billing codes. Be warm and clear, not clinical or legalistic. \
State the decision, the reason in plain terms, and the patient's next step (e.g. \
what to do if they disagree). Address the patient by the real name given to you — \
never write a bracketed placeholder like "[Patient Name]". 3-5 short paragraphs. \
Respond with ONLY the letter text, no preamble, no markdown."""


def _template_letter(state: AgenticPAState) -> str:
    """Deterministic fallback letter — always scores well above the Flesch
    target since it uses short, fixed sentences."""
    status = state.routing.final_status or "under review"
    service = state.clinical.requested_service_description or "your requested service"
    lines = [
        f"Hello {state.clinical.patient_name or 'there'},",
        "",
        f"We have finished reviewing your request for {service}.",
        f"Your request is: {status}.",
        "",
        "A member of our team looked closely at your case before this decision was made.",
        "If you have questions, or you do not agree with this decision, you can ask to "
        "talk with a person on our team.",
        "",
        "Thank you,",
        "Your Care Team",
    ]
    return "\n".join(lines)


def _build_user_content(state: AgenticPAState) -> str:
    return (
        f"Patient name (address them by this name, do not use a placeholder): "
        f"{state.clinical.patient_name or 'the patient'}\n"
        f"Decision: {state.routing.final_status}\n"
        f"Requested service: {state.clinical.requested_service_description}\n"
        f"Diagnosis (plain terms needed): {state.clinical.diagnosis_summary}\n"
        f"Reviewer rationale (translate, do not quote codes/dollar figures verbatim "
        f"unless simplified): {state.routing.interrupt_reason or 'No issues found.'}\n"
    )


def _build_fhir_stub(state: AgenticPAState) -> dict:
    """// DEMO-MOCKED: illustrative FHIR-shaped structure, not schema-validated."""
    return {
        "resourceType": "ClaimResponse",
        "status": "active",
        "outcome": state.routing.final_status or "pending",
        "patient": {"display": state.clinical.patient_name},
        "item": [
            {
                "productOrService": {"coding": [{"code": cpt} for cpt in state.clinical.cpt_codes]},
                "diagnosis": [{"coding": [{"code": icd} for icd in state.clinical.icd10_codes]}],
            }
        ],
        "adjudication": {
            "billed_amount": state.financial.billed_amount,
            "cms_benchmark_rate": state.financial.cms_benchmark_rate,
        },
    }


def run_summarizer_agent(state: AgenticPAState) -> dict:
    """Returns {"decision_letter", "fhir_stub", "flesch_score", "used_fallback"}."""
    try:
        letter = generate_text(
            system_prompt=LETTER_SYSTEM_PROMPT,
            user_content=_build_user_content(state),
            max_tokens=512,
        )
        score = textstat.flesch_reading_ease(letter)
        if score < FLESCH_TARGET:
            raise ValueError(f"letter scored {score} < {FLESCH_TARGET} Flesch target")
        used_fallback = False
    except Exception:
        letter = _template_letter(state)
        score = textstat.flesch_reading_ease(letter)
        used_fallback = True

    return {
        "decision_letter": letter,
        "fhir_stub": _build_fhir_stub(state),
        "flesch_score": round(score, 1),
        "used_fallback": used_fallback,
    }
