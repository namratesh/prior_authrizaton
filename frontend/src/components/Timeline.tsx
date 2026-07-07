import { useRef } from "react";
import { Check } from "lucide-react";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const STEPS = [
  { key: "intake", label: "Intake" },
  { key: "cost_check", label: "Cost Check" },
  { key: "peer_review", label: "Policy Check" },
  { key: "awaiting_review", label: "Review" },
  { key: "complete", label: "Decision" },
];

// current_phase values emitted by the graph/case_runner (see
// backend/app/core/graph.py and case_runner.py) — "cost_check" covers the
// parallel Cost + Policy RAG superstep, "peer_review" covers the hard-gate
// evaluation right after it, this table collapses those into the 5 UI steps.
const PHASE_TO_STEP_INDEX: Record<string, number> = {
  intake: 0,
  cost_check: 1,
  peer_review: 2,
  awaiting_review: 3,
  complete: 4,
};

export default function Timeline({
  currentPhase,
  needsHumanReview,
  interruptReason,
  caseStatus,
}: {
  currentPhase: string;
  needsHumanReview: boolean;
  interruptReason: string | null;
  caseStatus?: string | null;
}) {
  // An unrecognized phase (e.g. a new agent phase added server-side without
  // updating this map) should hold at the last known step, not visually
  // regress the patient's progress bar back to "Intake".
  const lastKnownIndex = useRef(0);
  const resolvedIndex = PHASE_TO_STEP_INDEX[currentPhase];
  if (resolvedIndex !== undefined) lastKnownIndex.current = resolvedIndex;
  const activeIndex = lastKnownIndex.current;
  const complete = currentPhase === "complete";
  const awaitingProviderResponse = caseStatus === "awaiting_provider_response";
  // Fraction of the connector track that should read as "filled".
  const fillPct = complete ? 100 : (activeIndex / (STEPS.length - 1)) * 100;

  const statusLabel = () => {
    if (currentPhase === "complete") return "Decision ready";
    if (awaitingProviderResponse)
      return "Awaiting your response — the reviewer asked a follow-up question";
    if (needsHumanReview) return "Awaiting reviewer — your case needs a closer look";
    if (currentPhase === "intake") return "Reading your request...";
    if (currentPhase === "cost_check") return "Checking cost and policy...";
    if (currentPhase === "peer_review") return "Checking policy and compliance...";
    return "Processing...";
  };

  return (
    <Card className="p-6">
      <div className="relative">
        {/* Track + animated fill behind the nodes. */}
        <div className="absolute left-0 right-0 top-4 mx-[10%] h-0.5 bg-border" />
        <motion.div
          className="absolute left-0 top-4 mx-[10%] h-0.5 bg-[linear-gradient(90deg,#264683,#199e88)]"
          initial={{ width: "0%" }}
          animate={{ width: `${(fillPct / 100) * 80}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          style={{ maxWidth: "80%" }}
        />
        <div className="relative flex items-center justify-between">
          {STEPS.map((step, i) => {
            const done = i < activeIndex || complete;
            const active = i === activeIndex && !complete;
            return (
              <div key={step.key} className="flex flex-1 flex-col items-center">
                <div
                  className={cn(
                    "z-10 grid h-8 w-8 place-items-center rounded-full text-sm font-medium transition-colors",
                    done
                      ? "bg-[linear-gradient(135deg,#264683,#199e88)] text-white shadow-soft"
                      : active
                      ? "animate-pulse bg-teal-500 text-white shadow-glow"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  {done ? <Check size={16} /> : i + 1}
                </div>
                <span
                  className={cn(
                    "mt-2 text-center text-xs font-medium",
                    done || active ? "text-foreground" : "text-muted-foreground"
                  )}
                >
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
      <p
        className={cn(
          "mt-5 text-sm",
          awaitingProviderResponse ? "animate-pulse font-medium text-radiant" : "text-foreground/80"
        )}
      >
        {statusLabel()}
      </p>
      {awaitingProviderResponse && interruptReason && (
        <div className="mt-3 rounded-lg border border-radiant/30 bg-red-50/60 p-3">
          <p className="text-xs font-semibold text-radiant">Reviewer's question</p>
          <p className="mt-1 text-sm text-foreground/90">
            {interruptReason.replace(/^Awaiting Provider Response:\s*/, "")}
          </p>
        </div>
      )}
      {!awaitingProviderResponse && needsHumanReview && interruptReason && (
        <p className="mt-1 text-xs text-radiant">Reason: {interruptReason}</p>
      )}
    </Card>
  );
}
