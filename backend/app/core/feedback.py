"""
Feedback-correction storage and lookup — the self-improving loop described in
CLAUDE.md's "Differentiator" section.

// DEMO-REAL

Corrections are keyed by (icd10_family, cpt_family). Lookup is an indexed
exact-match query on that family pair, not a vector similarity search: an
ICD-10 family (e.g. "J45" from "J45.909") is already a precise categorical
key, so embedding similarity would add latency/noise without adding recall.
This is a deliberate simplification of CLAUDE.md's "vector-searches this
table" phrasing — documented as a decision in the implementation report, not
a silent shortcut.
"""
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

ICD10_RE = re.compile(r"\b[A-TV-Z][0-9][0-9AB](?:\.[0-9A-TV-Z]{1,4})?\b")

FEW_SHOT_LIMIT = 3


def icd10_family(code: str) -> str:
    """'J45.909' -> 'J45'. Family is the category before the decimal point."""
    return code.split(".")[0].strip().upper()


def cpt_family(code: str) -> str:
    """CPT codes are already the right granularity — no sub-splitting needed."""
    return code.strip().upper()


def extract_candidate_icd10(raw_text: str) -> str | None:
    """Cheap regex pass over raw document text to find a candidate ICD-10 code
    *before* the LLM extraction call runs, so few-shot examples can be
    injected into that same call rather than requiring a second pass."""
    match = ICD10_RE.search(raw_text or "")
    return match.group(0) if match else None


def record_correction(
    db: Session,
    case_id: str,
    icd10_codes: list[str],
    cpt_codes: list[str],
    corrected_field: str,
    original_value: str | None,
    corrected_value: str | None,
    reviewer_id: str | None = None,
) -> None:
    """Insert one feedback_corrections row keyed by the case's primary
    ICD-10/CPT family. No-op if the case has no codes to key off of."""
    if not icd10_codes or not cpt_codes:
        return
    db.execute(
        text(
            """
            INSERT INTO feedback_corrections
                (id, icd10_family, cpt_family, case_id, reviewer_id,
                 corrected_field, original_value, corrected_value, created_at)
            VALUES
                (gen_random_uuid()::text, :icd10_family, :cpt_family, :case_id,
                 :reviewer_id, :corrected_field, :original_value,
                 :corrected_value, now())
            """
        ),
        {
            "icd10_family": icd10_family(icd10_codes[0]),
            "cpt_family": cpt_family(cpt_codes[0]),
            "case_id": case_id,
            "reviewer_id": reviewer_id,
            "corrected_field": corrected_field,
            "original_value": original_value,
            "corrected_value": corrected_value,
        },
    )
    db.commit()


def get_few_shot_examples(
    db: Session, icd10_code: str | None, limit: int = FEW_SHOT_LIMIT
) -> list[dict]:
    """Top-N most recent corrections sharing this ICD-10 family, across any
    CPT family — used as few-shot examples in the Intake extraction prompt."""
    if not icd10_code:
        return []
    rows = db.execute(
        text(
            """
            SELECT cpt_family, corrected_field, original_value, corrected_value, case_id
            FROM feedback_corrections
            WHERE icd10_family = :family
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"family": icd10_family(icd10_code), "limit": limit},
    ).mappings().all()
    return [dict(r) for r in rows]
