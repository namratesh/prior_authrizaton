import { useEffect, useState } from "react";
import { getStatus, type StatusResponse } from "@/store/api";
import Timeline from "@/components/Timeline";
import CostCard from "@/components/CostCard";
import LoadingState from "@/components/LoadingState";
import UrgencyBadge from "@/components/UrgencyBadge";
import { Card, CardContent } from "@/components/ui/card";

export default function TimelineView({ caseId }: { caseId: string }) {
  const [status, setStatus] = useState<StatusResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const s = await getStatus(caseId);
        if (!cancelled) setStatus(s);
      } catch {
        // transient poll failure — try again next tick
      }
    };
    poll();
    const interval = setInterval(poll, 2500);
    return () => {
      cancelled = true;
      clearInterval(interval);
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
          <UrgencyBadge slaDeadline={status.sla_deadline} />
        </CardContent>
      </Card>
      <Timeline
        currentPhase={status.current_phase}
        needsHumanReview={status.needs_human_review}
        interruptReason={status.interrupt_reason}
      />
      <CostCard estimate={status.estimated_out_of_pocket} />
      {status.is_expedite && (
        <div className="animate-pulse-ring rounded-xl bg-[linear-gradient(120deg,#b30000,#e00000)] p-4 text-sm font-medium text-white">
          Your case is being expedited due to SLA deadline.
        </div>
      )}
    </div>
  );
}
