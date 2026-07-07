import { useState } from "react";
import { respondToCase } from "@/store/api";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/sonner";

export default function ProviderResponseForm({
  caseId,
  onSubmitted,
}: {
  caseId: string;
  onSubmitted: () => void;
}) {
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
