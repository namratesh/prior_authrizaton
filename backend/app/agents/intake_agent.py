"""
Clinical Intake & Normalizer agent.

// DEMO-REAL (PDF text extraction + LLM extraction call)
// DEMO-REAL (few-shot injection from feedback_corrections — see core/feedback.py)

LLM is used here for extraction only (rule 1 in CLAUDE.md) — it reads the raw
PDF text and returns structured fields, but the resulting
extraction_confidence is what the Peer-Review Auditor's deterministic
LOW_CONFIDENCE_EXTRACTION hard-gate checks, not a decision this agent makes
itself. Fail-safe: if the LLM call fails, times out, or the confidence field
can't be parsed as a float, extraction_confidence is set to 0.0 (treated as
low-confidence, routed to human) rather than assumed high-confidence.
"""
import json

from sqlalchemy.orm import Session

from app.core.feedback import extract_candidate_icd10, get_few_shot_examples
from app.core.llm_client import generate_text
from app.core.state import ClinicalPayload

EXTRACTION_SYSTEM_PROMPT = """You are extracting structured fields from a Prior \
Authorization request document (clinical note + billing sheet) for a Medicare \
Advantage plan. You do not make any coverage or approval decision — you only \
extract what is written in the document.

Extract these fields exactly as they appear in the source text (do not invent \
values that aren't present):
- patient_name
- patient_dob (as written)
- patient_zip
- icd10_codes (list of strings, e.g. ["J45.909"])
- cpt_codes (list of strings, e.g. ["31626"])
- diagnosis_summary (one sentence, from the clinical note)
- prescribing_physician
- provider_npi
- requested_service_description
- billed_amount (number, no currency symbol)

Also return extraction_confidence: your own calibrated confidence (0.0-1.0) that \
every field above was read correctly and unambiguously from the source text. If a \
field is missing from the source, leave it null/empty and lower your confidence \
accordingly rather than guessing.

Also return field_confidence: a JSON object with your own calibrated confidence \
(0.0-1.0) for each of these six fields individually: cpt_codes, icd10_codes, \
billed_amount, patient_zip, provider_npi, requested_service_description. A field \
that's missing or ambiguous in the source should get a low score even if your \
overall extraction_confidence is high.

You will also be given the PATIENT'S CLAIM QUERY — their own words on what they're \
asking for. Use it, together with the extracted document, to decide which \
downstream checks are actually relevant to answering it:
- "cost": compare the billed amount to the CMS benchmark rate.
- "rag": check the plan's policy/coverage documents (EOC/SOB) for a match.
- "alternative": look for a lower-cost alternative therapy/procedure.
Return relevant_agents as a JSON list, any subset of ["cost", "rag", "alternative"]. \
This is only a routing hint, not a coverage decision — when the query is ambiguous \
or you're unsure whether a check applies, INCLUDE it rather than skip it; it is \
never safe to omit a check that might matter. Also return \
query_classification_reason: one short sentence explaining your inclusion/exclusion \
choices.

Respond with ONLY a JSON object, no prose outside it, no markdown fences:
{"patient_name": "...", "patient_dob": "...", "patient_zip": "...", \
"icd10_codes": [...], "cpt_codes": [...], "diagnosis_summary": "...", \
"prescribing_physician": "...", "provider_npi": "...", \
"requested_service_description": "...", "billed_amount": 0.0, \
"extraction_confidence": 0.0, \
"field_confidence": {"cpt_codes": 0.0, "icd10_codes": 0.0, "billed_amount": 0.0, \
"patient_zip": 0.0, "provider_npi": 0.0, "requested_service_description": 0.0}, \
"relevant_agents": ["cost", "rag", "alternative"], \
"query_classification_reason": "..."}
"""

FAIL_SAFE_CONFIDENCE = 0.0
# Fail-safe default: if query classification can't be computed (LLM failure or
# malformed reply), run every downstream check rather than silently skip one
# that might have mattered — mirrors the confidence fail-safe below.
ALL_AGENTS = ["cost", "rag", "alternative"]

FIELD_CONFIDENCE_KEYS = (
    "cpt_codes",
    "icd10_codes",
    "billed_amount",
    "patient_zip",
    "provider_npi",
    "requested_service_description",
)


def _parse_field_confidence(raw: object) -> dict[str, float]:
    """Fail-safe parse: keep only known keys with a valid float 0.0-1.0. Never
    fabricate a value for a key the LLM didn't return — the UI falls back to
    the overall extraction_confidence for any missing key."""
    if not isinstance(raw, dict):
        return {}
    result = {}
    for key in FIELD_CONFIDENCE_KEYS:
        if key not in raw:
            continue
        try:
            result[key] = max(0.0, min(1.0, float(raw[key])))
        except (TypeError, ValueError):
            continue
    return result


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        stripped = stripped.rsplit("```", 1)[0]
    return stripped.strip()


def _build_user_content(raw_document_text: str, few_shot: list[dict], patient_query: str) -> str:
    parts = [f"PATIENT'S CLAIM QUERY:\n{patient_query}", f"DOCUMENT TEXT:\n{raw_document_text}"]
    if few_shot:
        examples = "\n".join(
            f"- A prior case with the same ICD-10 family had its "
            f"'{ex['corrected_field']}' corrected from {ex['original_value']!r} "
            f"to {ex['corrected_value']!r} by a human reviewer."
            for ex in few_shot
        )
        parts.append(
            "REVIEWER FEEDBACK FROM SIMILAR PAST CASES (use this to avoid "
            f"repeating the same extraction mistake):\n{examples}"
        )
    return "\n\n".join(parts)


def run_intake_agent(
    raw_document_text: str,
    db: Session,
    case_id: str | None = None,
    patient_query: str = "",
) -> tuple[ClinicalPayload, list[str], str]:
    """Extract structured clinical fields from raw PA document text, and use
    the patient's claim query to decide which downstream checks are relevant.

    Fail-safe on any LLM failure (timeout, malformed JSON, provider error):
    returns extraction_confidence=0.0 (treated as low-confidence) and
    relevant_agents=ALL_AGENTS (run everything) rather than guessing — a
    skipped check can never be silently assumed safe.

    Returns (clinical_payload, relevant_agents, query_classification_reason).
    """
    candidate_icd10 = extract_candidate_icd10(raw_document_text)
    few_shot = get_few_shot_examples(db, candidate_icd10)
    user_content = _build_user_content(raw_document_text, few_shot, patient_query)

    try:
        raw_reply = generate_text(
            system_prompt=EXTRACTION_SYSTEM_PROMPT,
            user_content=user_content,
            max_tokens=1024,
        )
        parsed = json.loads(_strip_markdown_fence(raw_reply))
        confidence = float(parsed.get("extraction_confidence", FAIL_SAFE_CONFIDENCE))
    except Exception:
        # LLM unavailable/timed out/malformed reply -> treat as low-confidence,
        # never as high-confidence (CLAUDE.md reliability rule), and run every
        # downstream check rather than skip one based on a guess.
        clinical = ClinicalPayload(
            case_id=case_id,
            raw_document_text=raw_document_text,
            patient_query=patient_query,
            extraction_confidence=FAIL_SAFE_CONFIDENCE,
            few_shot_corrections_used=[ex["case_id"] for ex in few_shot],
        )
        return clinical, ALL_AGENTS, "Query classification unavailable — running full pipeline for safety."

    relevant_agents = [a for a in (parsed.get("relevant_agents") or ALL_AGENTS) if a in ALL_AGENTS]
    if not relevant_agents:
        relevant_agents = ALL_AGENTS
    # Deterministic safety net: the LLM's relevant_agents classification is a
    # routing hint and can be wrong-but-non-empty (the empty-list fail-safe
    # above never catches that). If the document itself carries the data a
    # check needs, force that check to run regardless of what the LLM
    # decided — a hard gate must never go dark just because a classifier
    # under-included a check.
    if parsed.get("billed_amount") is not None and "cost" not in relevant_agents:
        relevant_agents.append("cost")
    if (parsed.get("icd10_codes") or parsed.get("cpt_codes")) and "rag" not in relevant_agents:
        relevant_agents.append("rag")
    reason = parsed.get("query_classification_reason") or ""

    clinical = ClinicalPayload(
        case_id=case_id,
        patient_name=parsed.get("patient_name"),
        patient_dob=parsed.get("patient_dob"),
        patient_zip=parsed.get("patient_zip"),
        icd10_codes=parsed.get("icd10_codes") or [],
        cpt_codes=parsed.get("cpt_codes") or [],
        diagnosis_summary=parsed.get("diagnosis_summary"),
        prescribing_physician=parsed.get("prescribing_physician"),
        provider_npi=parsed.get("provider_npi"),
        requested_service_description=parsed.get("requested_service_description"),
        billed_amount=parsed.get("billed_amount"),
        extraction_confidence=confidence,
        field_confidence=_parse_field_confidence(parsed.get("field_confidence")),
        raw_document_text=raw_document_text,
        patient_query=patient_query,
        few_shot_corrections_used=[ex["case_id"] for ex in few_shot],
    )
    return clinical, relevant_agents, reason
