// Turns a raw agent_trace entry (backend/app/core/graph.py's _trace()) into a
// short human-readable line for the Admin Trace Explorer, so the primary view
// isn't a raw JSON dump. Raw JSON stays available as a secondary disclosure.
export function summarizeTraceEntry(entry: Record<string, any>): string {
  switch (entry.agent) {
    case "intake": {
      const pct =
        typeof entry.extraction_confidence === "number"
          ? `${(entry.extraction_confidence * 100).toFixed(0)}%`
          : "unknown";
      return `Extracted clinical fields at ${pct} confidence. Routed to: ${
        (entry.relevant_agents || []).join(", ") || "none"
      }.`;
    }
    case "cost_intelligence":
      if (entry.skipped) return "Skipped — not relevant to this request.";
      return `Variance ${entry.variance_percent?.toFixed?.(1) ?? "?"}% vs. CMS rate${
        entry.is_overcharge ? " — flagged as overcharge." : "."
      }`;
    case "aarp_rag":
      if (entry.skipped) return "Skipped — not relevant to this request.";
      return `Policy match confidence ${
        typeof entry.policy_match_confidence === "number"
          ? `${(entry.policy_match_confidence * 100).toFixed(0)}%`
          : "unknown"
      }${entry.policy_ambiguous ? " — below threshold, marked ambiguous." : "."}`;
    case "alternative_mapper":
      if (entry.skipped) return "Skipped — not relevant to this request.";
      return entry.fired
        ? `Found lower-cost alternative (CPT ${entry.alternative_cpt}).`
        : "No alternative therapy suggested.";
    case "peer_review_auditor": {
      const flags = entry.hard_gate_flags || [];
      return flags.length
        ? `Flagged for human review: ${flags.join(", ")}.`
        : "No hard-gate flags fired — cleared for auto-approval.";
    }
    case "reviewer":
      return `Reviewer action: ${entry.action}${
        entry.diffs && Object.keys(entry.diffs).length ? " (with corrections)" : ""
      }.`;
    case "summarizer":
      return entry.used_fallback
        ? "Generated decision letter (template fallback used)."
        : "Generated plain-English decision letter.";
    default:
      return "Agent step completed.";
  }
}
