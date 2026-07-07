import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { ClipboardCheck, Inbox as InboxIcon, ChevronRight, Check, Pencil, MessageSquare, Ban } from "lucide-react";
import { adjudicate, getAdminMetrics, getReview, type ReviewResponse } from "../store/api";
import { DEMO_REVIEWER_ID } from "../store/useAppStore";
import PdfViewer from "@/components/PdfViewer";
import ReviewForm, { type FieldDiffs } from "@/components/ReviewForm";
import RationalePanel from "@/components/RationalePanel";
import LoadingState from "@/components/LoadingState";
import UrgencyBadge from "@/components/UrgencyBadge";
import { is_expedite_client } from "../store/sla";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { toast } from "@/components/ui/sonner";

function CaseQueue({ onSelect }: { onSelect: (caseId: string) => void }) {
  const [cases, setCases] = useState<Awaited<ReturnType<typeof getAdminMetrics>>["cases"]>();

  useEffect(() => {
    getAdminMetrics().then((m) => setCases(m.cases.filter((c) => c.needs_human_review)));
  }, []);

  if (cases === undefined) return <LoadingState label="Loading case queue..." />;

  return (
    <div className="mx-auto max-w-3xl p-8">
      <div className="mb-1 flex items-center gap-2">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-[linear-gradient(135deg,#264683,#199e88)] text-white shadow-soft">
          <ClipboardCheck size={18} />
        </span>
        <h1 className="font-display text-2xl font-bold tracking-tight">Cases Awaiting Your Review</h1>
      </div>
      <p className="mb-6 text-sm text-muted-foreground">
        {cases.length} case{cases.length === 1 ? "" : "s"} flagged for human review.
      </p>

      {cases.length === 0 ? (
        <Card className="p-10 text-center">
          <InboxIcon size={32} className="mx-auto mb-3 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No cases currently need human review.</p>
        </Card>
      ) : (
        <div className="space-y-3">
          {cases.map((c, i) => (
            <motion.div
              key={c.case_id}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.06 }}
            >
              <button onClick={() => onSelect(c.case_id)} className="w-full text-left">
                <Card className="relative flex items-center justify-between overflow-hidden p-4 pl-5 transition-shadow hover:shadow-elevated">
                  <span className="absolute inset-y-0 left-0 w-1.5 bg-[linear-gradient(180deg,#264683,#199e88)]" />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold">{c.case_number}</p>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {c.requested_service_description || "Processing..."}
                    </p>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {c.flags.map((f) => (
                        <span
                          key={f}
                          className="rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700"
                        >
                          {f}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <UrgencyBadge slaDeadline={c.sla_deadline} />
                    <ChevronRight size={16} className="text-muted-foreground" />
                  </div>
                </Card>
              </button>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ReviewerPortal() {
  const { caseId } = useParams();
  const navigate = useNavigate();
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [diffs, setDiffs] = useState<FieldDiffs>({});
  const [denyReason, setDenyReason] = useState("");
  const [clarifyQuestion, setClarifyQuestion] = useState("");
  const [showClarify, setShowClarify] = useState(false);
  const [showDeny, setShowDeny] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (caseId) getReview(caseId).then(setReview);
  }, [caseId]);

  if (!caseId) return <CaseQueue onSelect={(id) => navigate(`/reviewer/${id}`)} />;
  if (!review) return <LoadingState label="Loading case..." />;

  const buildClinicalDiffs = () => {
    const out: Record<string, any> = {};
    if (diffs.cpt_codes !== undefined) out.cpt_codes = diffs.cpt_codes.split(",").map((s) => s.trim()).filter(Boolean);
    if (diffs.icd10_codes !== undefined) out.icd10_codes = diffs.icd10_codes.split(",").map((s) => s.trim()).filter(Boolean);
    if (diffs.billed_amount !== undefined) out.billed_amount = parseFloat(diffs.billed_amount);
    if (diffs.patient_zip !== undefined) out.patient_zip = diffs.patient_zip;
    if (diffs.provider_npi !== undefined) out.provider_npi = diffs.provider_npi;
    if (diffs.requested_service_description !== undefined)
      out.requested_service_description = diffs.requested_service_description;
    return out;
  };

  const submit = async (action: "approve" | "modify" | "deny" | "clarify" | "provider_responded") => {
    setSubmitting(true);
    try {
      const clinicalDiffs = buildClinicalDiffs();
      await adjudicate(caseId, {
        action,
        reviewer_id: DEMO_REVIEWER_ID,
        diffs: Object.keys(clinicalDiffs).length ? { clinical: clinicalDiffs } : {},
        question: action === "clarify" ? clarifyQuestion : undefined,
        original_reason: action === "provider_responded" ? review.routing?.interrupt_reason : undefined,
      });
      const updated = await getReview(caseId);
      setReview(updated);
      setShowClarify(false);
      setShowDeny(false);
      const MESSAGES: Record<typeof action, string> = {
        approve: "Case approved as is.",
        modify: "Modifications saved and case approved.",
        deny: "Case denied with justification recorded.",
        clarify: "Clarification requested — case awaiting provider response.",
        provider_responded: "Provider response recorded — case resumed.",
      };
      toast.success(MESSAGES[action]);
    } catch (e: any) {
      toast.error(e?.message || "Something went wrong submitting the decision.");
    } finally {
      setSubmitting(false);
    }
  };

  const lastRationaleEntry = [...review.agent_trace].reverse().find((t) => t.agent === "peer_review_auditor");
  const isExpedite = is_expedite_client(review.routing?.sla_deadline);
  const decided = review.final_status != null;

  return (
    <div className="flex h-[calc(100vh-64px)] flex-col overflow-hidden">
      <div className="flex shrink-0 items-center justify-between border-b border-border bg-card/70 px-5 py-3 backdrop-blur">
        <div>
          <p className="text-xs font-medium text-muted-foreground">Reviewing {review.case_number}</p>
          <p className="text-sm font-semibold">{review.clinical?.requested_service_description}</p>
        </div>
        <UrgencyBadge slaDeadline={review.routing?.sla_deadline} size="md" />
      </div>

      <div className="flex flex-1 gap-3 overflow-hidden p-3">
        <div className="w-[40%]">
          <PdfViewer
            caseId={caseId}
            cptCodes={review.clinical?.cpt_codes || []}
            icd10Codes={review.clinical?.icd10_codes || []}
          />
        </div>
        <div className="w-[30%]">
          <ReviewForm
            clinical={review.clinical}
            confidence={review.clinical?.extraction_confidence}
            diffs={diffs}
            onChange={(field, value) => setDiffs((d) => ({ ...d, [field]: value }))}
          />
        </div>
        <div className="w-[30%]">
          <RationalePanel
            needsHumanReview={review.needs_human_review}
            interruptReason={review.routing?.interrupt_reason}
            rationale={lastRationaleEntry?.rationale}
            policy={review.policy}
            financial={review.financial}
            isExpedite={isExpedite}
            relevantAgents={review.routing?.relevant_agents}
            queryClassificationReason={review.routing?.query_classification_reason}
          />
        </div>
      </div>

      {/* Floating glass action toolbar. */}
      <div className="shrink-0 px-3 pb-3">
        <div className="glass-card rounded-2xl px-4 py-3">
          {review.routing?.case_status === "awaiting_provider_response" && (
            <Alert variant="warning" className="mb-3 flex items-center justify-between gap-3">
              <AlertDescription>
                Awaiting Provider Response: {review.routing.interrupt_reason}
              </AlertDescription>
              {/* DEMO-MOCKED: manual stub button instead of a real provider-facing notification system. */}
              <Button size="sm" variant="secondary" disabled={submitting} onClick={() => submit("provider_responded")}>
                Provider Responded (stub)
              </Button>
            </Alert>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Button variant="success" disabled={decided || submitting} onClick={() => submit("approve")}>
              <Check size={16} />
              Approve as Is
            </Button>
            <Button
              variant="default"
              disabled={decided || submitting || Object.keys(diffs).length === 0}
              onClick={() => submit("modify")}
            >
              <Pencil size={16} />
              Modify & Approve
            </Button>
            <Button variant="outline" disabled={decided || submitting} onClick={() => setShowClarify(true)}>
              <MessageSquare size={16} />
              Request Clarification
            </Button>
            <Button
              variant="outline"
              className="border-radiant text-radiant hover:bg-red-50 hover:text-radiant"
              disabled={decided || submitting}
              onClick={() => setShowDeny(true)}
            >
              <Ban size={16} />
              Override to Deny
            </Button>
            {decided && (
              <span className="ml-auto text-sm font-medium">Case decided: {review.final_status}</span>
            )}
          </div>
        </div>
      </div>

      {/* Request Clarification dialog. */}
      <Dialog open={showClarify} onOpenChange={setShowClarify}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Request Clarification</DialogTitle>
            <DialogDescription>
              Send a free-text question to the provider. The case pauses at the same interrupt
              point as "Awaiting Provider Response".
            </DialogDescription>
          </DialogHeader>
          <Input
            placeholder="Question for the provider..."
            value={clarifyQuestion}
            onChange={(e) => setClarifyQuestion(e.target.value)}
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowClarify(false)}>
              Cancel
            </Button>
            <Button disabled={!clarifyQuestion.trim() || submitting} onClick={() => submit("clarify")}>
              Send
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Override to Deny dialog — mandatory justification. */}
      <Dialog open={showDeny} onOpenChange={setShowDeny}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Override to Deny</DialogTitle>
            <DialogDescription>
              A written justification is required and recorded in the audit trail.
            </DialogDescription>
          </DialogHeader>
          <Input
            placeholder="Justification for denial (required)..."
            value={denyReason}
            onChange={(e) => setDenyReason(e.target.value)}
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowDeny(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={!denyReason.trim() || submitting}
              onClick={() => submit("deny")}
            >
              Confirm Deny
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
