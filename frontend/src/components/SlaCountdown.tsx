import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { cn } from "@/lib/utils";

// Persistent SLA countdown for the non-expedite common case — UrgencyBadge
// only renders once a case is within the 2h expedite window, so up until
// then a reviewer heads-down in the PDF/form panes has no visible signal
// of how much SLA time is left. Ticks every 30s; cheap enough to always run.
function formatRemaining(ms: number): string {
  if (ms <= 0) return "Overdue";
  const totalMinutes = Math.floor(ms / 60000);
  const days = Math.floor(totalMinutes / (60 * 24));
  const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `${days}d ${hours}h left`;
  if (hours > 0) return `${hours}h ${minutes}m left`;
  return `${minutes}m left`;
}

export default function SlaCountdown({
  slaDeadline,
  className,
}: {
  slaDeadline: string | null | undefined;
  className?: string;
}) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(interval);
  }, []);

  if (!slaDeadline) return null;
  const remainingMs = new Date(slaDeadline).getTime() - now;
  const overdue = remainingMs <= 0;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium tabular-nums",
        overdue
          ? "border-radiant/30 bg-red-50 text-radiant"
          : "border-border bg-muted/50 text-muted-foreground",
        className
      )}
    >
      <Clock size={11} />
      {formatRemaining(remainingMs)}
    </span>
  );
}
