import { useEffect, useState } from "react";
import { getStatus, respondToCase, type StatusResponse } from "@/store/api";
import Timeline from "@/components/Timeline";
import CostCard from "@/components/CostCard";
import LoadingState from "@/components/LoadingState";
import UrgencyBadge from "@/components/UrgencyBadge";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";

function ProviderResponseForm({ caseId, onSubmitted }: { caseId: string; onSubmitted: () => void }) {
  const [response, setResponse] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (!response.trim()) return;
    setSubmitting(true);
    try {
      await respondToCase(caseId, response.trim());
      setResponse("");
      toast.success("Response sent — your case is back with the reviewer.");
      onSubmitted();
    } catch (e: any) {
      toast.error(e?.message || "Couldn't send your response, please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="p-4">
      <p className="text-sm font-medium">Your response</p>
      <Textarea
        value={response}
        onChange={(e) => setResponse(e.target.value)}
        placeholder="Answer the reviewer's question here..."
        rows={3}
        className="mt-2"
      />
      <Button className="mt-3" disabled={!response.trim() || submitting} onClick={submit}>
        {submitting ? "Sending..." : "Send response"}
      </Button>
    </Card>
  );
}

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
          <UrgencyBadge slaDeadline={status.sla_deadline} />
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
