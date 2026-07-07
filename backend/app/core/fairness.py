"""Real (not illustrative) cohort bucketing for the Admin Portal's Bias &
Fairness gauge, computed from fields that already exist on every case
(patient_dob, patient_zip, provider_npi, requested_service_description)
instead of a synthetic age/region dataset.

// MVP-REAL: replaces AdminPortal.tsx's previous BIAS_GAUGE_DATA constant,
which was hardcoded and explicitly marked MVP-MOCKED. Cohorts below the
MIN_COHORT_SIZE sample threshold are dropped rather than shown with a
misleadingly precise rate — small-N cohorts are exactly what causes fairness
dashboards to be misread.

Each cohort also carries a Wilson score interval and a `significant_disparity`
flag (its CI excludes the overall approval rate) so a gap like "60% vs 90%"
isn't asserted as real bias when it's actually just noise from a handful of
cases — the same small-N problem MIN_COHORT_SIZE guards against, just at the
comparison step instead of the display step.

Alongside that frequentist view, each cohort also carries a real Bayesian
Beta-Binomial posterior: `Beta(alpha_0 + successes, beta_0 + failures)`,
using a weakly-informative prior centered on the *overall* approval rate
(`PRIOR_STRENGTH = 4` pseudo-observations, so a 3-case cohort is still mostly
governed by its own data, not the prior). From that posterior we report the
posterior mean, a 95% equal-tailed credible interval (closed-form via the
Beta quantile function — no external stats dependency, no sampling), and
`p_worse_than_overall` = P(cohort's true approval rate < overall approval
rate | data), computed by numerically integrating the Beta PDF. This
answers a different question than the Wilson interval: not "is this
cohort's rate outside a null band around the overall rate" (frequentist
significance) but "how likely is it, given everything we've observed, that
this cohort is actually worse than average" (a direct, interpretable
probability) — the two are complementary lenses on the same data, not a
replacement of one by the other.
"""
import math
from datetime import date, datetime

MIN_COHORT_SIZE = 3
CONFIDENCE_Z = 1.96  # ~95% two-sided normal z-score
PRIOR_STRENGTH = 4  # pseudo-observations contributed by the Beta prior

AGE_BUCKETS = [
    (0, 64, "Under 65"),
    (65, 74, "Age 65-74"),
    (75, 84, "Age 75-84"),
    (85, 200, "Age 85+"),
]

# First-digit-of-ZIP -> US Census-style region, matching USPS ZIP prefix
# conventions. Coarse by design: fine enough to surface a real regional
# skew, coarse enough that a handful of MVP cases still land in >1 bucket.
ZIP_PREFIX_REGION = {
    "0": "Northeast", "1": "Northeast",
    "2": "South", "3": "South",
    "4": "Midwest", "5": "Midwest", "6": "Midwest",
    "7": "South",
    "8": "West", "9": "West",
}


def bucket_age(patient_dob: str | None, as_of: date | None = None) -> str | None:
    if not patient_dob:
        return None
    try:
        dob = datetime.fromisoformat(patient_dob).date()
    except ValueError:
        return None
    today = as_of or date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    for lo, hi, label in AGE_BUCKETS:
        if lo <= age <= hi:
            return label
    return None


def bucket_region(patient_zip: str | None) -> str | None:
    if not patient_zip:
        return None
    digits = "".join(c for c in patient_zip if c.isdigit())
    if not digits:
        return None
    return ZIP_PREFIX_REGION.get(digits[0])


def bucket_provider(provider_npi: str | None) -> str | None:
    if not provider_npi:
        return None
    return f"Provider {provider_npi}"


def bucket_service(requested_service_description: str | None) -> str | None:
    if not requested_service_description:
        return None
    return requested_service_description


DIMENSIONS = {
    "age": lambda row: bucket_age(row.get("patient_dob")),
    "region": lambda row: bucket_region(row.get("patient_zip")),
    "provider": lambda row: bucket_provider(row.get("provider_npi")),
    "service": lambda row: bucket_service(row.get("requested_service_description")),
}


def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _betacf(x: float, a: float, b: float) -> float:
    """Continued-fraction expansion for the incomplete beta function
    (Lentz's algorithm, as in Numerical Recipes §6.4). Pure-Python so the
    Bayesian posterior needs no scipy/numpy dependency."""
    MAX_ITER = 200
    EPS = 1e-14
    TINY = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < TINY:
        d = TINY
    d = 1.0 / d
    h = d
    for m in range(1, MAX_ITER + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < TINY:
            d = TINY
        c = 1.0 + aa / c
        if abs(c) < TINY:
            c = TINY
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < TINY:
            d = TINY
        c = 1.0 + aa / c
        if abs(c) < TINY:
            c = TINY
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def _betainc(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta function I_x(a, b) = CDF of Beta(a, b) at x.
    Standard continued-fraction + symmetry-relation implementation (Numerical
    Recipes §6.4) — this is the real, general-purpose algorithm used inside
    scipy.special.betainc, just hand-rolled to avoid adding scipy as a
    dependency for one function."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.log(x) * a + math.log(1.0 - x) * b - _log_beta(a, b))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(x, a, b) / a
    return 1.0 - front * _betacf(1.0 - x, b, a) / b


def _beta_quantile(p: float, a: float, b: float, tol: float = 1e-6) -> float:
    """Invert the Beta(a, b) CDF at probability p via bisection on _betainc —
    closed-form quantile functions for the Beta distribution don't exist in
    general, so bisection on the CDF is the standard approach."""
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if _betainc(mid, a, b) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return (lo + hi) / 2.0


def _beta_binomial_posterior(
    successes: int, n: int, overall_rate: float | None
) -> dict:
    """Real Bayesian Beta-Binomial conjugate update. Prior is Beta(alpha_0,
    beta_0) with alpha_0 + beta_0 = PRIOR_STRENGTH, centered on the overall
    approval rate across all rows (falls back to an uninformative Beta(1,1)
    if there's no overall rate to center on, e.g. an empty dataset).
    Posterior is Beta(alpha_0 + successes, beta_0 + failures) by conjugacy.

    Returns posterior mean, a 95% equal-tailed credible interval, and
    `p_worse_than_overall` = P(true cohort rate < overall_rate | data),
    i.e. the CDF of the posterior evaluated at overall_rate — a direct
    probability statement, not a p-value.
    """
    if overall_rate is None:
        alpha_0, beta_0 = 1.0, 1.0
    else:
        alpha_0 = PRIOR_STRENGTH * overall_rate
        beta_0 = PRIOR_STRENGTH * (1.0 - overall_rate)
    alpha_0 = max(alpha_0, 1e-3)
    beta_0 = max(beta_0, 1e-3)

    failures = n - successes
    alpha_post = alpha_0 + successes
    beta_post = beta_0 + failures

    mean = alpha_post / (alpha_post + beta_post)
    cred_low = _beta_quantile(0.025, alpha_post, beta_post)
    cred_high = _beta_quantile(0.975, alpha_post, beta_post)
    p_worse = (
        _betainc(overall_rate, alpha_post, beta_post) if overall_rate is not None else None
    )

    return {
        "posterior_mean": round(mean, 4),
        "credible_low": round(cred_low, 4),
        "credible_high": round(cred_high, 4),
        "p_worse_than_overall": round(p_worse, 4) if p_worse is not None else None,
    }


def _wilson_interval(successes: int, n: int, z: float = CONFIDENCE_Z) -> tuple[float, float]:
    """95%-by-default Wilson score interval — safe at small n, unlike a
    normal-approximation interval which can go outside [0, 1]."""
    if n == 0:
        return (0.0, 0.0)
    phat = successes / n
    denom = 1 + z**2 / n
    center = phat + z**2 / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))
    lo = (center - margin) / denom
    hi = (center + margin) / denom
    return max(0.0, lo), min(1.0, hi)


def compute_fairness_cohorts(rows: list[dict]) -> list[dict]:
    """rows: [{"patient_dob", "patient_zip", "provider_npi",
    "requested_service_description", "outcome_is_denied": bool}, ...] for
    finalized cases only. Returns cohorts with >= MIN_COHORT_SIZE cases across
    four dimensions (age, region, provider, service), each:
    {"dimension": str, "cohort": str, "total": int, "approval_rate": float,
     "ci_low": float, "ci_high": float, "significant_disparity": bool,
     "posterior_mean": float, "credible_low": float, "credible_high": float,
     "p_worse_than_overall": float | None}.

    significant_disparity is True when the cohort's own Wilson interval
    excludes the overall approval rate across all rows — i.e. the gap is
    unlikely to be sampling noise, not just "different from average". The
    posterior_mean/credible_*/p_worse_than_overall fields are the Bayesian
    Beta-Binomial counterpart (see _beta_binomial_posterior) — a direct
    probability that this cohort is worse than average, rather than a
    frequentist significance flag."""
    outcomes_all = [not row.get("outcome_is_denied", False) for row in rows]
    overall_rate = sum(outcomes_all) / len(outcomes_all) if outcomes_all else None

    buckets: dict[tuple[str, str], list[bool]] = {}
    for row in rows:
        outcome = not row.get("outcome_is_denied", False)
        for dimension, bucket_fn in DIMENSIONS.items():
            label = bucket_fn(row)
            if label:
                buckets.setdefault((dimension, label), []).append(outcome)

    cohorts = []
    for (dimension, label), outcomes in buckets.items():
        n = len(outcomes)
        if n < MIN_COHORT_SIZE:
            continue
        successes = sum(outcomes)
        rate = successes / n
        ci_low, ci_high = _wilson_interval(successes, n)
        bayes = _beta_binomial_posterior(successes, n, overall_rate)
        cohorts.append(
            {
                "dimension": dimension,
                "cohort": label,
                "total": n,
                "approval_rate": round(rate, 4),
                "ci_low": round(ci_low, 4),
                "ci_high": round(ci_high, 4),
                "significant_disparity": (
                    overall_rate is not None and not (ci_low <= overall_rate <= ci_high)
                ),
                "posterior_mean": bayes["posterior_mean"],
                "credible_low": bayes["credible_low"],
                "credible_high": bayes["credible_high"],
                "p_worse_than_overall": bayes["p_worse_than_overall"],
            }
        )
    return sorted(cohorts, key=lambda c: (c["dimension"], c["cohort"]))
