import { describe, expect, it } from "vitest";
import { summarizeTraceEntry } from "./traceSummary";

describe("summarizeTraceEntry", () => {
  it("summarizes intake with confidence and routing", () => {
    const text = summarizeTraceEntry({
      agent: "intake",
      extraction_confidence: 0.92,
      relevant_agents: ["cost", "rag"],
    });
    expect(text).toBe("Extracted clinical fields at 92% confidence. Routed to: cost, rag.");
  });

  it("summarizes intake with missing confidence and no routed agents", () => {
    const text = summarizeTraceEntry({ agent: "intake" });
    expect(text).toBe("Extracted clinical fields at unknown confidence. Routed to: none.");
  });

  it("marks cost_intelligence as skipped when not relevant", () => {
    expect(summarizeTraceEntry({ agent: "cost_intelligence", skipped: true })).toBe(
      "Skipped — not relevant to this request."
    );
  });

  it("flags cost_intelligence overcharge with variance", () => {
    const text = summarizeTraceEntry({
      agent: "cost_intelligence",
      variance_percent: 34.567,
      is_overcharge: true,
    });
    expect(text).toBe("Variance 34.6% vs. CMS rate — flagged as overcharge.");
  });

  it("reports peer_review_auditor flags when present", () => {
    const text = summarizeTraceEntry({
      agent: "peer_review_auditor",
      hard_gate_flags: ["FINANCIAL_EXCEPTION", "POLICY_AMBIGUOUS"],
    });
    expect(text).toBe("Flagged for human review: FINANCIAL_EXCEPTION, POLICY_AMBIGUOUS.");
  });

  it("clears peer_review_auditor when no flags fired", () => {
    const text = summarizeTraceEntry({ agent: "peer_review_auditor", hard_gate_flags: [] });
    expect(text).toBe("No hard-gate flags fired — cleared for auto-approval.");
  });

  it("falls back to a generic message for unknown agents", () => {
    expect(summarizeTraceEntry({ agent: "some_future_agent" })).toBe("Agent step completed.");
  });
});
