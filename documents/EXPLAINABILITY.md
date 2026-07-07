# Explainability in AgenticPA — Detailed Explanation

**Scope of this document:** how AgenticPA explains *why* a specific case was
routed to human review, beyond the free-text LLM rationale already produced
by the Peer-Review Auditor. This covers the new deterministic explainability
layer:

- **Counterfactual + factor-attribution explainer**
  (`backend/app/core/explainability.py`) — for a finalized/in-flight case's
  fired hard-gate flags, computes the exact numeric change that would have
  avoided each flag, and a ranked, normalized severity score per flag.

This is a different mechanism from, and complements, two things that already
existed before this document:

1. **`evaluate_hard_gates()`** (`backend/app/agents/peer_review_agent.py`) —
   decides *whether* a case needs human review. `explainability.py` never
   changes this decision; it only explains a decision already made.
2. **The LLM rationale layer** (`generate_rationale`, same file) — writes
   human-readable prose citing the fired flags. `explainability.py` doesn't
   replace that prose; it adds a structured, numeric layer next to it in the
   Reviewer Rationale Panel.

---

## 1. Why "explainability" means something different here

Classic explainability techniques (SHAP, LIME, attention-weight
visualization) exist to explain the output of a trained model whose internal
weights aren't directly interpretable. AgenticPA has no such model in its
decision path — `evaluate_hard_gates()` is a handful of deterministic
threshold comparisons over real CMS rates, RAG match scores, and extraction
confidence (see `documents/BIAS_FAIRNESS.md` §7 for the full list). Applying
SHAP to a set of `if x > threshold` comparisons would be theater: the "why"
is already fully transparent in the source code.

What a deterministic rule-based system *can* meaningfully offer that a plain
flag list can't:

1. **Counterfactuals** — not just "FINANCIAL_EXCEPTION fired" but "billed
   amount would need to be ≤ $519.48, not $5,000.00, to have stayed under
   the threshold." This is the single most actionable thing a reviewer or a
   provider disputing a denial can be told.
2. **Factor attribution when multiple flags fire** — a case can trip
   `LOW_CONFIDENCE_EXTRACTION` by a hair and `FINANCIAL_EXCEPTION` by 1000%
   simultaneously. Both appear in `hard_gate_flags`, but they are not
   equally "why" the case was escalated. Ranking them by how far past their
   own threshold each one is gives a real, non-arbitrary ordering.

---

## 2. Where it lives in the code

| Concern | File |
|---|---|
| Counterfactual + attribution algorithm | `backend/app/core/explainability.py` |
| API wiring (`GET /api/v1/review/{case_id}`) | `backend/app/api/routes.py` (`get_review`) |
| Reviewer Portal rendering | `frontend/src/components/RationalePanel.tsx` (new "Why This Decision" section) |
| Unit tests | `backend/tests/test_explainability.py` |

`explainability.py` is marked `// MVP-REAL` — every number it reports is
computed from the same fields `evaluate_hard_gates()` and `cost_agent.py` /
`rag_agent.py` already produce; nothing is invented or LLM-generated.

---

## 3. The algorithm

`explain_case(clinical, financial, policy, hard_gate_flags,
confidence_threshold, overcharge_threshold_percent, ambiguity_threshold)`
takes the same plain dict payloads the API already stores (`clinical_payload`,
`financial_payload`, `policy_payload`) plus the `hard_gate_flags` list
`evaluate_hard_gates()` already produced for that case, and the admin
thresholds in effect. For each fired flag it dispatches to a per-flag
explainer:

### 3.1 `LOW_CONFIDENCE_EXTRACTION`

- **Detail:** the actual `extraction_confidence` vs. `confidence_threshold`.
- **Counterfactual:** `"extraction_confidence would need to be >=
  {threshold} (currently {value})."` If confidence is missing entirely
  (not just low), severity is fixed at `1.0` and the counterfactual says so
  — a missing value isn't "almost enough," it's a different failure mode.
- **Severity:** `_gap_severity(confidence, threshold)` = how much of the
  threshold's own scale was missed, clipped to `[0, 1]`. E.g. confidence
  0.75 against threshold 0.85 → severity `(0.85-0.75)/0.85 ≈ 0.12` (missed
  by a little); confidence 0.0 → severity `1.0`.

### 3.2 `FINANCIAL_EXCEPTION`

- **Detail:** billed amount vs. CMS benchmark vs. variance percent.
- **Counterfactual:** the exact dollar ceiling —
  `max_billed = cms_benchmark_rate * (1 + overcharge_threshold_percent / 100)`,
  e.g. `"billed_amount would need to be <= $519.48 ... (currently
  $5,000.00)."` — computed directly from the same formula
  `cost_agent.py` uses to flag the overcharge, just inverted.
- **Severity:** `_bounded_overage(variance_percent, threshold)` = `1 -
  threshold / variance` for `variance > threshold`, else `0`. This
  saturates smoothly (0 at the threshold itself, 0.5 at 2x the threshold,
  ~0.9 at 10x) rather than growing unbounded — a 10,000%-over case and a
  100,000%-over case both read as "severely over," which is the honest
  signal; the exact multiple is still in `detail`.

### 3.3 `RATE_UNAVAILABLE`

- **Detail/counterfactual:** explicitly **no numeric counterfactual** —
  this flag means no CMS benchmark rate could be resolved at all (bad
  CPT/ZIP combination), which is a structural data-availability gap, not a
  value that crossed a line. Severity is fixed at `1.0`. Fabricating a
  "billed amount would need to be ≤ $X" here would be actively misleading
  since there is no `$X` to compute.

### 3.4 `POLICY_AMBIGUOUS`

- **Detail/counterfactual:** mirrors `LOW_CONFIDENCE_EXTRACTION`'s shape —
  `policy_match_confidence` vs. `ambiguity_threshold` (defaults to the same
  `0.70` used in `rag_agent.py`, passed in explicitly by the caller rather
  than imported, to avoid `app/core` depending on `app/agents`).

### 3.5 Combining multiple fired flags

```json
{
  "factors": [
    {"flag": "FINANCIAL_EXCEPTION", "severity": 0.96, "share": 0.89, "detail": "...", "counterfactual": "..."},
    {"flag": "LOW_CONFIDENCE_EXTRACTION", "severity": 0.12, "share": 0.11, "detail": "...", "counterfactual": "..."}
  ],
  "primary_driver": "FINANCIAL_EXCEPTION"
}
```

- `factors` is sorted by `severity` descending.
- `share = severity / sum(severity across fired flags)` — normalizes across
  flags measured on different underlying scales (a percent-variance gate
  and a confidence gate aren't directly comparable in raw units) so a
  reviewer can read "89% of why this case escalated is the cost variance."
  If every fired flag has severity `0` (only possible for edge-of-threshold
  cases), `share` splits evenly instead of dividing by zero.
- `primary_driver` is the single highest-severity flag, or `None` if no
  flags fired.

---

## 4. How it reaches the Reviewer Portal

`GET /api/v1/review/{case_id}` (`backend/app/api/routes.py`, `get_review`):

1. Pulls `hard_gate_flags` from the `peer_review_auditor` entry already
   present in the case's `agent_trace` (the same list `evaluate_hard_gates`
   produced when the case ran — not recomputed).
2. Reads the *current* admin-configured `confidence_threshold` and
   `overcharge_threshold_percent` via `get_settings(db)`. Note: if an admin
   changes these thresholds after a case was decided, the explanation
   reflects the *current* thresholds, not necessarily the ones in effect
   when the case was actually adjudicated — see §6.
3. Calls `explain_case(...)` and returns the result as `explainability` in
   the response body, alongside the existing `clinical`/`financial`/
   `policy`/`routing`/`agent_trace` fields.

`frontend/src/components/RationalePanel.tsx` renders a new "Why This
Decision (Explainability)" section (only when `explainability.factors` is
non-empty) below the Cost Formula Breakdown: one card per fired flag,
showing its `share` as a percentage, `severity` as a filled bar, the human
`detail` line, and the `counterfactual` line in teal.

---

## 5. Relationship to the LLM rationale layer

`generate_rationale()` (`peer_review_agent.py`) and `explain_case()` answer
related but distinct questions:

- The LLM rationale is **prose written for a human**, citing the same
  underlying numbers, and can also surface *additional* soft escalation
  reasons the deterministic hard gates didn't catch (see
  `documents/UNDERSTAND_AGENTICPA.md` / `peer_review_agent.py` docstring).
- `explain_case()` is **pure arithmetic over the hard-gate flags only** — it
  has no visibility into the LLM's additional escalation reasons, and
  cannot explain *those* with a counterfactual (there's no fixed threshold
  to invert for an LLM's free-form judgment call). This is intentional and
  disclosed: only deterministic gates get deterministic explanations.

---

## 6. Known limitations (state these proactively, don't wait to be asked)

| Limitation | Detail |
|---|---|
| No explanation for LLM-added escalation reasons | Only the four deterministic hard-gate flags get counterfactuals/attribution; `additional_escalation_reasons` from the LLM rationale layer are not explainable this way. |
| Thresholds used are "current," not "as-decided" | `get_review` reads live `admin_settings`, not a historical snapshot of the thresholds in effect when the case was actually adjudicated. If an admin changes `overcharge_threshold_percent` after the fact, the counterfactual dollar figure shown will reflect the new threshold. This matches how the Admin Portal already works elsewhere (settings aren't versioned per-case) but is worth naming explicitly here since a counterfactual is a precise-sounding number. |
| Severity is a distance-from-threshold heuristic, not a probability | `_bounded_overage`/`_gap_severity` are deliberately simple, monotonic, bounded transforms — not calibrated against any outcome (e.g. "probability this case is actually a true positive"). They answer "how far past the line," nothing more. |
| `RATE_UNAVAILABLE` has no counterfactual by design | This is disclosed, not a bug — see §3.3. |
| No cross-case comparison | Each explanation is self-contained to one case; there's no "this case's severity is in the Nth percentile of all `FINANCIAL_EXCEPTION` cases" framing (that would require aggregating across cases the way `fairness.py` does for cohorts — a possible future extension, not built here). |

---

## 7. Test coverage

`backend/tests/test_explainability.py` covers:

- Empty `hard_gate_flags` → `{"factors": [], "primary_driver": None}`.
- Each of the four flags' counterfactual text and severity computation,
  including the missing-confidence and rate-unavailable edge cases.
- Severity is exactly `0.0` at the threshold boundary (not negative, not
  flagged).
- Multiple fired flags are ranked by severity, `share` sums to `1.0`, and
  `primary_driver` matches the highest-severity flag.

See `documents/BIAS_FAIRNESS.md` for the companion Bayesian-fairness work
(`_beta_binomial_posterior` in `backend/app/core/fairness.py`), which is a
separate mechanism — that's about aggregate cohort-level disparity, this is
about a single case's own decision.
