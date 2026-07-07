# Bias & Fairness in AgenticPA — Detailed Explanation

**Scope of this document:** how AgenticPA detects, monitors, and discloses potential
demographic disparity in Prior Authorization (PA) outcomes, and — just as
important — what it does **not** do. This covers two separate mechanisms that
are easy to conflate:

1. **Bias & Fairness Gauge** (`backend/app/core/fairness.py`) — a monitoring
   dashboard that measures cohort-level approval-rate disparity from real
   case outcomes.
2. **Peer-Review hard gates** (`backend/app/agents/peer_review_agent.py`) —
   the deterministic rules that route individual cases to a human reviewer,
   which is the system's actual defense against biased or low-quality
   automated decisions.

Neither mechanism talks to the other. There is no automatic feedback loop
where the fairness gauge changes how a case is adjudicated — that is a
deliberate design choice, explained in §5.

---

## 1. The problem being addressed

Automated or AI-assisted adjudication of healthcare claims/PA requests
carries a well-documented risk: if approval/denial rates differ
systematically along demographic lines (age, race, sex, geography, income),
that is evidence of disparate impact even when no single decision looks
wrong in isolation. Regulators (e.g., CMS interoperability/PA rules) and
internal compliance teams expect adjudication systems to be able to answer,
at minimum: *"do outcomes differ by cohort, and if so, by how much, and
based on how much data?"*

AgenticPA's Bias & Fairness Gauge exists to make that question answerable
from real data, on the Admin Portal, at all times — rather than requiring a
retrospective audit.

### What this system explicitly cannot do

AgenticPA does not capture race, ethnicity, sex/gender, income, or
disability status anywhere in its data model (`backend/app/db/models.py`).
The only demographic-adjacent fields that exist on every case are:

- `patient_dob` (date of birth) — extracted by the Intake agent from the
  uploaded PDF
- `patient_zip` (ZIP code) — extracted the same way

So the fairness gauge can only ever compute **proxies**: age (derived from
DOB) and coarse geographic region (derived from ZIP). This is a real
limitation, not an oversight, and it is disclosed directly in the Admin
Portal UI caption and should be disclosed in any stakeholder-facing
material. See §6 for how to talk about this honestly.

---

## 2. Where it lives in the code

| Concern | File |
|---|---|
| Bucketing + aggregation algorithm | `backend/app/core/fairness.py` |
| API wiring (`GET /api/v1/admin/metrics`) | `backend/app/api/routes.py` |
| Dashboard rendering | `frontend/src/pages/AdminPortal.tsx` (`BiasFairnessCard`) |
| Unit tests | `backend/tests/test_fairness.py` |

`fairness.py` is marked `// DEMO-REAL` in its module docstring — it replaced
an earlier, explicitly `DEMO-MOCKED` hardcoded constant
(`BIAS_GAUGE_DATA`) that used to live in `AdminPortal.tsx`. The gauge is
computed live from the `cases` table, not from sample/fixture data.

---

## 3. The algorithm

### 3.1 Age bucketing — `bucket_age(patient_dob, as_of=None)`

```
AGE_BUCKETS = [
    (0,  64,  "Under 65"),
    (65, 74,  "Age 65-74"),
    (75, 84,  "Age 75-84"),
    (85, 200, "Age 85+"),
]
```

- Parses `patient_dob` as an ISO date string.
- Computes age as of `as_of` (defaults to `date.today()`; the parameter
  exists so tests are deterministic and don't rot as time passes).
- Maps age into exactly one of the four buckets above.
- Returns `None` — never raises — if `patient_dob` is missing, empty, or
  fails to parse. A `None` result means the case simply doesn't contribute
  to any age cohort; it does not crash the metrics endpoint.

The four buckets intentionally mirror Medicare-relevant age bands (AARP
Medicare's population skews 65+, so "Under 65," "65-74," "75-84," "85+" is
a clinically meaningful split, not an arbitrary quartering).

### 3.2 Region bucketing — `bucket_region(patient_zip)`

```
ZIP_PREFIX_REGION = {
    "0": "Northeast", "1": "Northeast",
    "2": "South",     "3": "South",
    "4": "Midwest",   "5": "Midwest", "6": "Midwest",
    "7": "South",
    "8": "West",      "9": "West",
}
```

- Strips all non-digit characters from `patient_zip`.
- Takes the **first digit only** and maps it to one of 4 US Census-style
  regions using the table above (this mirrors the real USPS ZIP-prefix
  geography — e.g. 0/1 = New England/NY/NJ, 9 = West Coast).
- Returns `None` if the ZIP is missing/empty after stripping non-digits.

This is deliberately coarse: a single digit only distinguishes ~10 macro
regions, not states or counties. The tradeoff is explicit — fine enough to
surface a genuine regional skew if one exists, coarse enough that a small
demo/pilot dataset still produces cohorts large enough to be meaningful
(see §3.3).

### 3.3 Cohort aggregation — `compute_fairness_cohorts(rows)`

Input: a list of dicts, one per **finalized** case (`final_status` is
`Approved` or `Denied` — cases still in flight are excluded):

```python
{"patient_dob": "1952-03-14", "patient_zip": "90210", "outcome_is_denied": False}
```

Logic:

1. For every row, compute **both** `bucket_age(...)` and
   `bucket_region(...)`. A single case can contribute to an age cohort
   *and* a region cohort simultaneously — these are two independent 1-D
   breakdowns, not a cross-tabulation (there is no "West + 75-84" cell).
2. Group outcomes (`approved = not outcome_is_denied`) by cohort label.
3. **Drop any cohort with fewer than `MIN_COHORT_SIZE = 3` outcomes
   entirely.** It is not shown with a caveat or an asterisk — it is
   omitted from the response. This is the single most important fairness
   safeguard in the code: a 1-of-1 or 2-of-2 cohort would report a 0% or
   100% approval rate that looks alarming or falsely reassuring but is
   statistical noise. Suppressing small-N cohorts prevents the dashboard
   from being misread — this is the classic failure mode fairness
   dashboards are criticized for.
4. For surviving cohorts, compute
   `approval_rate = round(approved_count / total_count, 4)`.
5. Return cohorts sorted alphabetically by label, e.g.:

```json
[
  {"cohort": "Age 65-74", "total": 12, "approval_rate": 0.9167},
  {"cohort": "Age 75-84", "total": 5,  "approval_rate": 0.6000},
  {"cohort": "Midwest",   "total": 4,  "approval_rate": 1.0000},
  {"cohort": "Northeast", "total": 6,  "approval_rate": 0.8333},
  {"cohort": "South",     "total": 7,  "approval_rate": 0.7143},
  {"cohort": "Under 65",  "total": 3,  "approval_rate": 1.0000}
]
```

Note "West," "Age 85+" are absent above — not because they're excluded by
design, but because (in this hypothetical) fewer than 3 finalized cases
landed in them.

---

## 4. How it reaches the Admin Portal

`GET /api/v1/admin/metrics` (`backend/app/api/routes.py`):

1. Queries all cases where `final_status IS NOT NULL`.
2. Builds `rows = [{"patient_dob": ..., "patient_zip": ..., "outcome_is_denied": final_status == "Denied"} for each case]`.
3. Calls `compute_fairness_cohorts(rows)` → `fairness_cohorts`.
4. Also returns `fairness_finalized_total` — the total count of finalized
   cases considered, *before* small-N cohort dropping. This lets the
   frontend distinguish "no cases yet" from "cases exist, but none of them
   cluster into a cohort of 3+" — two very different situations that would
   otherwise look identical (an empty chart).

`frontend/src/pages/AdminPortal.tsx`'s `BiasFairnessCard`:

- Renders a Recharts bar chart with one bar per cohort, y-axis =
  `approval_rate`.
- Displays an explanatory caption disclosing: the exact fields used
  (`patient_dob`/`patient_zip`), the ≥3-case threshold, and that cohorts
  below the threshold are omitted.
- If `fairness_finalized_total` is 0 or very low, shows a "not enough data
  yet" message instead of a possibly-empty/misleading chart.

---

## 5. Why this is monitoring, not mitigation — and why that's intentional

`fairness.py` is not imported by `graph.py`, `supervisor.py`, or
`peer_review_agent.py`. There is **zero** coupling between the fairness
gauge and the adjudication pipeline. Concretely, that means:

- No case is ever routed to human review *because* it belongs to a cohort
  with a lower approval rate.
- No decision is ever reweighted, adjusted, or blocked based on the
  fairness gauge's output.
- The gauge is read-only, backward-looking, and observational.

This is deliberate, for two reasons:

1. **Correctness of individual decisions must not depend on group
   statistics.** Down-weighting or up-weighting an individual PA decision
   based on a cohort's aggregate approval rate would itself be a form of
   demographic-based decision-making — arguably worse, since it would be
   automatic and opaque rather than disclosed. AgenticPA's actual defense
   against bad automated decisions is the deterministic, per-case hard-gate
   logic in the Peer-Review Auditor (§7below), which looks at *evidence
   quality* (extraction confidence, cost variance, policy match
   confidence) — never at demographics.
2. **A dashboard-only implementation is honest about what it is.** Building
   an automatic "corrective" mechanism on top of two proxy fields (age,
   coarse region) derived from a small dataset would create false
   confidence that the system is "fairness-corrected" when it has not been
   validated as such. Surfacing the disparity for human review/audit is a
   defensible, auditable design; silently correcting for it is not.

**In one sentence for a reviewer or stakeholder:** *AgenticPA detects and
discloses potential outcome disparity by age and region so a human
compliance reviewer can investigate it — it does not use demographic
proxies to make or alter any individual adjudication decision.*

---

## 6. Known limitations (state these proactively, don't wait to be asked)

| Limitation | Detail |
|---|---|
| No protected-class data | Race, ethnicity, sex/gender, disability, income are never captured. Age and ZIP-derived region are the only available proxies. |
| ZIP is a poor proxy for race/ethnicity | Using ZIP-code region as a demographic proxy is a widely-criticized practice in fairness literature (it can encode historical redlining patterns without being a clean substitute for any single protected attribute). Documented here explicitly so it is not overstated as more rigorous than it is. |
| Coarse granularity | 4 age buckets and up to 4 regions is not fine-grained; a single ZIP digit spans a huge and heterogeneous population per bucket. |
| No statistical significance testing | `approval_rate` is a raw proportion; there is no confidence interval, p-value, or multiple-comparison correction. `MIN_COHORT_SIZE = 3` is a floor against the worst noise, not a statistical guarantee of significance. |
| No intersectional analysis | Age and region are computed independently, not as an age×region cross-tab — a cohort that's simultaneously old *and* Southern isn't visible as its own bucket. |
| No feedback loop | As covered in §5, findings here don't change any decision. This is a monitoring tool, not a bias-correction system. |
| Small demo dataset | With only a handful of seeded Hero Cases, most cohorts will be dropped by the `MIN_COHORT_SIZE` threshold; the gauge only becomes meaningful at moderate case volume. |

---

## 7. Bias-adjacent safeguards elsewhere in the system (for completeness)

These don't touch demographics at all, but they are the system's actual
guardrails against a biased or wrong automated outcome, and are worth
citing alongside the fairness gauge since stakeholders often ask "so what
actually prevents a bad decision?":

- **`evaluate_hard_gates()`** (`peer_review_agent.py`) — pure deterministic,
  no LLM, no demographic input. Forces human review whenever:
  - `LOW_CONFIDENCE_EXTRACTION` — Intake's self-reported
    `extraction_confidence` is missing or below the admin-tunable
    `confidence_threshold` (default 0.85).
  - `FINANCIAL_EXCEPTION` — Cost agent flags `is_overcharge`
    (variance over the CMS benchmark exceeds 20%).
  - `RATE_UNAVAILABLE` — Cost agent could not resolve a CMS benchmark rate
    at all (never silently assumed fair).
  - `POLICY_AMBIGUOUS` — RAG agent's top policy match score falls below
    the `AMBIGUITY_THRESHOLD` (0.70).
- **LLM is never the sole gate.** Across Intake, Peer-Review, and
  Summarizer, the LLM is used only for extraction, rationale-writing, and
  plain-language translation. It can *add* an escalation reason but can
  never suppress an already-fired hard gate (`run_peer_review_agent` ORs
  the LLM's soft escalation into `needs_human_review`; hard gates stand
  even if the LLM call fails outright).
- **Fail-safe defaults everywhere.** Any agent failure (LLM timeout,
  malformed JSON, unresolved rate) defaults to the *more conservative*
  outcome — forcing human review or treating a value as unknown — never to
  silent auto-approval.

Together: the fairness gauge answers *"is there a disparity in aggregate
outcomes?"* and the hard gates answer *"is this specific case
well-evidenced enough to auto-decide?"* — they are complementary, not
substitutes for each other.

---

## 8. Test coverage

`backend/tests/test_fairness.py` covers:

- `bucket_age`: each of the 4 buckets, boundary ages, malformed/missing DOB
  → `None`.
- `bucket_region`: each ZIP-prefix digit mapping, missing/empty ZIP →
  `None`.
- `compute_fairness_cohorts`: cohorts below `MIN_COHORT_SIZE` are dropped;
  a valid cohort's `approval_rate` is computed correctly.

See `documents/test_cases/README.md` for scenario-level test cases (as PDFs
built from `.txt` source) that exercise fairness-relevant demographic
variety (different ages/regions) end-to-end through the real pipeline,
plus gaps the current automated suite doesn't cover yet (dual age+region
contribution from one case, cohort sort order, the `admin/metrics` API
wiring itself).
