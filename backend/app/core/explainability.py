"""Deterministic explainability layer for the Peer-Review Auditor's hard-gate
decision on a single case.

// MVP-REAL

There is no trained classifier anywhere in this pipeline to explain with
SHAP/LIME-style attribution over model weights — `evaluate_hard_gates()`
(`app/agents/peer_review_agent.py`) is a set of deterministic threshold
comparisons over real CMS/RAG/extraction numbers. So "explainability" here
means the two things that are actually meaningful for a rule-based decision:

1. **Counterfactuals** — for each fired flag, the exact numeric change to
   the underlying evidence that would have avoided it (e.g. "billed amount
   would need to be <= $X" or "extraction confidence would need to be >=
   Y"), computed from the same thresholds `evaluate_hard_gates` uses. Some
   flags (`RATE_UNAVAILABLE`) have no counterfactual threshold to report —
   they are a structural failure (no CMS rate resolved at all), not a value
   that crossed a line, and this module says so explicitly rather than
   fabricating one.
2. **Factor attribution** — a normalized 0-1 severity score per fired flag,
   so a reviewer looking at a case with multiple flags can see which one
   drove the decision hardest, not just that "something" fired. This is
   distance-from-threshold, not a learned weight: it answers "how far past
   the line is this," which is the only notion of "importance" a
   deterministic rule has.

Operates on the same plain dicts the API already stores/returns
(`clinical_payload`, `financial_payload`, `policy_payload` JSON columns) and
the `hard_gate_flags` list already produced by `evaluate_hard_gates` — no
reconstruction of `AgenticPAState` needed.
"""

LOW_CONFIDENCE_EXTRACTION = "LOW_CONFIDENCE_EXTRACTION"
FINANCIAL_EXCEPTION = "FINANCIAL_EXCEPTION"
RATE_UNAVAILABLE = "RATE_UNAVAILABLE"
POLICY_AMBIGUOUS = "POLICY_AMBIGUOUS"

# Mirrors app/agents/rag_agent.py's AMBIGUITY_THRESHOLD. Duplicated (not
# imported) deliberately: app/core is a lower architectural layer than
# app/agents, and this module accepts thresholds as parameters everywhere
# else for the same reason — the default here only covers the case where a
# caller doesn't have the agent's threshold handy (e.g. an ad-hoc script).
DEFAULT_AMBIGUITY_THRESHOLD = 0.70


def _bounded_overage(value: float, threshold: float) -> float:
    """Map a value that exceeds a threshold to (0, 1), saturating as the
    overage grows without bound. 0 at value == threshold, 0.5 at 2x
    threshold, ~0.9 at 10x threshold. Same shape for any positive threshold,
    which is what makes it usable across different fields/units (percent
    variance vs. a confidence gap)."""
    if threshold <= 0 or value <= threshold:
        return 0.0
    return max(0.0, 1.0 - threshold / value)


def _gap_severity(actual: float, threshold: float) -> float:
    """For 'must be >= threshold' gates (confidence, policy match): how much
    of the threshold's own scale was missed, clipped to [0, 1]."""
    if threshold <= 0:
        return 0.0
    return min(1.0, max(0.0, (threshold - actual) / threshold))


def _explain_low_confidence(clinical: dict, confidence_threshold: float) -> dict:
    confidence = clinical.get("extraction_confidence")
    if confidence is None:
        return {
            "flag": LOW_CONFIDENCE_EXTRACTION,
            "severity": 1.0,
            "detail": "extraction_confidence is missing entirely, not just low.",
            "counterfactual": (
                f"Intake would need to report a numeric extraction_confidence "
                f">= {confidence_threshold} (currently missing)."
            ),
        }
    severity = _gap_severity(confidence, confidence_threshold)
    return {
        "flag": LOW_CONFIDENCE_EXTRACTION,
        "severity": round(severity, 4),
        "detail": (
            f"extraction_confidence {confidence:.4f} is below the "
            f"{confidence_threshold} threshold."
        ),
        "counterfactual": (
            f"extraction_confidence would need to be >= {confidence_threshold} "
            f"(currently {confidence:.4f})."
        ),
    }


def _explain_financial_exception(financial: dict, overcharge_threshold_percent: float) -> dict:
    variance_percent = financial.get("variance_percent") or 0.0
    billed_amount = financial.get("billed_amount")
    benchmark_rate = financial.get("cms_benchmark_rate")
    severity = _bounded_overage(variance_percent, overcharge_threshold_percent)
    detail = (
        f"billed ${billed_amount:,.2f} vs. CMS benchmark ${benchmark_rate:,.2f} "
        f"is {variance_percent:.1f}% over, exceeding the "
        f"{overcharge_threshold_percent:.0f}% threshold."
        if billed_amount is not None and benchmark_rate is not None
        else f"variance_percent {variance_percent:.1f}% exceeds the "
        f"{overcharge_threshold_percent:.0f}% threshold."
    )
    if benchmark_rate:
        max_billed = benchmark_rate * (1 + overcharge_threshold_percent / 100)
        counterfactual = (
            f"billed_amount would need to be <= ${max_billed:,.2f} to stay within "
            f"{overcharge_threshold_percent:.0f}% of the ${benchmark_rate:,.2f} "
            f"CMS benchmark (currently ${billed_amount:,.2f})."
        )
    else:
        counterfactual = "No CMS benchmark rate on record to compute a dollar counterfactual from."
    return {
        "flag": FINANCIAL_EXCEPTION,
        "severity": round(severity, 4),
        "detail": detail,
        "counterfactual": counterfactual,
    }


def _explain_rate_unavailable() -> dict:
    return {
        "flag": RATE_UNAVAILABLE,
        "severity": 1.0,
        "detail": (
            "No CMS benchmark rate could be resolved for this CPT/ZIP combination — "
            "there is no billed amount to compare against, so cost can't be evaluated at all."
        ),
        "counterfactual": (
            "N/A — this is a structural data-availability gap (an RVU-payable CPT code "
            "resolving to a known locality), not a value that crossed a numeric threshold."
        ),
    }


def _explain_policy_ambiguous(policy: dict, ambiguity_threshold: float) -> dict:
    match_confidence = policy.get("policy_match_confidence") or 0.0
    severity = _gap_severity(match_confidence, ambiguity_threshold)
    return {
        "flag": POLICY_AMBIGUOUS,
        "severity": round(severity, 4),
        "detail": (
            f"top policy match confidence {match_confidence:.4f} is below the "
            f"{ambiguity_threshold} ambiguity threshold."
        ),
        "counterfactual": (
            f"policy_match_confidence would need to be >= {ambiguity_threshold} "
            f"(currently {match_confidence:.4f})."
        ),
    }


_EXPLAINERS = {
    LOW_CONFIDENCE_EXTRACTION: lambda ctx: _explain_low_confidence(
        ctx["clinical"], ctx["confidence_threshold"]
    ),
    FINANCIAL_EXCEPTION: lambda ctx: _explain_financial_exception(
        ctx["financial"], ctx["overcharge_threshold_percent"]
    ),
    RATE_UNAVAILABLE: lambda ctx: _explain_rate_unavailable(),
    POLICY_AMBIGUOUS: lambda ctx: _explain_policy_ambiguous(
        ctx["policy"], ctx["ambiguity_threshold"]
    ),
}


def explain_case(
    clinical: dict,
    financial: dict,
    policy: dict,
    hard_gate_flags: list[str],
    confidence_threshold: float,
    overcharge_threshold_percent: float,
    ambiguity_threshold: float = DEFAULT_AMBIGUITY_THRESHOLD,
) -> dict:
    """Build the counterfactual + factor-attribution explanation for a case's
    fired hard-gate flags.

    Returns:
    {
      "factors": [
        {"flag": str, "severity": float in [0,1], "share": float in [0,1],
         "detail": str, "counterfactual": str},
        ...  # sorted by severity desc, one entry per element of hard_gate_flags
      ],
      "primary_driver": str | None,  # flag with the highest severity, or None if no flags fired
    }

    `share` normalizes severity across only the flags that actually fired on
    this case (sums to 1.0 across `factors`) so a reviewer can read it as
    "80% of why this case was escalated is the cost variance, 20% is the
    confidence gap" rather than comparing raw severities across unrelated
    scales.
    """
    if not hard_gate_flags:
        return {"factors": [], "primary_driver": None}

    ctx = {
        "clinical": clinical,
        "financial": financial,
        "policy": policy,
        "confidence_threshold": confidence_threshold,
        "overcharge_threshold_percent": overcharge_threshold_percent,
        "ambiguity_threshold": ambiguity_threshold,
    }

    factors = [_EXPLAINERS[flag](ctx) for flag in hard_gate_flags if flag in _EXPLAINERS]
    severity_total = sum(f["severity"] for f in factors)
    for f in factors:
        f["share"] = round(f["severity"] / severity_total, 4) if severity_total > 0 else round(
            1.0 / len(factors), 4
        )

    factors.sort(key=lambda f: f["severity"], reverse=True)
    primary_driver = factors[0]["flag"] if factors else None

    return {"factors": factors, "primary_driver": primary_driver}
