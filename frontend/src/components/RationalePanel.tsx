import { AlertTriangle, Zap, FileSearch, Calculator, Route, Repeat, ListChecks } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const AGENT_LABELS: Record<string, string> = {
  cost: "Cost Check",
  rag: "Policy Check",
  alternative: "Alternative Therapy",
};

function SectionTitle({ icon: Icon, children }: { icon: typeof Calculator; children: React.ReactNode }) {
  return (
    <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
      <Icon size={13} className="text-navy-500" />
      {children}
    </h4>
  );
}

export default function RationalePanel({
  needsHumanReview,
  interruptReason,
  rationale,
  policy,
  financial,
  isExpedite,
  relevantAgents,
  queryClassificationReason,
}: {
  needsHumanReview: boolean;
  interruptReason: string | null;
  rationale: string | null;
  policy: Record<string, any>;
  financial: Record<string, any>;
  isExpedite: boolean;
  relevantAgents?: string[];
  queryClassificationReason?: string | null;
}) {
  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card shadow-soft">
      <div className="flex items-center gap-1.5 border-b border-border bg-[linear-gradient(120deg,rgba(38,70,131,0.08),transparent)] px-4 py-2.5">
        <FileSearch size={15} className="text-navy-600" />
        <h3 className="text-sm font-medium">Reviewer Rationale</h3>
      </div>

      <div className="flex-1 space-y-4 overflow-auto p-4">
        {isExpedite && (
          <div className="animate-pulse-ring flex items-center gap-2 rounded-xl bg-[linear-gradient(120deg,#b30000,#e00000)] p-3 text-sm font-semibold text-white">
            <Zap size={16} className="fill-white" />
            Expedite — within 2 hours of SLA deadline
          </div>
        )}

        {needsHumanReview && (
          <div className="animate-pulse rounded-xl border border-amber-300 bg-amber-50 p-3">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-amber-800">
              <AlertTriangle size={13} />
              Needs Human Review
            </p>
            <p className="mt-1 text-sm text-amber-900">{interruptReason}</p>
            {rationale && <p className="mt-2 text-xs text-amber-800">{rationale}</p>}
          </div>
        )}

        <div>
          <SectionTitle icon={FileSearch}>Policy Citation</SectionTitle>
          {(policy.eoc_citations || []).length === 0 ? (
            <p className="text-xs text-muted-foreground">No policy match retrieved.</p>
          ) : (
            <ul className="space-y-2">
              {policy.eoc_citations.map((cite: string, i: number) => (
                <li key={i} className="rounded-lg border border-border bg-muted/40 p-2 text-xs">
                  <p className="font-medium">{cite}</p>
                  <p className="mt-1 line-clamp-3 text-muted-foreground">
                    {policy.matched_policy_clauses?.[i]}
                  </p>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-1 text-xs text-muted-foreground">
            Similarity score: {policy.policy_match_confidence}
          </p>
        </div>

        <div>
          <SectionTitle icon={Calculator}>Cost Formula Breakdown</SectionTitle>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="cursor-help rounded-lg border border-border bg-muted/40 p-2 text-xs">
                <p>Billed: ${financial.billed_amount?.toFixed?.(2)}</p>
                <p>
                  CMS Rate:{" "}
                  {financial.cms_benchmark_rate != null
                    ? `$${financial.cms_benchmark_rate.toFixed(2)}`
                    : "N/A"}
                </p>
                <p className={cn(financial.is_overcharge && "font-semibold text-radiant")}>
                  Variance: {financial.variance_percent}%
                </p>
              </div>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              (Work RVU × Work GPCI + PE RVU × PE GPCI + MP RVU × MP GPCI) × CF
            </TooltipContent>
          </Tooltip>
        </div>

        {relevantAgents && (
          <div>
            <SectionTitle icon={Route}>Checks Run (query-routed)</SectionTitle>
            <div className="flex flex-wrap gap-2">
              {Object.entries(AGENT_LABELS).map(([key, label]) => {
                const ran = relevantAgents.includes(key);
                return (
                  <span
                    key={key}
                    className={cn(
                      "rounded-full border px-2 py-1 text-xs",
                      ran
                        ? "border-teal-200 bg-teal-50 text-teal-800"
                        : "border-border bg-muted text-muted-foreground"
                    )}
                  >
                    {ran ? "✓" : "skipped —"} {label}
                  </span>
                );
              })}
            </div>
            {queryClassificationReason && (
              <p className="mt-2 text-xs text-muted-foreground">{queryClassificationReason}</p>
            )}
          </div>
        )}

        {financial.alternative_therapy_suggestion && (
          <div>
            <SectionTitle icon={Repeat}>Alternative Therapy</SectionTitle>
            <div className="rounded-lg border border-border bg-muted/40 p-2 text-xs">
              <p>{financial.alternative_therapy_suggestion}</p>
              {financial.alternative_therapy_savings != null && (
                <p className="mt-1 font-semibold text-teal-700">
                  Net savings: ${financial.alternative_therapy_savings.toFixed(2)}
                </p>
              )}
            </div>
          </div>
        )}

        {policy.step_therapy_required && (
          <div>
            <SectionTitle icon={ListChecks}>Step-Therapy Timeline</SectionTitle>
            <ul className="list-inside list-disc text-xs text-foreground/80">
              {(policy.step_therapy_timeline || []).map((step: string, i: number) => (
                <li key={i}>{step}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
