# AgenticPA Test Case Suite — Test Plan

This directory contains **synthetic** Prior Authorization request documents
(`.txt`, one per scenario) meant to be converted to PDF and uploaded through
the Patient Portal (`POST /api/v1/upload`) to exercise every decision branch
in the pipeline end-to-end: Intake extraction → Cost/RAG/Alternative fan-out
→ Peer-Review hard gates → human review (where applicable) → Summarizer.

**No real PHI.** All names, DOBs, NPIs, and case details are fabricated,
following the same convention as `backend/scripts/seed_hero_cases.py`.

**How to use:** convert each `.txt` to PDF (e.g., print-to-PDF, `pandoc`, or
any text→PDF tool), then upload via the Patient Portal submission form,
pairing it with the **query** listed in the table below (the query drives
Intake's `relevant_agents` classification — it must be submitted with the
PDF, not left blank).

**Important caveat on demo data dependency:** several scenarios below
(overcharge, rate-unavailable, policy-ambiguous, step-therapy, alternative
therapy) depend on which CPT/ICD codes and ZIP codes are represented in the
seeded `RvuValue`/`GpciValue`/`ZipLocality`/Qdrant EOC corpus at the time
you run them. The 5 "hero" ZIPs known to resolve rates are `90210`, `36104`,
`10001`, `60601`, `30301` (see `backend/scripts/seed_hero_cases.py`). If your
local seed data differs, an "overcharge" scenario may instead land as
"rate unavailable" or vice versa — check the actual `financial_payload` in
the Reviewer Portal / `GET /review/{case_id}` response and adjust billed
amounts/ZIPs to match your environment if needed.

---

## Scenario index

The `.txt` files contain **only the document body** (what the intake LLM
sees) — submit each together with the **query** listed below in the Patient
Portal's submission form.

| # | File | Query to submit | Hard gate(s) expected | Also exercises |
|---|---|---|---|---|
| 01 | `01_clean_auto_approve.txt` | "Please check whether this bronchoscopy procedure is covered under my plan and whether the billed amount is reasonable." | none — should auto-approve | Full happy path, all 3 agents relevant |
| 02 | `02_low_confidence_handwritten.txt` | "Is this ambulatory blood pressure monitor covered by my plan?" | `LOW_CONFIDENCE_EXTRACTION` | Illegible/ambiguous handwritten-style field extraction |
| 03 | `03_extraction_failure_garbled.txt` | "What is this bill for and is it covered?" | `LOW_CONFIDENCE_EXTRACTION` (forced, confidence=0.0) | Intake fail-safe on near-total extraction failure |
| 04 | `04_financial_overcharge.txt` | "Is this glucose sensor insertion covered, and does the billed cost look right compared to what Medicare usually pays?" | `FINANCIAL_EXCEPTION` | Cost variance % calculation (>20% threshold) |
| 05 | `05_rate_unavailable_unknown_zip.txt` | "Please check whether this procedure's cost is reasonable." | `RATE_UNAVAILABLE` | CMS rate lookup miss (ZIP outside known localities) |
| 06 | `06_policy_ambiguous_obscure_service.txt` | "Is this experimental treatment covered under my plan?" | `POLICY_AMBIGUOUS` | RAG low-confidence match (<0.70) |
| 07 | `07_combined_worst_case.txt` | "Please review this request fully — coverage, cost, and any alternatives." | all 4 hard gates simultaneously | Multiple flags + LLM additional-escalation reasoning |
| 08 | `08_alternative_therapy_knee.txt` | "Please review whether this knee replacement is covered, whether the billed cost is fair, and whether there's a lower-cost alternative I should try first." | none expected, or `FINANCIAL_EXCEPTION` depending on billed amount vs. local benchmark | Alternative Therapy Mapper (knee arthroplasty → conservative injection) |
| 09 | `09_step_therapy_biologic.txt` | "Do I need to try anything else before this medication is approved?" | possibly `POLICY_AMBIGUOUS` depending on corpus match | `step_therapy_required` / `step_therapy_timeline` fields |
| 10 | `10_clearly_excluded_service.txt` | "Is this cosmetic procedure covered by my plan?" | none automatically — tests reviewer's manual "Override to Deny" path | Deny adjudication + mandatory justification, `FeedbackCorrection` recording |
| 11 | `11_clarify_missing_info.txt` | "Can you check if this request is complete and covered?" | likely `LOW_CONFIDENCE_EXTRACTION` or none | Reviewer "Request Clarification" self-loop, `case_status="awaiting_provider_response"` |
| 12 | `12_expedite_sla_timing.txt` | "This is time-sensitive, please review quickly." | none (timing test, not content) | SLA/expedite banner — see "Non-document test" note below |
| 13 | `13_fairness_under65.txt` | "Please check whether this is covered." | none expected | Fairness cohort: "Under 65" + region |
| 14 | `14_fairness_age_65_74.txt` | "Please check whether this is covered." | none expected | Fairness cohort: "Age 65-74" |
| 15 | `15_fairness_age_75_84.txt` | "Please check whether this is covered." | none expected | Fairness cohort: "Age 75-84" |
| 16 | `16_fairness_age_85_plus.txt` | "Please check whether this is covered." | none expected | Fairness cohort: "Age 85+" |
| 17 | `17_fairness_region_northeast.txt` | "Please check whether this is covered." | none expected | Fairness cohort: "Northeast" (ZIP prefix 0/1) |
| 18 | `18_fairness_region_west.txt` | "Please check whether this is covered." | none expected | Fairness cohort: "West" (ZIP prefix 8/9) |
| 19 | `19_missing_dob_and_zip.txt` | "Please check whether this is covered." | likely `LOW_CONFIDENCE_EXTRACTION` | `bucket_age`/`bucket_region` both return `None` — case excluded from all fairness cohorts |
| 20 | `20_multi_code_stress_test.txt` | "Please review full coverage and cost for all items on this request." | none expected, or `POLICY_AMBIGUOUS` if RAG can't disambiguate | Multi-value ICD-10/CPT list extraction (6 codes) |

That's 20 document-based scenarios (exceeds the ~15-18 target to leave
margin for demo-data variance). Scenarios 13-19 are designed to be run
**together, 3+ times each with varied outcomes** (some approved, some
denied via reviewer override) so that each age/region cohort accumulates
enough finalized cases to clear `MIN_COHORT_SIZE = 3` and actually appear
on the Bias & Fairness Gauge — a single run of each won't be enough on its
own. See §"Building a fairness-cohort dataset" below.

---

## Non-document tests (not representable as a PDF's text — test via `curl`/API directly)

| Scenario | How to test | Expected result |
|---|---|---|
| Oversized upload | `POST /api/v1/upload` with a PDF > 15MB | 4xx rejection, no case created |
| Wrong content-type | Upload a `.docx` or `.txt` renamed to `.pdf`, or a non-PDF `Content-Type` | 4xx rejection |
| Rate limit — upload | Fire 11+ `POST /upload` requests within 60s from the same IP | 11th+ request gets `429 Too Many Requests` |
| Rate limit — assign | Fire 31+ `POST /review/{id}/assign` within 60s | 31st+ gets `429` |
| Rate limit — adjudicate | Fire 61+ `POST /review/{id}/adjudicate` within 60s | 61st+ gets `429` |
| Double-assign conflict | Two different `reviewer_id`s call `assign` on the same unassigned case | Second call gets `409 Conflict` |
| Admin settings — confidence threshold | `PUT /admin/settings {"confidence_threshold": 0.99}`, then re-run scenario 01 | Previously-clean case now trips `LOW_CONFIDENCE_EXTRACTION` (threshold now stricter than the LLM's reported confidence) |
| Admin settings — disable agent | `PUT /admin/settings {"agents_enabled": {"cost": false, "rag": true, "alternative": true}}`, then upload scenario 04 (overcharge) | `FINANCIAL_EXCEPTION` does **not** fire even though the query asks about cost — cost agent is admin-disabled regardless of query classification |
| Fairness API wiring | `GET /api/v1/admin/metrics` after finalizing 3+ cases per cohort | `fairness_cohorts` non-empty, `fairness_finalized_total` matches total finalized case count |
| Audit-log immutability | Attempt a direct `UPDATE`/`DELETE` on `audit_logs` via psql | Rejected by the DB trigger installed in the initial migration |

---

## Building a fairness-cohort dataset (for scenarios 13-19)

`compute_fairness_cohorts` drops any cohort under 3 finalized cases. To see
real bars on the Bias & Fairness Gauge:

1. Upload scenario 13 three times with **three different ZIPs**, one in
   each of 3 different regions, so "Under 65" accumulates 3 cases while
   simultaneously seeding 3 different region cohorts a little.
2. Do the same for 14, 15, 16 (one age bucket at a time).
3. For clean region cohorts, vary DOB across the 4 age buckets while
   holding ZIP prefix constant per scenario 17 / 18 (repeat with 2 more
   ZIPs starting with the same digit but different, e.g. `02134`, `10001`,
   `19104` all start with `0`/`1` → "Northeast").
4. Adjudicate each case to a **terminal** `final_status` (Approve or Deny)
   — cases stuck in `needs_human_review` with no decision yet don't count
   (`final_status` must be non-NULL). Mix in a few denials (e.g. via
   scenario 10's manual override) so approval rates aren't uniformly 100%
   across every cohort — a dashboard where every bar reads 100% doesn't
   exercise the "disparity" visualization meaningfully.

---

## Expected hard-gate reference (for grading results)

From `backend/app/agents/peer_review_agent.py`, `confidence_threshold`
defaults to **0.85**, `OVERCHARGE_THRESHOLD_PERCENT` is **20.0%**,
`AMBIGUITY_THRESHOLD` is **0.70**. All three are admin-tunable at
`PUT /api/v1/admin/settings` — if you've changed them locally, adjust
expectations accordingly.
