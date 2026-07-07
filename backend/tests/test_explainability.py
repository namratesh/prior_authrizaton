from app.core.explainability import (
    FINANCIAL_EXCEPTION,
    LOW_CONFIDENCE_EXTRACTION,
    POLICY_AMBIGUOUS,
    RATE_UNAVAILABLE,
    explain_case,
)

CONFIDENCE_THRESHOLD = 0.85
OVERCHARGE_THRESHOLD_PERCENT = 20.0
AMBIGUITY_THRESHOLD = 0.70


def _explain(hard_gate_flags, clinical=None, financial=None, policy=None):
    return explain_case(
        clinical=clinical or {},
        financial=financial or {},
        policy=policy or {},
        hard_gate_flags=hard_gate_flags,
        confidence_threshold=CONFIDENCE_THRESHOLD,
        overcharge_threshold_percent=OVERCHARGE_THRESHOLD_PERCENT,
        ambiguity_threshold=AMBIGUITY_THRESHOLD,
    )


def test_no_flags_returns_empty_explanation():
    result = _explain([])
    assert result == {"factors": [], "primary_driver": None}


def test_low_confidence_counterfactual_reports_exact_gap():
    result = _explain(
        [LOW_CONFIDENCE_EXTRACTION], clinical={"extraction_confidence": 0.5}
    )
    factor = result["factors"][0]
    assert factor["flag"] == LOW_CONFIDENCE_EXTRACTION
    assert "0.85" in factor["counterfactual"]
    assert "0.5000" in factor["counterfactual"]
    assert 0.0 < factor["severity"] <= 1.0
    assert result["primary_driver"] == LOW_CONFIDENCE_EXTRACTION


def test_missing_confidence_is_max_severity():
    result = _explain([LOW_CONFIDENCE_EXTRACTION], clinical={"extraction_confidence": None})
    assert result["factors"][0]["severity"] == 1.0


def test_financial_exception_counterfactual_computes_exact_dollar_threshold():
    result = _explain(
        [FINANCIAL_EXCEPTION],
        financial={"billed_amount": 5000.0, "cms_benchmark_rate": 432.90, "variance_percent": 1055.0},
    )
    factor = result["factors"][0]
    # max_billed = 432.90 * 1.20 = 519.48
    assert "519.48" in factor["counterfactual"]
    assert factor["severity"] > 0.9  # deeply over threshold, should saturate high


def test_financial_exception_severity_zero_at_threshold_boundary():
    result = _explain(
        [FINANCIAL_EXCEPTION],
        financial={"billed_amount": 100.0, "cms_benchmark_rate": 100.0, "variance_percent": 20.0},
    )
    assert result["factors"][0]["severity"] == 0.0


def test_rate_unavailable_has_no_numeric_counterfactual():
    result = _explain([RATE_UNAVAILABLE])
    factor = result["factors"][0]
    assert factor["severity"] == 1.0
    assert "N/A" in factor["counterfactual"]


def test_policy_ambiguous_counterfactual_reports_exact_gap():
    result = _explain([POLICY_AMBIGUOUS], policy={"policy_match_confidence": 0.4})
    factor = result["factors"][0]
    assert "0.7" in factor["counterfactual"]
    assert "0.4000" in factor["counterfactual"]


def test_multiple_flags_ranked_by_severity_and_shares_sum_to_one():
    result = _explain(
        [LOW_CONFIDENCE_EXTRACTION, FINANCIAL_EXCEPTION],
        clinical={"extraction_confidence": 0.84},  # barely below threshold, low severity
        financial={
            "billed_amount": 5000.0,
            "cms_benchmark_rate": 432.90,
            "variance_percent": 1055.0,
        },  # deeply over, high severity
    )
    factors = result["factors"]
    assert [f["flag"] for f in factors] == [FINANCIAL_EXCEPTION, LOW_CONFIDENCE_EXTRACTION]
    assert result["primary_driver"] == FINANCIAL_EXCEPTION
    assert round(sum(f["share"] for f in factors), 6) == 1.0
