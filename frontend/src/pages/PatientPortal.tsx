import { useState } from "react";
import { useAppStore } from "../store/useAppStore";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import SubmissionView from "./patient/SubmissionView";
import TimelineView from "./patient/TimelineView";
import InboxView from "./patient/InboxView";

type View = "submission" | "timeline" | "inbox";

const SUBTITLES: Record<View, string> = {
  submission: "Upload a prior authorization request PDF to get started.",
  timeline: "Track your case as our agents review it, step by step.",
  inbox: "Review past decisions and cost breakdowns.",
};

const TAB_LABELS: Record<View, string> = {
  submission: "Submission",
  timeline: "Living Timeline",
  inbox: "Decision Inbox",
};

export default function PatientPortal() {
  const [view, setView] = useState<View>("submission");
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);
  const { caseHistory, addCaseToHistory } = useAppStore();

  const handleUploaded = (caseId: string) => {
    addCaseToHistory(caseId);
    setActiveCaseId(caseId);
    setView("timeline");
  };

  return (
    <div>
      <div className="mx-auto max-w-2xl px-6 pt-10 text-center">
        <h1 className="font-display text-3xl font-bold tracking-tight text-gradient">
          Patient Portal
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">{SUBTITLES[view]}</p>
      </div>

      <div className="flex justify-center pt-6">
        <Tabs value={view} onValueChange={(v) => setView(v as View)}>
          <TabsList>
            {(["submission", "timeline", "inbox"] as View[]).map((v) => (
              <TabsTrigger key={v} value={v}>
                {TAB_LABELS[v]}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {view === "submission" && <SubmissionView onUploaded={handleUploaded} />}
      {view === "timeline" &&
        (activeCaseId ? (
          <TimelineView caseId={activeCaseId} />
        ) : (
          <div className="mx-auto max-w-2xl p-8 text-center text-muted-foreground">
            Upload a request first to see its timeline.
          </div>
        ))}
      {view === "inbox" && <InboxView caseIds={caseHistory} />}
    </div>
  );
}
