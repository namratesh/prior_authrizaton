# AgenticPA — Backend Workflow (Mermaid)

Source of truth: `backend/app/core/graph.py`, `core/case_runner.py`, `core/state.py`,
`agents/peer_review_agent.py`, `agents/cost_agent.py`, `agents/rag_agent.py`.

## 1. LangGraph flowchart

```mermaid
flowchart TD
    upload["Patient Portal\nPDF upload + query"] -->|"POST /api/v1/upload"| api["API layer\nroutes.py"]
    api -->|"case_runner.start_case()\ngraph.invoke(thread_id=case_id)"| intake

    intake["intake\nLLM extraction + query\nclassification (fail-safe: ALL_AGENTS)"]

    intake -->|route_after_intake| routecheck{"relevant_agents\n⊆ {cost, rag, alternative}"}
    routecheck -->|cost| cost["cost\ndeterministic\nCMS rate vs billed\n>20% ⇒ FINANCIAL_EXCEPTION"]
    routecheck -->|rag| rag["rag\ndeterministic\nQdrant hybrid search\n<0.70 ⇒ POLICY_AMBIGUOUS"]
    routecheck -->|"skipped agents"| alternative

    cost --> alternative
    rag --> alternative

    alternative["alternative\nDEMO-MOCKED\njoin node + hardcoded\nprocedure alt. mapping"]
    alternative --> peer_review

    peer_review["peer_review\nLayer 1: evaluate_hard_gates() — deterministic\nLOW_CONFIDENCE_EXTRACTION (conf < 0.85)\nFINANCIAL_EXCEPTION / RATE_UNAVAILABLE\nPOLICY_AMBIGUOUS\n---\nLayer 2: generate_rationale() — LLM\n(can only ADD reasons, never suppress)"]

    peer_review -->|route_after_peer_review| gatecheck{"needs_human_review?"}
    gatecheck -->|"True"| human_review
    gatecheck -->|"False"| summarizer

    human_review["human_review\nREAL langgraph interrupt()\nPostgresSaver checkpoint\n(thread_id=case_id)"]
    human_review -->|"clarify /\nprovider_responded"| human_review
    human_review -->|"approve / modify / deny\n(final_status set)"| summarizer

    summarizer["summarizer\nLLM translation\ndecision letter + FHIR stub\nused_fallback on LLM failure"]
    summarizer --> persist["case_runner._persist()\nupsert cases / append audit_logs"]
    persist --> done(["END\nserved via /status, /review,\n/admin/metrics"])

    classDef llm fill:#ecebfa,stroke:#4340c7,color:#1a1a1a;
    classDef gate fill:#e6f4f0,stroke:#0e7c66,color:#1a1a1a;
    classDef mock fill:#f0f1f3,stroke:#6b6f7a,color:#1a1a1a,stroke-dasharray: 3 3;
    classDef hitl fill:#fdeaea,stroke:#e00000,color:#1a1a1a;
    classDef decision fill:#f4f5f8,stroke:#dde2ea,color:#1a1a1a;

    class intake,summarizer llm;
    class cost,rag gate;
    class alternative mock;
    class human_review hitl;
    class routecheck,gatecheck decision;
```

**Reading notes**

- `route_after_intake` and `relevant_agents` are a **routing hint only** — any
  classification failure fails safe to running every agent. It never suppresses
  a safety check, only skips work judged unnecessary.
- `cost` and `rag` execute in the same LangGraph superstep (true parallel
  fan-out); their audit-trace entries are folded in at the `alternative` join
  node because a Pydantic state channel accepts one write per step.
- `needs_human_review` is set **entirely** by `peer_review`'s deterministic
  Layer 1 before any LLM call runs. Layer 2 (LLM) can only add escalation
  reasons — it can never flip a fired hard gate back to auto-approve, and if
  it fails/times out, the hard-gate result still stands.
- `human_review` is a genuine graph-level `interrupt()`, checkpointed to
  Postgres — the graph cannot physically reach `summarizer` while
  `needs_human_review=True`. "Request Clarification" and "Provider Responded"
  loop back to the *same* interrupt point rather than creating a new node.

---

## 2. State schema (UML class diagram)

```mermaid
classDiagram
    class AgenticPAState {
        +ClinicalPayload clinical
        +FinancialPayload financial
        +PolicyPayload policy
        +RoutingPayload routing
        +AuditPayload audit
    }

    class ClinicalPayload {
        +str case_id
        +str patient_name
        +str patient_dob
        +str patient_zip
        +list~str~ icd10_codes
        +list~str~ cpt_codes
        +str diagnosis_summary
        +str provider_npi
        +str requested_service_description
        +float billed_amount
        +float extraction_confidence
        +list~str~ few_shot_corrections_used
        +str patient_query
    }

    class FinancialPayload {
        +float billed_amount
        +float cms_benchmark_rate
        +float variance_amount
        +float variance_percent
        +bool is_overcharge
        +str alternative_therapy_suggestion
        +float alternative_therapy_savings
    }

    class PolicyPayload {
        +list~str~ eoc_citations
        +list~str~ matched_policy_clauses
        +bool step_therapy_required
        +list~str~ step_therapy_timeline
        +float policy_match_confidence
        +bool policy_ambiguous
    }

    class RoutingPayload {
        +str current_phase
        +bool needs_human_review
        +str interrupt_reason
        +str reviewer_id
        +str reviewer_decision
        +dict reviewer_diffs
        +str final_status
        +datetime sla_deadline
        +str case_status
        +list~str~ relevant_agents
        +str query_classification_reason
    }

    class AuditPayload {
        +list~dict~ agent_trace
        +list~str~ feedback_corrections_used
        +str decision_letter
        +dict fhir_stub
        +datetime created_at
        +datetime updated_at
    }

    AgenticPAState "1" *-- "1" ClinicalPayload
    AgenticPAState "1" *-- "1" FinancialPayload
    AgenticPAState "1" *-- "1" PolicyPayload
    AgenticPAState "1" *-- "1" RoutingPayload
    AgenticPAState "1" *-- "1" AuditPayload
```

---

## 3. Human-review interrupt lifecycle (sequence diagram)

```mermaid
sequenceDiagram
    participant R as Reviewer (UI)
    participant API as FastAPI routes
    participant CR as case_runner
    participant G as LangGraph (PostgresSaver)

    R->>API: GET /review/{case_id}
    API->>CR: read persisted state
    CR-->>API: ClinicalPayload / FinancialPayload / PolicyPayload / rationale
    API-->>R: split-screen data

    Note over G: graph paused at human_review\n(needs_human_review=True)

    alt Request Clarification
        R->>API: adjudicate(action="clarify", question)
        API->>CR: resume_case(case_id, payload)
        CR->>G: graph.invoke(Command(resume=payload))
        G-->>G: human_review re-interrupts\n(same point, case_status=awaiting_provider_response)
    else Approve / Modify / Deny
        R->>API: adjudicate(action, diffs, reviewer_id)
        API->>CR: resume_case(case_id, payload)
        CR->>G: graph.invoke(Command(resume=payload))
        G->>G: final_status set, needs_human_review=False
        G->>G: summarizer runs (decision letter + FHIR stub)
        G-->>CR: completed state
        CR->>CR: persist cases + audit_logs
    end
```
