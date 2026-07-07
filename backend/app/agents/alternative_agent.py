"""
Alternative Therapy Mapper.

// MVP-MOCKED: the CPT->alternative-CPT mapping table below is hardcoded (2-3
entries), not a real clinical-guideline engine. This is explicitly scoped as
MVP-MOCKED in CLAUDE.md, not a TODO.

// MVP-REAL: once a mapping fires, the alternative's dollar cost is computed
via the same real CMS rate lookup (app.core.cms_rates.get_cms_rate) used by
the Cost agent — the savings number shown to the reviewer is not fabricated.

Per CLAUDE.md's resolved item #2, the flagship mapping (M17.9 + CPT 27447,
total knee arthroplasty) is reframed as a procedure alternative rather than a
drug/biosimilar swap: CMS prices major surgery's OR/implant/hospital
component through a separate facility payment system this repo doesn't
model, so the only "biosimilar"-shaped comparison available from local RVU
data is professional-fee-to-professional-fee (surgery vs. a conservative
first-line injection) — same "out of scope" boundary as ASP/DMEPOS drug
pricing noted elsewhere in this repo.
"""
from sqlalchemy.orm import Session

from app.core.cms_rates import get_cms_rate

# (icd10_family, cpt) -> (alternative_cpt, human-readable description)
ALTERNATIVE_MAPPINGS: dict[tuple[str, str], tuple[str, str]] = {
    ("M17", "27447"): (
        "20610",
        "Conservative-first pathway: physical therapy + intra-articular "
        "corticosteroid/hyaluronic acid injection (CPT 20610) before "
        "proceeding to total knee arthroplasty (CPT 27447).",
    ),
    ("M25", "29881"): (
        "20610",
        "Conservative-first pathway: intra-articular corticosteroid "
        "injection (CPT 20610) before proceeding to knee arthroscopy "
        "(CPT 29881).",
    ),
    ("M54", "63030"): (
        "64483",
        "Conservative-first pathway: lumbar epidural steroid injection "
        "(CPT 64483) before proceeding to lumbar discectomy (CPT 63030).",
    ),
}


def run_alternative_mapper(
    icd10_codes: list[str],
    cpt_codes: list[str],
    zip_code: str | None,
    db: Session,
) -> dict | None:
    """Look up a hardcoded conservative-first alternative for the case's
    (ICD-10 family, CPT) pair. Returns None if no mapping fires — this agent
    never invents an alternative outside its static table.

    Returns {"alternative_cpt", "description", "alternative_cost",
    "savings"} — alternative_cost/savings are None if the alt CPT isn't
    RVU-payable or the zip doesn't resolve (same "rate unavailable" contract
    as cms_rates.get_cms_rate).
    """
    if not icd10_codes or not cpt_codes or not zip_code:
        return None

    families = {code.split(".")[0].strip().upper() for code in icd10_codes}
    for cpt in cpt_codes:
        for family in families:
            mapping = ALTERNATIVE_MAPPINGS.get((family, cpt.strip()))
            if mapping:
                alt_cpt, description = mapping
                alt_cost = get_cms_rate(alt_cpt, zip_code, db)
                return {
                    "requested_cpt": cpt,
                    "alternative_cpt": alt_cpt,
                    "description": description,
                    "alternative_cost": round(alt_cost, 2) if alt_cost is not None else None,
                }
    return None
