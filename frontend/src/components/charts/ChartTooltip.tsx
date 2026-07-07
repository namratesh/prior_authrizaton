import type { TooltipProps } from "recharts";

// Shared custom tooltip for Admin's recharts — themed card surface instead of
// recharts' default white box, with an optional value formatter.
export default function ChartTooltip({
  active,
  payload,
  label,
  formatter,
}: TooltipProps<number, string> & { formatter?: (v: number) => string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-card/95 px-3 py-2 text-xs shadow-elevated backdrop-blur">
      {label != null && <p className="mb-1 font-medium text-foreground">{label}</p>}
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-1.5 text-muted-foreground">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: entry.color }} />
          <span className="font-medium text-foreground">
            {typeof entry.value === "number" && formatter
              ? formatter(entry.value)
              : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}
