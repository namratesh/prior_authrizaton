# AgenticPA MVP Cases — Approved / Rejected / Info Needed / Human Approval

Six MVP Prior Authorization cases built to show the full reasoning chain in
one sitting: document-grounded coverage decisions (real AARP Medicare EOC
language via RAG), CMS-CSV-based cost math (real RVU/GPCI files run through
the actual Medicare payment formula), and every terminal outcome the
reviewer pipeline supports.

Unlike the QA suite in `documents/test_cases/` (20 scenarios covering every
hard gate in isolation for testing), these 6 are curated for a live MVP
narrative and are all grounded in real source documents:

- **Policy/coverage reasoning** comes from `aarp_policies/AATX26LP0337564_001.pdf`
  (2026 Evidence of Coverage, AARP Medicare Advantage Patriot No Rx TX-MA05),
  already ingested into the `aarp_policies` Qdrant collection. RAG citations
  in the MVP below quote the actual EOC page numbers.
- **Cost reasoning** comes from the real CMS files in `backend/data/rates/`
  (`PPRRVU2026_Jan_nonQPP.csv` for RVUs, `GPCI2026.csv` for geographic
  adjustment, `26LOCCO.csv` for locality lookup), run through the formula in
  `backend/app/core/cms_rates.py`:

  ```
  rate = (work_rvu * work_gpci + pe_rvu * pe_gpci + mp_rvu * mp_gpci) * 33.4009
  ```

PDFs for all 6 cases are already generated in `documents/mvp_pdfs/` (see
"Generating the PDFs" below to regenerate). Zip codes reuse the 5 known-good
localities from `backend/scripts/seed_hero_cases.py` /
`backend/app/data/zip_county_subset.csv` (`90210`, `36104`, `10001`, `60601`,
`30301`) so CMS rate lookups resolve without needing to extend that CSV.

---

## Case index

| # | Key | Outcome | PDF | Hard gate expected |
|---|---|---|---|---|
| 1 | PA-101 | **Approved** | `PA-101_hip_replacement_request.pdf` | none, or a minor gate resolved by reviewer approve |
| 2 | PA-102 | **Rejected — policy exclusion** | `PA-102_vasectomy_request.pdf` | POLICY_AMBIGUOUS may fire; denied by reviewer citing EOC exclusion |
| 3 | PA-103 | **Rejected — medical necessity mismatch** | `PA-103_lumbar_decompression_request.pdf` | LLM additional-escalation reason (diagnosis/procedure mismatch); denied by reviewer |
| 4 | PA-104 | **Rejected — cost-based** | `PA-104_endoscopy_request.pdf` | `FINANCIAL_EXCEPTION` (~1,050% over benchmark); denied by reviewer |
| 5 | PA-105 | **Info Needed** | `PA-105_knee_injection_intake.pdf` | `LOW_CONFIDENCE_EXTRACTION`; reviewer issues `clarify` |
| 6 | PA-106 | **Human Approval Required** | `PA-106_knee_replacement_request.pdf` | `FINANCIAL_EXCEPTION` (~49% over benchmark); left **pending**, not resolved |

Submit each PDF through the Patient Portal upload form **together with its
query** (query drives Intake's `relevant_agents` routing — it must not be
left blank).

---

## 1. PA-101 — Approved

**Patient:** Dorothy Mensah, DOB 1950-02-11, Zip 90210 (Los Angeles County, CA)
**Diagnosis:** M16.11 — unilateral primary osteoarthritis, right hip
**Requested service:** Total hip arthroplasty (CPT 27130)
**Billed:** $1,300.00
**Query:** *"Please check whether this hip replacement is covered under my plan and whether the billed amount is reasonable."*

**Why it's grounded, not scripted:**
- Diagnosis and procedure are clinically consistent (hip OA → hip replacement) — clinical logic has nothing to flag.
- CMS benchmark math (locality 18, Los Angeles-Long Beach-Anaheim):
  - Work RVU 19.11 × GPCI 1.041 = 19.893
  - PE RVU 11.63 × GPCI 1.183 = 13.758
  - MP RVU 4.05 × GPCI 0.664 = 2.689
  - Total RVU-adjusted = 36.34 × $33.4009 conversion factor ≈ **$1,213.90 benchmark**
  - Billed $1,300 vs. benchmark $1,213.90 → **+7.1% variance**, well inside the 20% `FINANCIAL_EXCEPTION` threshold.
- RAG retrieves the EOC's covered-services language for medically necessary joint replacement (Chapter 4 Medical Benefits Chart) — no exclusion, no ambiguity.

**Expected MVP flow:** case may still pause on a minor/soft gate (e.g. extraction confidence) — if so, resolve with reviewer action `approve`, citing the clean diagnosis/procedure match and the 7.1% variance. `final_status="Approved"`.

---

## 2. PA-102 — Rejected (policy exclusion)

**Patient:** Marcus Delaney, DOB 1962-07-30, Zip 36104 (Alabama, statewide locality)
**Diagnosis:** Z30.2 — encounter for sterilization
**Requested service:** Vasectomy, unilateral or bilateral (CPT 55250)
**Billed:** $350.00
**Query:** *"Is this vasectomy procedure covered under my plan?"*

**Why it's grounded, not scripted:**
- The EOC (`AATX26LP0337564_001.pdf`, page 118, "Services not covered by Medicare" table) states verbatim:

  > "Elective hysterectomy, tubal ligation, or vasectomy, if the primary indication for these procedures is sterilization... **Not covered under any condition.**"

- RAG should retrieve this exact clause for the query — this is a real EOC exclusion, not an invented rule.
- Cost is not the driver here: benchmark ≈ (3.29×1.000 + 6.67×0.875 + 0.42×0.566) × 33.4009 ≈ **$312.80**; billed $350 is only ~11.9% over, nowhere near the overcharge threshold — the denial is entirely policy-driven, cleanly isolating the reasoning path.

**Expected MVP flow:** reviewer resolves with action `deny`, reason citing the page-118 EOC exclusion clause returned by RAG. `final_status="Denied"`.

---

## 3. PA-103 — Rejected (medical necessity mismatch)

**Patient:** Irene Kowalczyk, DOB 1957-04-18, Zip 10001 (Manhattan, NY)
**Diagnosis:** J06.9 — acute upper respiratory infection, unspecified (common cold)
**Requested service:** Laminotomy with decompression of nerve root, single lumbar level (CPT 63030)
**Billed:** $1,100.00
**Query:** *"Please check if this procedure is covered and appropriate for my diagnosis."*

**Why it's grounded, not scripted:**
- The diagnosis (common cold) does not clinically justify the requested procedure (lumbar spinal decompression surgery) — a deliberate mismatch for the peer-review LLM rationale layer (`generate_rationale` in `peer_review_agent.py`) to catch as an additional escalation reason beyond the deterministic hard gates.
- Cost is deliberately kept unremarkable so it isn't also flagged: benchmark ≈ (11.70×1.064 + 11.35×1.162 + 3.84×1.586) × 33.4009 ≈ **$1,059.70**; billed $1,100 is only ~3.8% over.
- This isolates the "the AI reasons about clinical appropriateness, not just codes matching a list" narrative.

**Expected MVP flow:** reviewer resolves with action `deny`, reason citing the diagnosis/procedure mismatch flagged in the Rationale Panel. `final_status="Denied"`.

---

## 4. PA-104 — Rejected (cost-based)

**Patient:** Walter Iniguez, DOB 1949-12-05, Zip 60601 (Chicago, Cook County, IL)
**Diagnosis:** K21.9 — GERD without esophagitis
**Requested service:** Upper GI endoscopy with biopsy (CPT 43239)
**Billed:** $5,000.00
**Query:** *"Is this billed amount reasonable for my endoscopy procedure compared to what Medicare usually pays?"*

**Why it's grounded, not scripted:**
- Diagnosis and procedure are clinically appropriate (GERD → EGD with biopsy) — coverage isn't in question, only cost.
- CMS benchmark math (locality 16, Chicago):
  - Work RVU 2.33 × GPCI 1.007 = 2.346
  - PE RVU 9.94 × GPCI 1.005 = 9.990
  - MP RVU 0.27 × GPCI 2.295 = 0.620
  - Total RVU-adjusted = 12.956 × $33.4009 ≈ **$432.90 benchmark**
  - Billed $5,000 vs. benchmark $432.90 → **+1,055% variance**, triggering `FINANCIAL_EXCEPTION` by a wide, unambiguous margin.

**Expected MVP flow:** `FINANCIAL_EXCEPTION` fires automatically. Reviewer resolves with action `deny`, reason citing the exact variance percent and dollar figures from the Financial payload. `final_status="Denied"`.

---

## 5. PA-105 — Info Needed

**Patient (illegible-style intake):** "B. Alvarez?", DOB approx. 1953, Zip 30301
**Diagnosis (loosely noted):** M25.561 — pain in right knee
**Requested service:** "knee injection thing", CPT ambiguous between 20610 and 20605
**Billed:** ~$180 (approximate, illegible)
**NPI:** illegible; physician "Dr. T.?"
**Query:** *"Can you check if this request is complete and covered?"*

**Why it's grounded, not scripted:**
- Modeled on the same handwritten/low-legibility pattern already proven in `documents/test_cases/02_low_confidence_handwritten.txt` — genuinely ambiguous extraction (missing NPI, uncertain CPT code, approximate DOB), not an artificially forced state.
- Intake's real extraction-confidence score should fall below the 0.85 threshold, firing `LOW_CONFIDENCE_EXTRACTION` for a genuine reason (the source text is actually ambiguous).

**Expected MVP flow:** case pauses at human review. Reviewer issues action `clarify` with a concrete question (e.g. "Please confirm the exact CPT code for the knee injection — 20605 or 20610 — and the provider NPI"). Routing sets `case_status="awaiting_provider_response"`, `interrupt_reason="Awaiting Provider Response: ..."`. This is the live "Info Needed" state — use the new `ProviderResponseForm.tsx` to submit a provider reply and show the loop resuming.

---

## 6. PA-106 — Human Approval Required

**Patient:** Sylvia Brennan, DOB 1946-09-22, Zip 90210 (Los Angeles County, CA)
**Diagnosis:** M17.11 — unilateral primary osteoarthritis, right knee
**Requested service:** Total knee arthroplasty (CPT 27447)
**Billed:** $1,800.00
**Query:** *"Please review whether this knee replacement is covered and whether the billed cost is fair."*

**Why it's grounded, not scripted:**
- Diagnosis/procedure match cleanly (same shape as the Approved case) — this isolates cost as the sole judgment call.
- CMS benchmark math (locality 18, Los Angeles):
  - Work RVU 19.11 × GPCI 1.041 = 19.893
  - PE RVU 11.58 × GPCI 1.183 = 13.699
  - MP RVU 4.02 × GPCI 0.664 = 2.669
  - Total RVU-adjusted = 36.26 × $33.4009 ≈ **$1,211.30 benchmark**
  - Billed $1,800 vs. benchmark $1,211.30 → **+48.6% variance** — real overcharge, but not the extreme 1,000%+ seen in PA-104. This is a genuinely borderline number, appropriate for human judgment rather than an obvious auto-deny.

**Expected MVP flow:** `FINANCIAL_EXCEPTION` fires. **Do not resolve this case** — leave it sitting at `needs_human_review=True`, `final_status=None` in the Reviewer Portal so you can approve or deny it live during the MVP, showing the real interrupt/resume mechanism (a genuine LangGraph `interrupt`, checkpointed to Postgres, not a UI-faked pause).

---

## Generating the PDFs

```bash
conda run -n pa_hack python3 documents/generate_mvp_pdfs.py
```

Writes all 6 PDFs into `documents/mvp_pdfs/`. Safe to re-run — it always
regenerates the same 6 files. Each PDF contains **only** the raw intake
document (patient/diagnosis/procedure/billing) — no title, case key, or
outcome label, so it reads like a genuine PA request and doesn't give away
the intended MVP outcome. The query for each case is **not** in the PDF —
it must be typed into the Patient Portal's query field separately (see the
table above and each section's "Query" line); it is not parsed out of the
PDF by Intake.

## Running the cases

Upload each PDF via the Patient Portal (`POST /api/v1/upload`) paired with
its query from the table above, then work each one to its terminal state in
the Reviewer Portal per the "Expected MVP flow" notes:

1. PA-101 → reviewer **Approve**
2. PA-102 → reviewer **Deny** (cite EOC page 118 exclusion)
3. PA-103 → reviewer **Deny** (cite diagnosis/procedure mismatch)
4. PA-104 → reviewer **Deny** (cite variance %)
5. PA-105 → reviewer **Request Clarification**, then submit a provider response to show the loop
6. PA-106 → leave **pending** for live approve/deny during the MVP

Note: exact hard-gate behavior depends on live extraction-confidence scores
and RAG match quality at run time (same caveat as
`documents/test_cases/README_TEST_PLAN.md`) — the billed-vs-benchmark dollar
figures above are fixed by the real CSV data and won't change, but which
*additional* soft gates fire (e.g. `LOW_CONFIDENCE_EXTRACTION` on a
well-formed PDF) can vary slightly by LLM run. Check the actual
`financial_payload`/`policy_payload` in the Reviewer Portal before presenting
if you want to narrate the exact fired flags.
