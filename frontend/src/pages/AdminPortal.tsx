import { useEffect, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  CartesianGrid,
} from "recharts";
import { DollarSign, TrendingUp, Scale, ListTree, Table2 } from "lucide-react";
import { AdminMetrics, getAdminMetrics, getReview, ReviewResponse } from "../store/api";
import StatusBadge from "@/components/StatusBadge";
import LoadingState from "@/components/LoadingState";
import UrgencyBadge from "@/components/UrgencyBadge";
import ChartTooltip from "@/components/charts/ChartTooltip";
import { CHART_COLORS } from "@/lib/chart-theme";
import { useCountUp } from "@/lib/useCountUp";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

// // DEMO-MOCKED: static bar chart, not computed from real cohort data —
// synthetic Hero Cases don't carry age/region attributes to aggregate.
const BIAS_GAUGE_DATA = [
  { cohort: "Age 65-74", approvalRate: 0.82 },
  { cohort: "Age 75-84", approvalRate: 0.79 },
  { cohort: "Age 85+", approvalRate: 0.76 },
  { cohort: "Region: West", approvalRate: 0.81 },
  { cohort: "Region: South", approvalRate: 0.78 },
];

function LeakageTile({ value }: { value: number }) {
  const animated = useCountUp(value);
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
        <ResponsiveContainer width="100%" height={100}>
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
      </CardContent>
    </Card>
  );
}

function TraceExplorer({ metrics }: { metrics: AdminMetrics }) {
  const [reviews, setReviews] = useState<Record<string, ReviewResponse>>({});

  const load = (caseId: string) => {
    if (!reviews[caseId]) {
      getReview(caseId)
        .then((r) => setReviews((prev) => ({ ...prev, [caseId]: r })))
        .catch(() => {});
    }
  };

  return (
    <Card>
      <div className="flex items-center gap-2 border-b border-border p-4 text-muted-foreground">
        <ListTree size={16} className="text-navy-600" />
        <h3 className="text-sm font-medium">Agent Trace Explorer</h3>
      </div>
      <div className="px-4">
        <Accordion type="multiple">
          {metrics.cases.map((c) => (
            <AccordionItem key={c.case_id} value={c.case_id}>
              <AccordionTrigger onClick={() => load(c.case_id)}>
                <span className="font-medium">{c.case_number}</span>
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-2">
                  {reviews[c.case_id]?.agent_trace.map((entry, i) => (
                    <div
                      key={i}
                      className="overflow-hidden rounded-lg border border-navy-800 bg-navy-950 text-xs"
                    >
                      <div className="border-b border-navy-800 px-3 py-1.5 font-mono font-semibold text-teal-300">
                        {entry.agent}
                      </div>
                      <pre className="overflow-x-auto whitespace-pre-wrap break-all px-3 py-2 font-mono text-navy-100/80">
                        {JSON.stringify(entry, null, 2)}
                      </pre>
                    </div>
                  )) || <p className="py-2 text-xs text-muted-foreground">Loading trace...</p>}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
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

  if (!metrics) return <LoadingState label="Loading metrics..." />;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-8">
      <div>
        <h1 className="font-display text-3xl font-bold tracking-tight text-gradient">
          Admin Dashboard
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">System health, savings, and audit trail.</p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <LeakageTile value={metrics.leakage_prevented} />
        <AccuracyTile data={metrics.accuracy_drift} />
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="mb-4 flex items-center gap-2 text-muted-foreground">
            <Scale size={16} className="text-navy-600" />
            <h3 className="text-sm font-medium">Bias &amp; Fairness Gauge</h3>
            <Badge variant="outline" className="ml-1 text-[10px]">DEMO-MOCKED</Badge>
          </div>
          <ResponsiveContainer width="100%" height={190}>
            <BarChart data={BIAS_GAUGE_DATA} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <defs>
                <linearGradient id="biasFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CHART_COLORS.primary} stopOpacity={0.95} />
                  <stop offset="100%" stopColor={CHART_COLORS.teal} stopOpacity={0.75} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />
              <XAxis dataKey="cohort" tick={{ fontSize: 10, fill: CHART_COLORS.axis }} tickLine={false} axisLine={false} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 10, fill: CHART_COLORS.axis }} tickLine={false} axisLine={false} />
              <Tooltip cursor={{ fill: "rgba(38,70,131,0.06)" }} content={<ChartTooltip formatter={(v) => `${(v * 100).toFixed(0)}%`} />} />
              <Bar dataKey="approvalRate" fill="url(#biasFill)" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <TraceExplorer metrics={metrics} />

      <Card className="overflow-hidden">
        <div className="flex items-center gap-2 border-b border-border p-4 text-muted-foreground">
          <Table2 size={16} className="text-navy-600" />
          <h3 className="text-sm font-medium">Case List</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-muted/70 backdrop-blur">
              <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="p-3 font-medium">Case</th>
                <th className="p-3 font-medium">Service</th>
                <th className="p-3 font-medium">Status</th>
                <th className="p-3 font-medium">SLA</th>
                <th className="p-3 font-medium">Flags</th>
              </tr>
            </thead>
            <tbody>
              {metrics.cases.map((c) => (
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
                    {c.flags.map((f) => (
                      <Badge key={f} variant="warning" className="text-[10px]">
                        {f}
                      </Badge>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
