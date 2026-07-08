import { useEffect, useState } from "react";
import { getStatus, type StatusResponse } from "@/store/api";
import Timeline from "@/components/Timeline";
import CostCard from "@/components/CostCard";
import LoadingState from "@/components/LoadingState";
import UrgencyBadge from "@/components/UrgencyBadge";
import ProviderResponseForm from "@/components/ProviderResponseForm";
import { Card, CardContent } from "@/components/ui/card";

export default function TimelineView({ caseId }: { caseId: string }) {
  const [status, setStatus] = useState<StatusResponse | null>(null);

  const refresh = async () => {
    try {
      const s = await getStatus(caseId);
      setStatus(s);
    } catch {
      // transient poll failure — try again next tick
    }
  };

  useEffect(() => {
    let cancelled = false;
    let interval: ReturnType<typeof setInterval> | undefined;
    const poll = async () => {
      try {
        const s = await getStatus(caseId);
        if (cancelled) return;
        setStatus(s);
        if (s.final_status != null && interval) {
          clearInterval(interval);
          interval = undefined;
        }
      } catch {
        // transient poll failure — try again next tick
      }
    };
    poll();
    interval = setInterval(poll, 2500);
    return () => {
      cancelled = true;
      if (interval) clearInterval(interval);
    };
  }, [caseId]);

  if (!status) return <LoadingState label="Loading your case..." />;

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <Card>
        <CardContent className="flex items-start justify-between pt-6">
          <div>
            <p className="text-xs font-medium text-muted-foreground">
              Case {status.case_number} &middot; Requested Service
            </p>
            <p className="mt-1 font-medium">
              {status.requested_service_description || "Detecting requested service..."}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {status.final_status == null && (
              <span className="flex items-center gap-1.5 rounded-full border border-teal-200 bg-teal-50/80 px-2.5 py-1 text-[11px] font-medium text-teal-700">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-500 opacity-75" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-teal-500" />
                </span>
                Live
              </span>
            )}
            <UrgencyBadge slaDeadline={status.sla_deadline} />
          </div>
        </CardContent>
      </Card>
      <Timeline
        currentPhase={status.current_phase}
        needsHumanReview={status.needs_human_review}
        interruptReason={status.interrupt_reason}
        caseStatus={status.case_status}
      />
      {status.case_status === "awaiting_provider_response" && (
        <ProviderResponseForm caseId={caseId} onSubmitted={refresh} />
      )}
      <CostCard estimate={status.estimated_out_of_pocket} />
      {status.is_expedite && (
        <div className="animate-pulse-ring rounded-xl bg-[linear-gradient(120deg,#b30000,#e00000)] p-4 text-sm font-medium text-white">
          Your case is being expedited due to SLA deadline.
        </div>
      )}
    </div>
  );
}
