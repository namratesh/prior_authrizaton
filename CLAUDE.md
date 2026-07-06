# CLAUDE.md — AgenticPA
 
## What we're building
AgenticPA: multi-agent Prior Authorization for UHG AARP Medicare. Clinical RAG + financial benchmarking + human-in-the-loop + self-improving feedback loop. Built for a hackathon — optimize for a tight, real, demoable end-to-end path over feature breadth.
 
---
 
## 🚨 NON-NEGOTIABLE RULES
1. **LLM is used for extraction (Intake), translation (Summarizer), AND reasoning/explainability (Peer-Review) — but never as the sole gate on a hard threshold.**
   - Deterministic hard-gates stay in code, not model calls: Cost's 20% variance threshold, RAG's 0.70 similarity threshold, Intake's 85% confidence threshold. These compute `needs_human_review` flags independently of any LLM.
   - Peer-Review's LLM reasoning layer synthesizes the three agents' structured outputs into a richer contradiction narrative + human-readable rationale (for the Reviewer's Rationale Panel) than a boolean check alone could catch.
   - **Asymmetric authority rule:** the LLM reasoning layer can only ADD reasons to escalate to human review — it can never suppress or downgrade a hard-gate flag back to auto-approve. This preserves "Absolute Human Primacy" and keeps the audit trail deterministic at its core, while adding real reasoning/explainability on top.
   - When asked "why agents, not one prompt": the deterministic hard-gates are the answer — they're what a single LLM call can't guarantee (consistent, auditable, non-hallucinated thresholds). The LLM reasoning layer is additive value, not a replacement for that guarantee.
2. **Real LangGraph interrupt.** Graph cannot transition Peer-Review → Summarizer if `needs_human_review == True`. Must be a true graph-level interrupt, not a UI-faked pause.
3. **Synthetic data only.** `Faker`-generated. No real PHI, ever.
4. **Code comments:** mark `// DEMO-REAL` vs `// DEMO-MOCKED` on every agent/feature so we never accidentally oversell to judges what's actually running live.
5. **One phase/agent at a time.** Don't scaffold the whole system from this doc in one shot — build and test each agent standalone before wiring the graph.
---
 
## Scope (locked)
**DEMO-REAL:** Intake → Cost → RAG (parallel) → Peer-Review contradiction check → human interrupt → Reviewer approve/modify → Summarizer → correction writeback → feedback-loop injection on next matching case. Reviewer Portal split-screen. Postgres `PostgresSaver` checkpointer.
 
**DEMO-MOCKED (build as hardcoded, not a TODO):**
- Alternative Therapy Mapper — 2-3 hardcoded biosimilar mappings.
- Bias & Fairness Gauge — static chart.
- Azure Document Intelligence fallback — skip, pdfplumber only.
- Auth — hardcode two roles (Patient, Reviewer), no real login.
- Patient/Admin portals — thin, just enough to serve the demo beats below.
- "Chain-of-Thought toggle" (referenced in demo beat 5) — **not yet defined**; either scope this as a simple static reveal of the agent trace JSON already in Admin, or cut it from the script. Don't leave it undefined going into build.
---
 
## 🎨 UI Theme (Sapient + UHG)
- Colors: Radiant Red `#E00000` (CTAs/urgency), White `#FFFFFF`, Black `#1A1A1A`, Surface `#F5F7FA`, Border `#E5E7EB`.
- Font: `Inter` (Tailwind default).
- Components: clean cards (`rounded-lg shadow-sm p-6`), generous spacing.
- Reviewer split-screen: Left 40% PDF viewer (CPT=yellow, ICD-10=blue, price=red highlights) · Middle 30% editable form · Right 30% Rationale Panel (EOC citation + cost formula + step-therapy timeline).
---
 
## Architecture
- **State**: `AgenticPAState` (Pydantic) — Clinical Payload, Financial Payload, Policy Payload, Routing Payload, Audit Payload. Build this first.
- **6 agents + Supervisor**: Clinical Intake & Normalizer, AARP Medicare RAG, Cost Intelligence & Benchmarking, Alternative Therapy Mapper (mocked), Peer-Review Compliance Auditor, Dual-Output Summarizer, plus SLA-aware Supervisor/orchestrator.
- **Stack**: FastAPI + LangGraph (`PostgresSaver`) + Qdrant (policy vectors, 1 EOC/SOB doc subset is enough) + Redis (10-15 hardcoded CMS rates) + PostgreSQL (`cases`, `audit_logs` insert-only, `feedback_corrections`) + React 19/TS/Vite/Tailwind/Shadcn/`react-pdf`/`recharts` + Zustand + React Router.
- **LLM providers**: multi-provider setup — Gemini (key loaded from `.env` as `GEMINI_KEY`, never hardcoded or logged) used for RAG's embedding generation. ⚠️ **Open item**: confirm Gemini's role is embeddings-only vs. also generation within the RAG agent — if generation, it needs the same asymmetric-authority treatment as Peer-Review's reasoning layer (rule 1), since RAG is otherwise marked retrieval-only/no-decision-making. Other agents (Intake extraction, Summarizer, Peer-Review reasoning) — confirm which provider each uses; don't assume all default to one model.
## 🖥️ Page-Wise UI Specs (fields decided against AgenticPAState + demo script needs)
 
### 👤 Patient Portal — 3 views
 
**View 1: Submission**
- Drag-and-drop PDF upload zone (large, centered, Radiant Red border on hover).
- Auto-populated fields (read-only, pulled from synthetic patient record): Patient Name, DOB, Member ID, Zip Code.
- Requested Service field (free text, populated post-extraction — shown as "detected" after upload, not before).
- Submit button → calls `/api/v1/upload`.
**View 2: Living Timeline** (post-submission, polls `/api/v1/status/{case_id}`)
- Horizontal step tracker: Intake → Cost Check → Policy Check → Review → Decision.
- Current active step pulses/highlights; completed steps show checkmark.
- Status label per step (e.g., "Cost Agent reviewing...", "Awaiting reviewer — your case needs a closer look").
- **Cost Transparency Card**: estimated out-of-pocket cost, shown as soon as Cost Agent completes (before final decision) — pulled from Redis-cached `get_cms_rate` result, not the full adjudicated amount.
**View 3: Decision Inbox**
- List of past cases (case ID, date, service, status badge: Approved/Denied/Needs Info).
- Click into a case → Plain-English Decision Letter (from Summarizer), cost breakdown, next steps.
- "Ask a Human" button → opens a stub secure message thread (doesn't need real backend messaging — visual only is fine, mark `// DEMO-MOCKED`).
---
 
### 👩‍⚕️ Reviewer Portal — single split-screen view (Priority #1)
 
**Left 40% — PDF Viewer**
- Rendered PDF (`react-pdf`) with AI-highlighted regions: CPT codes (yellow), ICD-10 codes (blue), price/dollar mentions (red).
- Page navigation controls.
**Middle 30% — Editable Form**
- Fields, all pre-filled with AI-extracted values and editable: CPT Code, ICD-10 Code, Billed Amount, Patient Zip, Provider NPI, Requested Service Description.
- Each field shows a small confidence indicator (from Intake's extraction confidence) next to it.
- Any edit here is what feeds the `ReviewerCorrection` diff on submit.
**Right 30% — Rationale Panel**
- **Contradiction Banner** (yellow, pulsing if `needs_human_review == True`): shows `interrupt_reason` text plus the LLM-generated rationale from Peer-Review.
- **Policy Citation Block**: retrieved EOC/SOB clause text, source filename, page number, similarity score.
- **Cost Formula Breakdown**: `Billed Amount` vs `CMS Rate` with the formula shown on hover: `(Work RVU × Work GPCI + PE RVU × PE GPCI + MP RVU × MP GPCI) × CF`, variance %.
- **Step-Therapy/Alternative Panel**: if Alternative Mapper fired, shows requested vs. alternative side-by-side with net savings.
- **Priority Badge**: pulsing red "Expedite" banner if within 2h of SLA deadline (from Supervisor).
**Actions (bottom bar, always visible)**
- *Approve as Is* / *Modify & Approve* / *Request Clarification* (opens free-text note to provider) / *Override to Deny* (requires mandatory free-text justification — button disabled until text entered).
---
 
### 📊 Admin Portal — single dashboard view (kept thin per scope)
 
- **Leakage Prevented ($LFT) Counter**: large number, ticks up in real time as cases resolve with cost adjustments. Pulled from `/api/v1/admin/metrics`.
- **Accuracy Drift Line Chart** (`recharts`): `(1 - reviewer_overrides/total_cases)` over last 7 days, trending upward.
- **Agent Trace Explorer**: collapsible tree per case ID — each node shows agent name, execution time, and (if CoT toggle is kept — see open item) the raw prompt/response for that node's LLM call.
- **Bias & Fairness Gauge**: static/mocked bar chart, approval rate by synthetic age/region cohort — mark `// DEMO-MOCKED`.
- **Case List Table**: case ID, status, SLA countdown, flags fired (badges for FINANCIAL_EXCEPTION / POLICY_AMBIGUOUS / low-confidence).
| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/upload` | Upload PDF → returns `case_id` |
| GET | `/api/v1/status/{case_id}` | Poll current phase |
| GET | `/api/v1/review/{case_id}` | Full state for split-screen |
| POST | `/api/v1/review/{case_id}/adjudicate` | Submit reviewer decision + diffs |
| GET | `/api/v1/admin/metrics` | LFT + accuracy drift + trace |
## 📁 Repo Structure
```
agentic-pa/
├── backend/app/
│   ├── agents/          # LangGraph nodes
│   ├── core/            # State + graph builder
│   ├── db/               # Postgres models
│   ├── api/              # FastAPI routes
│   └── utils/            # pdfplumber
├── frontend/src/
│   ├── pages/            # Patient, Reviewer, Admin
│   ├── components/       # SplitScreen, Timeline, LFT
│   └── store/            # Zustand
└── docker-compose.yml
```
 
---
 
## 🔁 The Differentiator (protect above all else)
Reviewer corrections stored keyed by `(icd10_family, cpt_family)`. Next case sharing an ICD-10 family → Intake vector-searches this table and injects top-3 as few-shot examples. **Must demo with 2 sequential cases** — one producing a correction, one visibly using it. Ensure the seed data actually varies the corrected field (e.g., CPT) between the two cases, or there's nothing to show.
 
## 🧪 5 Hero Cases (pre-seed exactly these — UPDATED with real RVU-priced CPTs + real zips)
Original CPTs (drugs/DME: J2357, E0784, J7326) were swapped — CMS prices drugs/DME via ASP/DMEPOS systems not present in our local RVU files. These are real CPT codes priced via actual RVU×GPCI×CF math against backend/data/rates files, not fabricated.
 
| ID | Scenario | ICD-10 | CPT | Zip→Locality | Billed | CMS Rate | Variance | Behavior |
|---|---|---|---|---|---|---|---|---|
| PA-001 | Clean | J45.909 | 31626 (Bronchoscopy w/markers) | 90210→CA-18 | $850 | $1,002.83 | -15.2% | Approve |
| PA-002 | Overcharge | E11.9 | 0446T (Implantable glucose sensor insertion) | 36104→AL-00 | $12,000 | $5,533.81 | +116.9% | Interrupt (overcharge) |
| PA-003 | Missing info | I10 | 93784 (Ambulatory BP monitor) | 10001→NY-01 | $2,500 | $54.71 | +4469% | Interrupt (low confidence **and** overcharge — see open item below) |
| PA-004 | Alternative | M17.9 | 27447 (Total knee arthroplasty) | 60601→IL-16 | $8,000 | $1,339.63 (⚠️ verify — see open item) | +497% | Interrupt (overcharge/alt.) |
| PA-005 | Feedback demo | J45.909 | 31626 (same as PA-001) | 30301→GA-01 | $900 | $884.40 | +1.8% | Approve, uses PA-001's correction |
 
**zip_county_subset.csv** (5-row bridge, general public geography, not CMS-sourced — marked `// DEMO-REAL (zip→county is general geography, not CMS-sourced; scoped to Hero Cases only)`):
90210→Los Angeles County, CA · 36104→Montgomery County, AL · 10001→New York County, NY · 60601→Cook County, IL · 30301→Fulton County, GA
 
**CMS_CONVERSION_FACTOR_2026 = 33.4009** — read directly from the RVU file's own CONV FACTOR column (constant across all rows in the 2026 non-anesthesia file), not supplied externally.
 
### ⚠️ OPEN ITEMS — resolve before Step 9 (Peer-Review)
1. **PA-004's rate needs a facility-vs-non-facility check.** CPT 27447 (TKA) is almost always facility-based; $1,339.63 looks implausibly low for a knee replacement even accounting for professional-component-only pricing. Check whether PPRRVU2026_Jan_nonQPP has separate Facility/Non-Facility PE RVU columns and confirm the right one is being used before trusting this number in front of judges.
2. **PA-004's "Alternative Therapy" narrative no longer matches the original biologic/biosimilar story** (charter's demo script was built around a drug substitution). Since PA-004 is now a procedure (TKA), the Alternative Therapy Mapper (mocked, Step 8) needs to be reframed as a *procedure* alternative (e.g., less invasive intervention) rather than a drug-to-biosimilar swap — **decision still pending**, do not build Step 8's mock logic until this is locked.
3. **PA-003 now triggers both low-confidence (Intake) and overcharge (Cost) simultaneously** (+4469% variance). Decide whether this dual-trigger is acceptable (both agents legitimately flagging) or whether PA-003 needs a cleaner single-cause scenario for demo clarity.
## 🎬 Demo Script (7 beats — must work live, 3x rehearsed, recorded fallback ready)
1. Patient upload (PA-002).
2. Admin trace view — parallel agents firing, interrupt trigger visible.
3. Reviewer — yellow contradiction banner, opens split-screen.
4. Reviewer — edits CPT, hovers cost formula, clicks "Modify & Approve."
5. Admin — LFT ticks up, accuracy drift updates. (Cut or define the CoT toggle before this is final.)
6. Patient — opens empathetic letter.
7. Admin — submit PA-005, show few-shot injection sourced from PA-001.
---
 
## Build Order (strict, one step at a time via Claude Code)
1. Zustand + React Router (3 pages, empty shells).
2. FastAPI + Postgres schema + `AgenticPAState`.
3. Agents standalone, in order: Intake → Cost → RAG → Alternative (mock) → Peer-Review → Summarizer.
4. Wire LangGraph (conditional edges + checkpointer), test end-to-end on one seeded case.
5. Reviewer Split-Screen (priority #1 UI).
6. Remaining API endpoints.
7. Feedback loop (correction capture + injection).
8. Patient Timeline + thin Admin.
9. Seed 5 Hero Cases.
10. Rehearse demo 5x, prep recorded fallback.
