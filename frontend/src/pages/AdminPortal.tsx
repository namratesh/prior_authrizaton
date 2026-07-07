import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import {
  DollarSign,
  TrendingUp,
  Scale,
  ListTree,
  Table2,
  ClipboardList,
  Hourglass,
  CheckCircle2,
  Info,
  Code2,
  Search,
  ExternalLink,
  Download,
  Settings2,
  BarChart3,
} from "lucide-react";
import {
  AdminMetrics,
  AdminSettings,
  getAdminMetrics,
  getAdminSettings,
  updateAdminSettings,
  getReview,
  ReviewResponse,
  exportCaseAuditUrl,
  exportAllAuditUrl,
  downloadWithAuth,
} from "../store/api";
import StatusBadge from "@/components/StatusBadge";
import LoadingState from "@/components/LoadingState";
import UrgencyBadge from "@/components/UrgencyBadge";
import ChartTooltip from "@/components/charts/ChartTooltip";
import { CHART_COLORS } from "@/lib/chart-theme";
import { cn } from "@/lib/utils";
import { summarizeTraceEntry } from "@/lib/traceSummary";
import { useCountUp } from "@/lib/useCountUp";
import { Card, CardContent } from "@/components/ui/card";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

// Deterministic hard-gate flags get differentiated colors so severity is
// scannable at a glance instead of every flag looking identical.
const FLAG_STYLES: Record<string, BadgeProps["variant"]> = {
  FINANCIAL_EXCEPTION: "destructive",
  RATE_UNAVAILABLE: "secondary",
  POLICY_AMBIGUOUS: "info",
  LOW_CONFIDENCE_EXTRACTION: "warning",
};

function SectionHeader({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof ListTree;
  title: string;
  description?: string;
}) {
  return (
    <div className="mb-1 flex items-center gap-2">
      <Icon size={18} className="text-navy-600" />
      <h2 className="font-display text-lg font-semibold tracking-tight text-foreground">{title}</h2>
      {description && <span className="text-xs text-muted-foreground">— {description}</span>}
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="flex h-full min-h-[100px] items-center justify-center rounded-lg border border-dashed border-border text-xs text-muted-foreground">
      {label}
    </div>
  );
}

function StatTile({
  icon: Icon,
  label,
  value,
  accent = "navy",
}: {
  icon: typeof ClipboardList;
  label: string;
  value: string | number;
  accent?: "navy" | "teal" | "radiant";
}) {
  const accentClass =
    accent === "radiant" ? "text-radiant" : accent === "teal" ? "text-teal-600" : "text-navy-600";
  return (
    <Card>
      <CardContent className="flex items-center gap-3 pt-6">
        <div className={cnBg(accent)}>
          <Icon size={18} className={accentClass} />
        </div>
        <div>
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          <p className="font-display text-2xl font-bold tabular-nums">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function cnBg(accent: "navy" | "teal" | "radiant") {
  if (accent === "radiant") return "rounded-lg bg-red-50 p-2";
  if (accent === "teal") return "rounded-lg bg-teal-50 p-2";
  return "rounded-lg bg-navy-50 p-2";
}

function LeakageTile({ value }: { value: number }) {
  const animated = useCountUp(value, 3600);
  return (
    <Card className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute -right-10 -top-12 h-40 w-40 rounded-full blur-2xl"
        style={{ background: "radial-gradient(circle, rgba(224,0,0,0.18), transparent 70%)" }}
      />
      <CardContent className="relative pt-6">
        <div className="flex items-center gap-2 text-muted-foreground">
          <DollarSign size={16} className="text-radiant" />
          <h3 className="text-sm font-medium">Leakage Prevented</h3>
        </div>
        <p className="mt-1 font-display text-4xl font-bold tabular-nums text-gradient-radiant">
          ${animated.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
      </CardContent>
    </Card>
  );
}

function AccuracyTile({ data }: { data: AdminMetrics["accuracy_drift"] }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="mb-2 flex items-center gap-2 text-muted-foreground">
          <TrendingUp size={16} className="text-teal-600" />
          <h3 className="text-sm font-medium">Accuracy Drift (7 days)</h3>
        </div>
        {data.length === 0 ? (
          <EmptyState label="No finalized cases in the last 7 days yet" />
        ) : (
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
              <defs>
                <linearGradient id="accuracyFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CHART_COLORS.teal} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={CHART_COLORS.teal} stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" hide />
              <YAxis domain={[0, 1]} hide />
              <Tooltip content={<ChartTooltip formatter={(v) => `${(v * 100).toFixed(1)}%`} />} />
              <Area
                type="monotone"
                dataKey="accuracy"
                stroke={CHART_COLORS.teal}
                strokeWidth={2.5}
                fill="url(#accuracyFill)"
                dot={{ r: 2.5, fill: CHART_COLORS.teal }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

const FAIRNESS_DIMENSIONS: { key: AdminMetrics["fairness_cohorts"][number]["dimension"] | "demographics"; label: string }[] = [
  { key: "demographics", label: "Age / Region" },
  { key: "provider", label: "Provider" },
  { key: "service", label: "Service" },
];

const FAIRNESS_LENSES: { key: "frequentist" | "bayesian"; label: string }[] = [
  { key: "frequentist", label: "Wilson CI" },
  { key: "bayesian", label: "Bayesian" },
];

function isFlagged(c: AdminMetrics["fairness_cohorts"][number], lens: "frequentist" | "bayesian"): boolean {
  return lens === "frequentist"
    ? c.significant_disparity
    : c.p_worse_than_overall != null && (c.p_worse_than_overall >= 0.9 || c.p_worse_than_overall <= 0.1);
}

function FairnessTooltip({
  active,
  payload,
  lens,
}: {
  active?: boolean;
  payload?: { payload: AdminMetrics["fairness_cohorts"][number] }[];
  lens: "frequentist" | "bayesian";
}) {
  if (!active || !payload?.length) return null;
  const c = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-card/95 px-3 py-2 text-xs shadow-elevated backdrop-blur">
      <p className="mb-1 font-medium text-foreground">{c.cohort}</p>
      <p className="text-muted-foreground">
        Approval rate: <span className="font-medium text-foreground">{(c.approval_rate * 100).toFixed(0)}%</span>{" "}
        (n={c.total})
      </p>
      {lens === "frequentist" ? (
        <>
          <p className="text-muted-foreground">
            95% Wilson CI: {(c.ci_low * 100).toFixed(0)}%–{(c.ci_high * 100).toFixed(0)}%
          </p>
          {c.significant_disparity && (
            <p className="mt-1 font-medium text-radiant">Differs from overall rate beyond sampling noise</p>
          )}
        </>
      ) : (
        <>
          <p className="text-muted-foreground">
            Posterior mean: <span className="font-medium text-foreground">{(c.posterior_mean * 100).toFixed(0)}%</span>
          </p>
          <p className="text-muted-foreground">
            95% credible interval: {(c.credible_low * 100).toFixed(0)}%–{(c.credible_high * 100).toFixed(0)}%
          </p>
          {c.p_worse_than_overall != null && (
            <p className="text-muted-foreground">
              P(worse than overall | data): <span className="font-medium text-foreground">{(c.p_worse_than_overall * 100).toFixed(0)}%</span>
            </p>
          )}
          {isFlagged(c, "bayesian") && (
            <p className="mt-1 font-medium text-radiant">
              {c.p_worse_than_overall! >= 0.9 ? "Likely worse than overall, given the data" : "Likely better than overall, given the data"}
            </p>
          )}
        </>
      )}
    </div>
  );
}

function BiasFairnessCard({
  data,
  finalizedTotal,
}: {
  data: AdminMetrics["fairness_cohorts"];
  finalizedTotal: number;
}) {
  const [dimension, setDimension] = useState<(typeof FAIRNESS_DIMENSIONS)[number]["key"]>("demographics");
  const [lens, setLens] = useState<"frequentist" | "bayesian">("frequentist");

  const filtered = data.filter((c) =>
    dimension === "demographics" ? c.dimension === "age" || c.dimension === "region" : c.dimension === dimension
  );
  const overallRate = data.length
    ? data.reduce((sum, c) => sum + c.approval_rate * c.total, 0) / data.reduce((sum, c) => sum + c.total, 0)
    : null;

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Scale size={16} className="text-navy-600" />
            <h3 className="text-sm font-medium">Bias &amp; Fairness Gauge</h3>
          </div>
          <div className="flex gap-1">
            {FAIRNESS_DIMENSIONS.map((d) => (
              <button
                key={d.key}
                onClick={() => setDimension(d.key)}
                className={cn(
                  "rounded-full border px-2 py-0.5 text-[11px] transition-colors",
                  dimension === d.key
                    ? "border-navy-600 bg-navy-600 text-white"
                    : "border-border text-muted-foreground hover:bg-muted"
                )}
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>
        <div className="mb-3 flex items-center gap-1">
          <span className="text-[11px] text-muted-foreground">Method:</span>
          {FAIRNESS_LENSES.map((l) => (
            <button
              key={l.key}
              onClick={() => setLens(l.key)}
              className={cn(
                "rounded-full border px-2 py-0.5 text-[11px] transition-colors",
                lens === l.key
                  ? "border-teal-600 bg-teal-600 text-white"
                  : "border-border text-muted-foreground hover:bg-muted"
              )}
            >
              {l.label}
            </button>
          ))}
        </div>
        <p className="mb-3 flex items-start gap-1 text-[11px] leading-snug text-muted-foreground">
          <Info size={12} className="mt-0.5 shrink-0" />
          {lens === "frequentist" ? (
            <>
              Approval rate by cohort, computed from each case's own data. Cohorts with fewer than 3
              finalized cases are omitted. Bars in red have a 95% Wilson confidence interval that excludes
              the overall approval rate — a disparity unlikely to be sampling noise.
            </>
          ) : (
            <>
              A Bayesian Beta-Binomial posterior per cohort, using a weakly-informative prior centered on
              the overall approval rate. Bars in red have &ge;90% posterior probability of being worse (or
              &le;10%, better) than overall, given the data observed so far — a direct probability
              statement rather than a significance test.
            </>
          )}
        </p>
        {filtered.length === 0 ? (
          <EmptyState
            label={
              finalizedTotal === 0
                ? "No finalized cases yet — the cohort breakdown will populate as cases are approved or denied."
                : `Not enough finalized cases yet for a reliable cohort breakdown in this dimension (out of ${finalizedTotal} finalized case${finalizedTotal === 1 ? "" : "s"})`
            }
          />
        ) : (
          <ResponsiveContainer width="100%" height={170}>
            <BarChart data={filtered} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <defs>
                <linearGradient id="biasFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CHART_COLORS.primary} stopOpacity={0.95} />
                  <stop offset="100%" stopColor={CHART_COLORS.teal} stopOpacity={0.75} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />
              <XAxis dataKey="cohort" tick={{ fontSize: 10, fill: CHART_COLORS.axis }} tickLine={false} axisLine={false} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 10, fill: CHART_COLORS.axis }} tickLine={false} axisLine={false} />
              <Tooltip cursor={{ fill: "rgba(38,70,131,0.06)" }} content={<FairnessTooltip lens={lens} />} />
              {overallRate != null && (
                <ReferenceLine y={overallRate} stroke={CHART_COLORS.axis} strokeDasharray="4 4" />
              )}
              <Bar dataKey={lens === "frequentist" ? "approval_rate" : "posterior_mean"} radius={[6, 6, 0, 0]}>
                {filtered.map((c, i) => (
                  <Cell key={i} fill={isFlagged(c, lens) ? "#dc2626" : "url(#biasFill)"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

function SystemConfigCard() {
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getAdminSettings().then(setSettings);
  }, []);

  if (!settings) return null;

  const save = async () => {
    setSaving(true);
    setSaved(false);
    try {
      const updated = await updateAdminSettings(settings);
      setSettings(updated);
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  const AGENT_LABELS: Record<string, string> = {
    cost: "Cost Intelligence",
    rag: "Policy RAG",
    alternative: "Alternative Therapy Mapper",
  };

  return (
    <Card>
      <div className="flex items-center gap-2 border-b border-border p-4 text-muted-foreground">
        <Settings2 size={16} className="text-navy-600" />
        <h3 className="text-sm font-medium">System Configuration</h3>
      </div>
      <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-4">
        <label className="text-xs">
          <span className="mb-1 block font-medium text-muted-foreground">SLA Window (hours)</span>
          <Input
            type="number"
            min={1}
            value={settings.sla_hours}
            onChange={(e) => setSettings({ ...settings, sla_hours: Number(e.target.value) })}
          />
        </label>
        <label className="text-xs">
          <span className="mb-1 block font-medium text-muted-foreground">Expedite Window (hours)</span>
          <Input
            type="number"
            min={0.5}
            step={0.5}
            value={settings.expedite_hours}
            onChange={(e) => setSettings({ ...settings, expedite_hours: Number(e.target.value) })}
          />
        </label>
        <label className="text-xs">
          <span className="mb-1 block font-medium text-muted-foreground">
            Confidence Threshold ({Math.round(settings.confidence_threshold * 100)}%)
          </span>
          <Input
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={settings.confidence_threshold}
            onChange={(e) => setSettings({ ...settings, confidence_threshold: Number(e.target.value) })}
          />
        </label>
        <label className="text-xs">
          <span className="mb-1 block font-medium text-muted-foreground">Overcharge Threshold (%)</span>
          <Input
            type="number"
            min={0}
            step={1}
            value={settings.overcharge_threshold_percent}
            onChange={(e) =>
              setSettings({ ...settings, overcharge_threshold_percent: Number(e.target.value) })
            }
          />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-4 border-t border-border p-4">
        {Object.entries(AGENT_LABELS).map(([key, label]) => (
          <label key={key} className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={settings.agents_enabled[key as keyof typeof settings.agents_enabled]}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  agents_enabled: { ...settings.agents_enabled, [key]: e.target.checked },
                })
              }
            />
            {label}
          </label>
        ))}
        <Button size="sm" className="ml-auto" disabled={saving} onClick={save}>
          {saving ? "Saving..." : "Save Settings"}
        </Button>
        {saved && <span className="text-xs text-teal-600">Saved — applies to the next case.</span>}
      </div>
    </Card>
  );
}

const SEGMENT_LABELS: Record<string, string> = {
  provider: "Provider (NPI)",
  service: "Requested Service",
  reviewer: "Reviewer",
};

function SegmentDrilldownCard() {
  const [groupBy, setGroupBy] = useState<"provider" | "service" | "reviewer">("service");
  const [segments, setSegments] = useState<AdminMetrics["segments"]>(null);

  useEffect(() => {
    getAdminMetrics(groupBy).then((m) => setSegments(m.segments));
  }, [groupBy]);

  return (
    <Card>
      <div className="flex items-center justify-between border-b border-border p-4 text-muted-foreground">
        <div className="flex items-center gap-2">
          <BarChart3 size={16} className="text-navy-600" />
          <h3 className="text-sm font-medium">Analytics Drill-Down</h3>
        </div>
        <select
          value={groupBy}
          onChange={(e) => setGroupBy(e.target.value as typeof groupBy)}
          className="h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground"
        >
          {Object.entries(SEGMENT_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              By {label}
            </option>
          ))}
        </select>
      </div>
      {!segments || segments.length === 0 ? (
        <div className="p-4">
          <EmptyState label="No finalized cases to segment yet" />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/70">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="p-3 font-medium">{SEGMENT_LABELS[groupBy]}</th>
                <th className="p-3 font-medium">Cases</th>
                <th className="p-3 font-medium">Override Rate</th>
                <th className="p-3 font-medium">Leakage Prevented</th>
              </tr>
            </thead>
            <tbody>
              {segments.map((s) => (
                <tr key={s.key} className="border-b border-border last:border-0 odd:bg-muted/30">
                  <td className="p-3 font-medium">{s.key}</td>
                  <td className="p-3 text-muted-foreground">{s.total}</td>
                  <td className="p-3 text-muted-foreground">
                    {s.override_rate != null ? `${(s.override_rate * 100).toFixed(0)}%` : "—"}
                  </td>
                  <td className="p-3 text-muted-foreground">${s.leakage.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function TraceExplorer({ metrics }: { metrics: AdminMetrics }) {
  const [reviews, setReviews] = useState<Record<string, ReviewResponse>>({});
  const [rawOpen, setRawOpen] = useState<Record<string, boolean>>({});

  const load = (caseId: string) => {
    if (!reviews[caseId]) {
      getReview(caseId)
        .then((r) => setReviews((prev) => ({ ...prev, [caseId]: r })))
        .catch(() => {});
    }
  };

  return (
    <Card>
      <div className="flex items-center justify-between border-b border-border p-4 text-muted-foreground">
        <div className="flex items-center gap-2">
          <ListTree size={16} className="text-navy-600" />
          <h3 className="text-sm font-medium">Agent Trace &amp; Audit Log</h3>
        </div>
        {metrics.cases.length > 0 && (
          <button
            type="button"
            onClick={() => downloadWithAuth(exportAllAuditUrl(), "audit_export.csv").catch(() => {})}
            className="flex items-center gap-1 text-xs font-medium text-navy-600 hover:underline"
          >
            <Download size={12} />
            Export All (CSV)
          </button>
        )}
      </div>
      {metrics.cases.length === 0 ? (
        <div className="p-4">
          <EmptyState label="No cases yet" />
        </div>
      ) : (
        <div className="px-4">
          <Accordion type="multiple">
            {metrics.cases.map((c) => (
              <AccordionItem key={c.case_id} value={c.case_id}>
                <AccordionTrigger onClick={() => load(c.case_id)}>
                  <span className="font-medium">{c.case_number}</span>
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    {c.requested_service_description || ""}
                  </span>
                </AccordionTrigger>
                <AccordionContent>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      downloadWithAuth(exportCaseAuditUrl(c.case_id), `audit_${c.case_number}.csv`).catch(() => {});
                    }}
                    className="mb-2 inline-flex items-center gap-1 text-[11px] font-medium text-navy-600 hover:underline"
                  >
                    <Download size={11} />
                    Export this case (CSV)
                  </button>
                  {c.rationale && (
                    <div className="mb-3 rounded-lg border border-navy-100 bg-navy-50/50 p-3">
                      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-navy-600">
                        Why this case was flagged
                      </p>
                      <p className="text-xs leading-relaxed text-foreground/80">{c.rationale}</p>
                    </div>
                  )}
                  <div className="space-y-2">
                    {reviews[c.case_id]?.agent_trace.map((entry, i) => {
                      const rawKey = `${c.case_id}-${i}`;
                      return (
                        <div key={i} className="rounded-lg border border-border bg-muted/30 text-xs">
                          <div className="flex items-center justify-between px-3 py-2">
                            <div className="flex items-center gap-2">
                              <span className="rounded bg-navy-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-navy-700">
                                {entry.agent}
                              </span>
                              {entry.at && (
                                <span className="text-[10px] text-muted-foreground">
                                  {new Date(entry.at).toLocaleTimeString()}
                                </span>
                              )}
                            </div>
                            <button
                              type="button"
                              onClick={() =>
                                setRawOpen((prev) => ({ ...prev, [rawKey]: !prev[rawKey] }))
                              }
                              className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground"
                            >
                              <Code2 size={11} />
                              {rawOpen[rawKey] ? "Hide raw" : "View raw"}
                            </button>
                          </div>
                          <p className="px-3 pb-2 text-foreground/80">{summarizeTraceEntry(entry)}</p>
                          {rawOpen[rawKey] && (
                            <pre className="overflow-x-auto whitespace-pre-wrap break-all border-t border-border bg-navy-950 px-3 py-2 font-mono text-navy-100/80">
                              {JSON.stringify(entry, null, 2)}
                            </pre>
                          )}
                        </div>
                      );
                    }) || <p className="py-2 text-xs text-muted-foreground">Loading trace...</p>}
                  </div>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      )}
    </Card>
  );
}

function CaseListTable({ cases }: { cases: AdminMetrics["cases"] }) {
  const [search, setSearch] = useState("");
  const [flagFilter, setFlagFilter] = useState("all");

  const flagOptions = useMemo(() => {
    const seen = new Set<string>();
    cases.forEach((c) => c.flags.forEach((f) => seen.add(f)));
    return Array.from(seen).sort();
  }, [cases]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return cases.filter((c) => {
      if (flagFilter !== "all" && !c.flags.includes(flagFilter)) return false;
      if (!q) return true;
      return (
        c.case_number.toLowerCase().includes(q) ||
        (c.requested_service_description || "").toLowerCase().includes(q) ||
        (c.final_status || c.current_phase || "").toLowerCase().includes(q)
      );
    });
  }, [cases, search, flagFilter]);

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4 text-muted-foreground">
        <div className="flex items-center gap-2">
          <Table2 size={16} className="text-navy-600" />
          <h3 className="text-sm font-medium">Case List</h3>
        </div>
        {cases.length > 0 && (
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search case, service, status..."
                className="h-8 w-56 pl-8 text-xs"
              />
            </div>
            <select
              value={flagFilter}
              onChange={(e) => setFlagFilter(e.target.value)}
              className="h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground"
            >
              <option value="all">All flags</option>
              {flagOptions.map((f) => (
                <option key={f} value={f}>
                  {f.split("_").join(" ")}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      {cases.length === 0 ? (
        <div className="p-4">
          <EmptyState label="No cases yet" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="p-4">
          <EmptyState label="No cases match your search/filter" />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-muted/70 backdrop-blur">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="p-3 font-medium">Case</th>
                <th className="p-3 font-medium">Service</th>
                <th className="p-3 font-medium">Status</th>
                <th className="p-3 font-medium">SLA</th>
                <th className="p-3 font-medium">Flags</th>
                <th className="p-3 font-medium">Assigned</th>
                <th className="p-3 font-medium">Review</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.case_id} className="border-b border-border last:border-0 odd:bg-muted/30 hover:bg-teal-50/40">
                  <td className="p-3 font-medium">{c.case_number}</td>
                  <td className="p-3 text-muted-foreground">{c.requested_service_description || "—"}</td>
                  <td className="p-3">
                    <StatusBadge status={c.final_status || c.current_phase} />
                  </td>
                  <td className="p-3">
                    <UrgencyBadge slaDeadline={c.sla_deadline} />
                  </td>
                  <td className="space-x-1 p-3">
                    {c.flags.length === 0 && <span className="text-xs text-muted-foreground">—</span>}
                    {c.flags.map((f) => (
                      <Badge key={f} variant={FLAG_STYLES[f] ?? "warning"} className="text-[10px]">
                        {f.split("_").join(" ")}
                      </Badge>
                    ))}
                  </td>
                  <td className="p-3 text-xs text-muted-foreground">{c.assigned_to || "—"}</td>
                  <td className="p-3">
                    {c.needs_human_review && !c.final_status ? (
                      <Link
                        to={`/reviewer/${c.case_id}`}
                        className="inline-flex items-center gap-1 text-xs font-medium text-navy-600 hover:underline"
                      >
                        Open in Reviewer
                        <ExternalLink size={11} />
                      </Link>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export default function AdminPortal() {
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);

  useEffect(() => {
    const poll = () => getAdminMetrics().then(setMetrics).catch(() => {});
    poll();
    const interval = setInterval(poll, 4000);
    return () => clearInterval(interval);
  }, []);

  const kpis = useMemo(() => {
    if (!metrics) return null;
    const total = metrics.cases.length;
    const inReview = metrics.cases.filter((c) => c.needs_human_review && !c.final_status).length;
    const resolved = metrics.cases.filter((c) => c.final_status).length;
    return { total, inReview, resolved };
  }, [metrics]);

  if (!metrics || !kpis) return <LoadingState label="Loading metrics..." />;

  return (
    <div className="mx-auto max-w-6xl space-y-10 p-8">
      <div>
        <h1 className="font-display text-3xl font-bold tracking-tight text-gradient">
          Admin Dashboard
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">System health, savings, and audit trail.</p>
      </div>

      <section className="space-y-4">
        <SectionHeader icon={ClipboardList} title="Overview" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatTile icon={ClipboardList} label="Total Cases" value={kpis.total} accent="navy" />
          <StatTile icon={Hourglass} label="In Review" value={kpis.inReview} accent="radiant" />
          <StatTile icon={CheckCircle2} label="Resolved" value={kpis.resolved} accent="teal" />
        </div>
        <LeakageTile value={metrics.leakage_prevented} />
      </section>

      <section className="space-y-4">
        <SectionHeader
          icon={TrendingUp}
          title="Financial & Fairness Analytics"
          description="accuracy trend and cohort-level approval equity"
        />
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <AccuracyTile data={metrics.accuracy_drift} />
          <BiasFairnessCard data={metrics.fairness_cohorts} finalizedTotal={metrics.fairness_finalized_total} />
        </div>
        <SegmentDrilldownCard />
      </section>

      <section className="space-y-4">
        <SectionHeader
          icon={Settings2}
          title="System Configuration"
          description="admin-tunable SLA, confidence threshold, and agent toggles"
        />
        <SystemConfigCard />
      </section>

      <section className="space-y-4">
        <SectionHeader
          icon={ListTree}
          title="Operations & Audit"
          description="per-case agent trace, explainability, and case list"
        />
        <TraceExplorer metrics={metrics} />
        <CaseListTable cases={metrics.cases} />
      </section>
    </div>
  );
}
