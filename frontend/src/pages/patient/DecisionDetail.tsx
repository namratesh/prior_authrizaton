import { useEffect, useState } from "react";
import { ArrowLeft, MessageCircle, Send } from "lucide-react";
import { getReview, type ReviewResponse } from "@/store/api";
import StatusBadge from "@/components/StatusBadge";
import LoadingState from "@/components/LoadingState";
import ProviderResponseForm from "@/components/ProviderResponseForm";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export default function DecisionDetail({ caseId, onBack }: { caseId: string; onBack: () => void }) {
  const [review, setReview] = useState<ReviewResponse | null>(null);

  const refresh = () => {
    getReview(caseId).then(setReview);
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  if (!review) return <LoadingState label="Loading decision..." />;

  const awaitingProviderResponse = review.routing?.case_status === "awaiting_provider_response";
  const interruptReason: string | undefined = review.routing?.interrupt_reason;

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft size={15} />
        Back to Decision Inbox
      </button>

      {awaitingProviderResponse && (
        <div className="rounded-lg border border-radiant/30 bg-red-50/60 p-3">
          <p className="text-xs font-semibold text-radiant">Reviewer's question</p>
          <p className="mt-1 text-sm text-foreground/90">
            {interruptReason?.replace(/^Awaiting Provider Response:\s*/, "") ||
              "The reviewer needs more information before this case can proceed."}
          </p>
        </div>
      )}
      {awaitingProviderResponse && <ProviderResponseForm caseId={caseId} onSubmitted={refresh} />}

      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-display text-lg font-semibold">
                Decision: {review.final_status ?? "Pending"}
              </h2>
              <p className="text-xs text-muted-foreground">Case {review.case_number}</p>
            </div>
            <StatusBadge status={review.final_status} />
          </div>

          <div className="rounded-xl border border-border bg-muted/50 p-4">
            <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground/90">
              {review.decision_letter || "Your decision letter is still being prepared."}
            </pre>
          </div>

          <Separator />

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="col-span-2">
              <p className="text-xs text-muted-foreground">Requested Service</p>
              <p className="font-medium">{review.clinical?.requested_service_description}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Billed Amount</p>
              <p className="font-medium">${review.financial?.billed_amount?.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Medicare Benchmark Rate</p>
              <p className="font-medium">
                {review.financial?.cms_benchmark_rate != null
                  ? `$${review.financial.cms_benchmark_rate.toFixed(2)}`
                  : "Unavailable"}
              </p>
            </div>
          </div>

          {/* DEMO-MOCKED: visual-only secure message thread stub, no backend messaging. */}
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="default" className="mt-2">
                <MessageCircle size={16} />
                Ask a Human
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Message your Care Team</DialogTitle>
                <DialogDescription>
                  Send a secure note about this decision. A member of our team will follow up.
                </DialogDescription>
              </DialogHeader>
              <div className="rounded-xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">
                <p className="flex items-center gap-2 font-medium">
                  <Send size={15} /> Message sent to your Care Team
                </p>
                <p className="mt-1 text-teal-800">
                  A member of our team will follow up with you shortly. (This is a demo
                  stub — no message is actually sent.)
                </p>
              </div>
            </DialogContent>
          </Dialog>
        </CardContent>
      </Card>
    </div>
  );
}
