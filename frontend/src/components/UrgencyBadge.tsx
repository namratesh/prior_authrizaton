import { Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { is_expedite_client } from "@/store/sla";

// Consolidated "Expedite" pill — previously duplicated across ReviewerPortal
// (queue + header) and AdminPortal. Pass a raw sla_deadline and it applies the
// same client-side "within 2h" check (mirror of the backend supervisor rule).
export default function UrgencyBadge({
  slaDeadline,
  size = "sm",
  className,
}: {
  slaDeadline: string | null | undefined;
  size?: "sm" | "md";
  className?: string;
}) {
  if (!is_expedite_client(slaDeadline)) return null;
  return (
    <span
      className={cn(
        "inline-flex animate-pulse-ring items-center gap-1 rounded-full bg-[linear-gradient(120deg,#b30000,#e00000)] font-semibold uppercase tracking-wide text-white",
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-3 py-1 text-xs",
        className
      )}
    >
      <Zap size={size === "sm" ? 11 : 13} className="fill-white" />
      Expedite
    </span>
  );
}
