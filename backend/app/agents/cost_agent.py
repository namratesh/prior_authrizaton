"""
Cost Intelligence & Benchmarking agent.

// MVP-REAL

Pure deterministic computation: no LLM call anywhere in this module (rule 1
in CLAUDE.md — decisions are RAG retrieval + math + hardcoded rules, never a
model). Looks up the real CMS benchmark rate for the billed CPT/zip via
app.core.cms_rates.get_cms_rate, then flags FINANCIAL_EXCEPTION when the
billed amount exceeds the benchmark by more than overcharge_threshold_percent
(admin-tunable via settings_store.py, default 20%).
"""
from sqlalchemy.orm import Session

from app.core.cms_rates import get_cms_rate
from app.core.settings_store import DEFAULT_OVERCHARGE_THRESHOLD_PERCENT
from app.core.state import FinancialPayload


def run_cost_agent(
    billed_amount: float,
    cpt: str,
    zip_code: str,
    db: Session,
    overcharge_threshold_percent: float = DEFAULT_OVERCHARGE_THRESHOLD_PERCENT,
) -> FinancialPayload:
    """Compute variance of a billed amount against the real CMS benchmark rate.

    If the CPT isn't RVU-payable or the zip doesn't resolve to a known
    locality, returns a payload with cms_benchmark_rate=None and
    is_overcharge=None — "rate unavailable, manual review required" is a
    routing decision for the caller, not something this function fabricates.
    """
    rate = get_cms_rate(cpt, zip_code, db)
    if rate is None:
        return FinancialPayload(billed_amount=billed_amount)

    variance_amount = billed_amount - rate
    variance_percent = (variance_amount / rate) * 100
    is_overcharge = variance_percent > overcharge_threshold_percent

    return FinancialPayload(
        billed_amount=billed_amount,
        cms_benchmark_rate=round(rate, 2),
        variance_amount=round(variance_amount, 2),
        variance_percent=round(variance_percent, 2),
        is_overcharge=is_overcharge,
    )
