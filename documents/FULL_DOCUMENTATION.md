# AgenticPA (PA_Advisor) — Full System Documentation

## 1. What this system is

AgenticPA is a multi-agent Prior Authorization (PA) processing system built
for a Medicare-Advantage-style plan (AARP Medicare, per the demo/hackathon
framing). A patient uploads a PA request document (clinical note + billing
sheet, as a PDF) along with a free-text description of what they're asking
about. The system automatically:

1. Extracts structured clinical/billing data from the document.
2. Benchmarks the billed cost against real CMS Physician Fee Schedule rates.
3. Checks the requested service against the plan's Evidence of
   Coverage/Summary of Benefits (EOC/SOB) policy documents via retrieval.
4. Suggests a lower-cost clinically-equivalent alternative when one exists.
5. Applies deterministic compliance rules ("hard gates") to decide whether
   the case can auto-resolve or must go to a human reviewer.
6. If routed to a human, presents a split-screen Reviewer Portal (PDF +
   editable extracted fields + rationale) supporting Approve /
   Modify & Approve / Deny / Request Clarification.
7. Produces a plain-English decision letter (readability-targeted) for the
   patient, and a FHIR-shaped audit stub.
8. Tracks SLA deadlines and expedite status throughout.
9. Records every reviewer correction into a feedback table so future
   extractions on similar codes get few-shot-corrected.
10. Surfaces system-level oversight (leakage prevented, accuracy drift,
    bias/fairness cohort disparity, per-segment override rates) on an Admin
    Portal.

**Every mocked component is explicitly labeled** `// DEMO-MOCKED` in code
comments (currently: the Alternative Therapy Mapper's lookup table, the
FHIR stub's schema fidelity, and the 3 hardcoded demo user identities used
in place of real auth). Everything else — cost math, policy retrieval,
hard-gate logic, fairness cohort computation, SLA/settings, the feedback
loop — runs on real logic against real (synthetic, non-PHI) data, and is
labeled `// DEMO-REAL`.

---

## 2. Architecture

### 2.1 Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI |
| Orchestration | LangGraph (`StateGraph`, `PostgresSaver` checkpointer, real `interrupt()`) |
| Database | PostgreSQL (SQLAlchemy ORM), Alembic migrations |
| Vector search | Qdrant (hybrid dense + sparse) over ingested EOC/SOB policy chunks |
| Rate data | CMS Physician Fee Schedule CSVs (RVUs, GPCIs, locality/county mapping) loaded into Postgres |
| Rate limiting | `slowapi` (IP-keyed) |
| LLM | Pluggable via `LLM_PROVIDER` env var: Gemini / OpenAI / Bedrock Claude, behind a single `app/core/llm_client.py` interface |
| Frontend | React 19 + TypeScript + Vite + Tailwind + Zustand + React Router |
| Frontend data viz | Recharts (Admin Portal charts) |

### 2.2 High-level flow

```
Patient uploads PDF + query
        │
        ▼
   POST /api/v1/upload  ──►  background task: start_case()
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│                      LangGraph state machine                │
│                                                              │
│   START ──► intake ──► route_after_intake                   │
│                            │                                │
│              ┌─────────────┼─────────────┐                  │
│              ▼             ▼             │                  │
│         cost_node     rag_node           │  (parallel        │
│              │             │             │   superstep,      │
│              └──────┬──────┘             │   query-routed)   │
│                     ▼                                       │
│              alternative_node (join; optional Alt. Therapy)  │
│                     │                                       │
│                     ▼                                       │
│              peer_review (hard gates + rationale)            │
│                     │                                       │
│         needs_human_review? ──yes──► human_review (interrupt)│
│                     │no                    │ resumes on      │
│                     ▼                      │ adjudicate      │
│                summarizer  ◄───────────────┘                 │
│                     │                                       │
│                    END                                       │
└───────────────────────────────────────────────────────────┘
```

State is a single Pydantic object, `AgenticPAState`
(`backend/app/core/state.py`), threaded through every node:

- **`ClinicalPayload`** — Intake's extracted fields: `patient_name`,
  `patient_dob`, `patient_zip`, `icd10_codes`, `cpt_codes`,
  `diagnosis_summary`, `prescribing_physician`, `provider_npi`,
  `requested_service_description`, `billed_amount`,
  `extraction_confidence`, `field_confidence` (per-field score for 6
  fields), `raw_document_text`, `few_shot_corrections_used`,
  `patient_query`.
- **`FinancialPayload`** — `billed_amount`, `cms_benchmark_rate`,
  `variance_amount`, `variance_percent`, `is_overcharge`,
  `alternative_therapy_suggestion`, `alternative_therapy_savings`.
- **`PolicyPayload`** — `eoc_citations`, `matched_policy_clauses`,
  `step_therapy_required`, `step_therapy_timeline`,
  `policy_match_confidence`, `policy_ambiguous`.
- **`RoutingPayload`** — graph-control state: `current_phase`,
  `needs_human_review`, `interrupt_reason`, `reviewer_id`,
  `reviewer_decision`, `diffs`, `final_status`, `sla_deadline`,
  `case_status`, `relevant_agents`, `query_classification_reason`.
- **`AuditPayload`** — insert-only: `agent_trace` (list of trace entries,
  one per agent invocation), `feedback_corrections_used`,
  `decision_letter`, `fhir_stub`, timestamps.

The graph is compiled once per process (`get_compiled_graph()`) with a
`PostgresSaver` checkpointer, using a custom `JsonPlusSerializer` so the
app's Pydantic state classes survive msgpack round-tripping. This means
`human_review_node`'s `interrupt()` call is a **real pause** — the process
can restart and the case resumes exactly where it left off, keyed by
`case_id` as the LangGraph `thread_id`.

`backend/app/core/case_runner.py` bridges the graph's own checkpoint state
to the queryable `cases`/`audit_logs` Postgres tables (the LangGraph
checkpoint itself isn't cheaply queryable for the Admin Portal's list/CSV
views). `start_case()` invokes the graph fresh; `resume_case()` sends a
`Command(resume=payload)` to continue a paused interrupt. `_persist()`
upserts the `cases` row and appends only newly-added `agent_trace` entries
into the insert-only `audit_logs` table.

### 2.3 Query-driven routing (not a fixed pipeline)

Every case's patient-submitted **query** (e.g. "is this covered and is the
price fair?") is classified by the Intake agent into a subset of
`{"cost", "rag", "alternative"}` — `relevant_agents`. `route_after_intake`
only fans out to the agents actually relevant to what the patient asked,
intersected with the admin's `agents_enabled` settings (an admin-disabled
agent can never run regardless of query classification). On any
classification failure, it fails safe to **all** agents rather than
silently skipping checks.

This has a direct effect on hard-gate evaluation: `FINANCIAL_EXCEPTION` and
`RATE_UNAVAILABLE` are only evaluated if `"cost"` was actually relevant (and
enabled); `POLICY_AMBIGUOUS` only if `"rag"` was relevant/enabled. An
irrelevant-but-unrun check cannot spuriously fire.

---

## 3. Agents (detailed)

### 3.1 Clinical Intake & Normalizer (`intake_agent.py`)

- LLM-only extraction (never decides anything downstream). Given raw PDF
  text + the patient's query, calls the LLM with a structured extraction
  prompt to populate all `ClinicalPayload` fields, plus a self-reported
  `extraction_confidence` (0-1) and per-field `field_confidence` for 6 of
  them.
- Also classifies the query into `relevant_agents` +
  `query_classification_reason` (a routing hint only — prompt explicitly
  says "when ambiguous, INCLUDE rather than skip").
- **Fail-safe on any exception** (timeout, malformed JSON, etc.):
  `extraction_confidence = 0.0` (forces human review downstream) and
  `relevant_agents = ALL_AGENTS` (never assumes something is irrelevant on
  failure).
- **Few-shot self-improvement**: a cheap regex extracts a candidate ICD-10
  code from the raw text before the LLM call; `get_few_shot_examples()`
  (in `feedback.py`) looks up up to 3 recent reviewer corrections sharing
  that ICD-10 family and folds them into the prompt as "avoid repeating
  this mistake" context. Tracked via `few_shot_corrections_used`.

### 3.2 Cost Intelligence & Benchmarking (`cost_agent.py`)

Pure deterministic math, **no LLM**. `run_cost_agent(billed_amount, cpt,
zip_code, db)`:

- Resolves the real CMS benchmark rate via `get_cms_rate(cpt, zip_code,
  db)` — `(Work RVU × Work GPCI + PE RVU × PE GPCI + MP RVU × MP GPCI) ×
  Conversion Factor`, using ingested RVU/GPCI/locality CSVs.
- If the CPT isn't RVU-payable or the ZIP doesn't resolve to a known
  locality → returns `cms_benchmark_rate=None`, `is_overcharge=None`
  ("rate unavailable" is a routing decision for the caller, never
  fabricated).
- Otherwise computes `variance_amount`, `variance_percent`, and
  `is_overcharge = variance_percent > 20.0` (`OVERCHARGE_THRESHOLD_PERCENT`).

### 3.3 AARP Medicare RAG (`rag_agent.py`)

Pure retrieval, **no LLM**. Hybrid (dense + sparse) Qdrant search
(`hybrid_search`) against ingested EOC/SOB policy chunks, built from a
query string composed of `diagnosis_summary` + ICD-10s + CPTs.

- `policy_ambiguous = True` when the top hit's score is below
  `AMBIGUITY_THRESHOLD = 0.70`, or when there are no hits at all.
- Returns `eoc_citations` (source + page), `matched_policy_clauses`,
  `policy_match_confidence` (top score), and `step_therapy_required` (true
  if any matched clause contains the phrase "step therapy").

### 3.4 Alternative Therapy Mapper (`alternative_agent.py`) — `DEMO-MOCKED`

A hardcoded lookup table of (ICD-10 family, CPT) → (alternative CPT,
description) — currently 3 entries, e.g. M17 (knee osteoarthritis) + 27447
(total knee arthroplasty) → 20610 (conservative injection). The **cost** of
the suggested alternative is computed via the same real CMS rate lookup
used by the Cost agent (this part is `DEMO-REAL`), so the savings number
shown is genuine even though the mapping itself is a small illustrative
table, not a clinical-guidelines engine.

### 3.5 Peer-Review Compliance Auditor (`peer_review_agent.py`)

Two strictly-ordered layers — this is the system's actual gate on
automated decisions:

**Layer 1 — `evaluate_hard_gates(state, confidence_threshold=0.85)`**
(pure deterministic, no LLM):

| Flag | Condition |
|---|---|
| `LOW_CONFIDENCE_EXTRACTION` | `extraction_confidence` is `None` or `< confidence_threshold` |
| `FINANCIAL_EXCEPTION` | Cost agent's `is_overcharge is True` (only if `"cost"` was relevant) |
| `RATE_UNAVAILABLE` | Cost agent's `is_overcharge is None` — rate never resolved (only if `"cost"` was relevant) |
| `POLICY_AMBIGUOUS` | RAG agent's `policy_ambiguous is True` (only if `"rag"` was relevant) |

Any fired flag sets `routing.needs_human_review = True`.

**Layer 2 — `generate_rationale(state, hard_gate_flags)`** (LLM
translation only): writes a human-readable rationale citing exact
numbers/codes/citations, and may propose *additional* soft
`additional_escalation_reasons`. Critically, the LLM's output is ORed into
`needs_human_review` — it can only **add** escalation, never remove a hard
gate that already fired. If the LLM call itself fails, hard-gate flags
still stand and `rationale` falls back to an error string.

### 3.6 Dual-Output Summarizer (`summarizer_agent.py`)

LLM translation only. Writes a plain-English decision letter targeting
Flesch Reading Ease > 60 (`FLESCH_TARGET`). If the LLM fails, or the
generated letter scores below target, falls back to a deterministic
`_template_letter`. Also builds a `DEMO-MOCKED` FHIR-shaped `ClaimResponse`
stub (illustrative structure, not schema-validated against the real FHIR
spec).

---

## 4. Human Review Workflow

`human_review_node` performs a real LangGraph `interrupt()`. The Reviewer
Portal (`frontend/src/pages/ReviewerPortal.tsx`) presents:

- **Case Queue**: My Queue / Unassigned / All tabs; claim/release a case
  (`POST /review/{id}/assign` — 409 if already claimed by someone else;
  `POST /review/{id}/unassign`).
- **Split-screen case detail**: PDF viewer (40%) / editable extracted
  fields with confidence badges (30%) / rationale panel (30%).
- **Actions** (`POST /review/{id}/adjudicate`):
  - `approve` — accept as-is.
  - `modify` — apply reviewer diffs to clinical fields, then approve; each
    diffed field is recorded as a `FeedbackCorrection` (keyed by ICD-10 /
    CPT family) feeding the Intake few-shot loop.
  - `deny` — requires a mandatory justification; also recorded as a
    correction.
  - `clarify` — self-loop: folds the reviewer's question into
    `interrupt_reason`, sets `case_status = "awaiting_provider_response"`,
    re-pauses. A demo-mocked "Mark Provider Responded" action
    (`provider_responded`) simulates the provider replying and re-pauses
    for the reviewer.
- **Rationale Panel**: expedite banner, "Needs Human Review" alert (hard
  gate flags + LLM rationale), policy citations, cost formula breakdown
  (with an RVU×GPCI tooltip), which checks actually ran (query-routed) +
  why, alternative therapy suggestion + savings, step-therapy timeline.

---

## 5. SLA & Expedite Logic (`supervisor.py`)

- `DEFAULT_SLA_HOURS = 48.0`, `DEFAULT_EXPEDITE_HOURS = 2.0` — fallback
  defaults only; the live values are admin-tunable via `settings_store`.
- `compute_sla_deadline(submitted_at, sla_hours)` → `submitted_at +
  timedelta(hours=sla_hours)`.
- `is_expedite(sla_deadline, now, expedite_hours)` → `True` if within
  `expedite_hours` of the deadline, or already past it.
- Surfaced to patients via `SlaCountdown.tsx` (always-visible countdown:
  "Overdue" / "Xh Ym left" / "Xd Yh left" / "Xm left", ticking every 30s)
  and an animated "being expedited" banner on `TimelineView.tsx`.

---

## 6. Admin-Tunable Settings (`settings_store.py`)

Backed by a single-row `admin_settings` Postgres table (JSONB for
`agents_enabled`), read fresh on every call (`get_settings(db)` — not
cached at process start, so a change takes effect on the *next* case, not
retroactively):

| Setting | Default | Effect |
|---|---|---|
| `sla_hours` | 48.0 | SLA deadline computation |
| `expedite_hours` | 2.0 | Expedite-window computation |
| `confidence_threshold` | 0.85 | Peer-Review's `LOW_CONFIDENCE_EXTRACTION` gate |
| `agents_enabled` | `{cost: true, rag: true, alternative: true}` | Admin on/off switch per downstream agent, intersected with query-based routing |

Exposed via `GET`/`PUT /api/v1/admin/settings`, edited from the Admin
Portal's `SystemConfigCard`.

---

## 7. Data Model (`backend/app/db/models.py`)

| Table | Purpose |
|---|---|
| `users` | Stub role table (`patient`/`reviewer`); no real auth — 3 demo identities seeded at startup |
| `cases` | One row per PA case: identity `case_number` (→ human-readable `PA-YYYY-NNNN`), current phase, final status, `needs_human_review`, assignment (reviewer + timestamp), 4 JSONB payload columns mirroring `AgenticPAState`, timestamps |
| `audit_logs` | Insert-only trace (agent, action, JSONB details, timestamp) — enforced insert-only by a DB trigger, not just app-layer discipline |
| `feedback_corrections` | Self-improving loop: ICD-10/CPT family (indexed, not unique), case, reviewer, corrected field, original/corrected value |
| `rvu_values` | CMS Physician Fee Schedule RVUs per CPT (work/PE/MP + status) |
| `gpci_values` | Geographic Practice Cost Indices per (state, locality) |
| `locality_counties` | State/locality → county mapping (MAC, fee schedule area) |
| `zip_localities` | ZIP → (county, state, locality) — currently only the 5 demo "hero" ZIPs |
| `admin_settings` | Single-row settings table backing `settings_store.py` |

---

## 8. API Surface (`backend/app/api/routes.py`, prefix `/api/v1`)

| Method | Path | Rate limit | Purpose |
|---|---|---|---|
| POST | `/upload` | 10/min | Validates PDF (content-type, ≤15MB), extracts text via `pdfplumber`, creates a case, kicks off `start_case()` as a background task, returns `case_id` immediately |
| GET | `/status/{case_id}` | — | Patient Timeline poll: phase, final_status, needs_human_review, case_status, interrupt_reason, estimated out-of-pocket, SLA deadline, `is_expedite` |
| GET | `/review/{case_id}` | — | Full case state for the Reviewer split-screen |
| GET | `/review/{case_id}/pdf` | — | Serves the raw uploaded PDF |
| POST | `/review/{case_id}/assign` | 30/min | Claim a case (409 if already claimed) |
| POST | `/review/{case_id}/unassign` | — | Release a case |
| GET | `/review/{case_id}/audit-export` | — | CSV of one case's agent trace |
| GET | `/admin/audit-export` | — | CSV across all cases |
| GET | `/admin/settings` | — | Current tunables |
| PUT | `/admin/settings` | — | Partial update of tunables |
| POST | `/review/{case_id}/adjudicate` | 60/min | Resume the paused interrupt (approve/modify/deny/clarify/provider_responded); records `FeedbackCorrection`s on modify/deny |
| GET | `/admin/metrics` | — | `leakage_prevented`, `accuracy_drift` (7-day), `fairness_cohorts` + `fairness_finalized_total`, optional `segments` (`group_by=provider\|service\|reviewer`), last 50 `cases` with flags/rationale |
| GET | `/health` (in `main.py`) | — | Liveness check |

Rate limiting (`slowapi`, IP-keyed) is scoped narrowly to the
highest-cost/most-exposed write endpoints (`upload`, `assign`,
`adjudicate`) on this unauthenticated demo deployment — it is not applied
globally.

---

## 9. Frontend

| Page/Component | Role |
|---|---|
| `patient/SubmissionView.tsx` | Two-step submission: free-text query (required, drives routing) → PDF upload |
| `patient/TimelineView.tsx` | Polls status every 2.5s until finalized; 5-step progress (Intake → Cost → Policy → Review → Decision), cost card, expedite banner |
| `patient/InboxView.tsx` | List of past submissions, empty state, click-through to decision detail |
| `ReviewerPortal.tsx` | Case Queue + split-screen review UI + action toolbar (approve/modify/deny/clarify) |
| `ReviewForm.tsx` | Editable extracted fields with per-field confidence badges (`ConfidenceBadge`: destructive <60%, warning 60-85%, success ≥85% — a **UI-only** threshold, separate from the backend's admin-tunable `confidence_threshold`) |
| `RationalePanel.tsx` | Hard-gate alert, policy citations, cost breakdown w/ RVU formula tooltip, which checks ran + why, alternative therapy, step-therapy timeline |
| `Timeline.tsx` | Patient-facing phase progress bar; never regresses visually on unrecognized phases |
| `SlaCountdown.tsx` | Always-visible SLA countdown |
| `AdminPortal.tsx` | KPI tiles, leakage tile, accuracy-drift chart, `BiasFairnessCard`, `SystemConfigCard`, `SegmentDrilldownCard`, `TraceExplorer`, `CaseListTable` |

---

## 10. Bias & Fairness

See **`documents/BIAS_FAIRNESS.md`** for the full deep dive. Summary:
`backend/app/core/fairness.py` computes real cohort approval-rate
disparity by age (from `patient_dob`) and coarse region (from
`patient_zip`'s first digit), dropping any cohort under 3 finalized cases
to avoid misleading small-sample rates. It is a **monitoring/disclosure**
feature only — it has zero coupling to the adjudication pipeline. The
system's actual defense against a bad automated decision is the
deterministic hard-gate logic in the Peer-Review Auditor (§3.5), which
never looks at demographics — only at evidence quality (extraction
confidence, cost variance, policy match strength).

---

## 11. Test Coverage

### Existing automated tests

| File | Covers |
|---|---|
| `backend/tests/test_fairness.py` | Age bucketing, region bucketing, cohort computation + small-sample dropping |
| `backend/tests/test_supervisor.py` | SLA deadline computation, expedite-window logic |
| `backend/tests/test_peer_review_agent.py` | `evaluate_hard_gates` — all 4 flags, query-relevance gating |
| `backend/tests/test_case_number.py` | Human-readable case number formatting |
| `frontend/src/components/ReviewForm.test.tsx` | `ConfidenceBadge` rendering thresholds |
| `frontend/src/components/SlaCountdown.test.tsx` | Countdown display branches |
| `frontend/src/lib/traceSummary.test.ts` | Trace-entry summarization for intake/cost/peer-review branches |

### Known gaps (not currently covered by automated tests)

- `cost_agent.py`, `rag_agent.py`, `alternative_agent.py`,
  `summarizer_agent.py`, `feedback.py`, `settings_store.py`,
  `rate_limit.py`, `case_runner.py` — no backend unit tests.
- `routes.py` — no API-level tests (upload, status, review, assign,
  adjudicate, audit-export, admin endpoints).
- `generate_rationale` / `run_peer_review_agent` — the LLM-escalation-only-
  adds behavior and fail-safe-on-LLM-exception path are untested.
- Frontend: `AdminPortal.tsx`, `ReviewerPortal.tsx`, patient portal views,
  `RationalePanel.tsx`, `Timeline.tsx`, and `ReviewForm.tsx`'s field-editing
  behavior (beyond the `ConfidenceBadge` sub-component) are untested.

### Manual scenario coverage

See **`documents/test_cases/README_TEST_PLAN.md`** for 20 synthetic
document scenarios plus a set of API-level (non-document) tests covering
upload validation, rate limiting, assignment conflicts, admin-settings
effects, and fairness-cohort accumulation — designed to exercise every
hard gate, the alternative therapy mapper, step therapy, the clarify loop,
and every fairness age/region bucket at least once.

---

## 12. Running Locally

See the repository root `README.md` for full setup (prerequisites, env
files, Alembic migration, hero-case seeding, dev servers) and
`.claude/skills/run-agenticpa/SKILL.md` for a scripted local-stack
bring-up (Postgres/Redis/Qdrant via Docker + FastAPI backend + Vite
frontend) used to verify changes end-to-end. Backend runs under the conda
environment `pa_hack`, not system/base Python.

Demo login: 3 hardcoded roles (`patient_demo`, `reviewer_demo`,
`admin_demo`) — auth is mocked, not real, for this demo deployment. All
seed/demo data is synthetic (Faker-generated); no real PHI is used or
stored anywhere in this repository.

---

## 13. Terminology Quick Reference

| Term | Meaning |
|---|---|
| Hard gate | A deterministic, non-LLM rule in `evaluate_hard_gates` that forces human review |
| Soft escalation | An *additional* reason for review proposed by the rationale LLM — can only add, never remove, a hard gate |
| DEMO-REAL | Code comment marker: this logic runs against real computed/retrieved data |
| DEMO-MOCKED | Code comment marker: this logic is an illustrative stand-in (hardcoded table, unvalidated schema, fake auth) |
| Cohort | A fairness-gauge grouping (one age bucket or one region) with ≥3 finalized cases |
| Finalized case | A case whose `final_status` is `Approved` or `Denied` (not NULL) |
| Interrupt | A real LangGraph pause (`human_review_node`), checkpointed to Postgres, resumable across process restarts |
