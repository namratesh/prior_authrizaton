import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { UploadCloud, FileText } from "lucide-react";
import { uploadCase } from "@/store/api";
import { MVP_PATIENT } from "@/store/useAppStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

const FIELDS: { label: string; key: keyof typeof MVP_PATIENT }[] = [
  { label: "Patient Name", key: "name" },
  { label: "Date of Birth", key: "dob" },
  { label: "Member ID", key: "memberId" },
  { label: "Zip Code", key: "zip" },
];

export default function SubmissionView({ onUploaded }: { onUploaded: (caseId: string) => void }) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const hasQuery = query.trim().length > 0;

  const handleFile = async (file: File) => {
    if (!hasQuery) {
      setError("Please describe what you're requesting before uploading.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const { case_id } = await uploadCase(file, query.trim());
      onUploaded(case_id);
    } catch (e: any) {
      setError(e.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Your Information</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 text-sm">
          {FIELDS.map(({ label, key }) => (
            <div key={key}>
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="font-medium">{MVP_PATIENT[key]}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="mb-2 flex items-center gap-2">
            <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-navy-100 text-[11px] font-semibold text-navy-700">
              1
            </span>
            <label className="text-sm font-medium">What are you requesting?</label>
          </div>
          <Textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. Please check if this knee replacement is covered and whether the billed cost is fair."
            rows={3}
            className="mt-2"
          />
          <p className="mt-1.5 text-xs text-muted-foreground">
            This tells us which checks to run on your case — we'll detect the CPT/ICD-10 codes and
            requested service directly from your document after you upload it.
          </p>
        </CardContent>
      </Card>

      <motion.div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const file = e.dataTransfer.files?.[0];
          if (file) handleFile(file);
        }}
        onClick={() => hasQuery && inputRef.current?.click()}
        animate={dragOver ? { scale: 1.01 } : { scale: 1 }}
        className={cn(
          "rounded-2xl border-2 border-dashed p-14 text-center transition-colors",
          !hasQuery
            ? "cursor-not-allowed border-border bg-card/50 opacity-60"
            : dragOver
            ? "cursor-pointer border-radiant bg-red-50/70 shadow-glow"
            : "cursor-pointer border-border bg-card/70 hover:border-teal-400 hover:bg-teal-50/40"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          disabled={!hasQuery}
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        <div
          className={cn(
            "mx-auto mb-4 grid h-16 w-16 place-items-center rounded-2xl transition-colors",
            dragOver ? "bg-radiant text-white" : "bg-muted text-muted-foreground"
          )}
        >
          {uploading ? <FileText size={30} className="animate-pulse" /> : <UploadCloud size={30} />}
        </div>
        <p className="font-display text-lg font-semibold">
          {uploading ? "Uploading..." : (
            <>
              <span className="mr-2 inline-grid h-5 w-5 place-items-center rounded-full bg-navy-100 align-middle text-[11px] font-semibold text-navy-700">
                2
              </span>
              Drag &amp; drop your Prior Authorization PDF
            </>
          )}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {hasQuery ? "or click to browse" : "Describe your request above first"}
        </p>
      </motion.div>
      {error && <p className="text-sm text-radiant">{error}</p>}
    </div>
  );
}
