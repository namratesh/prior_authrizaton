import { SlidersHorizontal } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

function ConfidenceBadge({ confidence }: { confidence: number | null | undefined }) {
  if (confidence == null) return null;
  const pct = Math.round(confidence * 100);
  const variant = pct >= 85 ? "success" : pct >= 60 ? "warning" : "destructive";
  return (
    <Badge variant={variant} className="px-1.5 py-0 text-[10px]">
      {pct}%
    </Badge>
  );
}

// Intake returns one calibrated confidence for the whole extraction, not a
// separate score per field — so every field shows the same badge value.
// (Documented simplification, not a bug: see CLAUDE.md's Reviewer Portal spec.)
export interface FieldDiffs {
  cpt_codes?: string;
  icd10_codes?: string;
  billed_amount?: string;
  patient_zip?: string;
  provider_npi?: string;
  requested_service_description?: string;
}

export default function ReviewForm({
  clinical,
  confidence,
  diffs,
  onChange,
}: {
  clinical: Record<string, any>;
  confidence: number | null;
  diffs: FieldDiffs;
  onChange: (field: keyof FieldDiffs, value: string) => void;
}) {
  const field = (label: string, key: keyof FieldDiffs, originalValue: string) => {
    const edited = diffs[key] !== undefined && diffs[key] !== originalValue;
    return (
      <div className="mb-4">
        <div className="mb-1.5 flex items-center gap-2">
          <label className="text-xs font-medium text-muted-foreground">{label}</label>
          <ConfidenceBadge confidence={confidence} />
          {edited && <span className="text-[10px] font-medium text-teal-600">edited</span>}
        </div>
        <Input
          className={edited ? "border-teal-400 ring-1 ring-teal-200" : ""}
          value={diffs[key] ?? originalValue}
          onChange={(e) => onChange(key, e.target.value)}
        />
      </div>
    );
  };

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card shadow-soft">
      <div className="flex items-center gap-1.5 border-b border-border bg-[linear-gradient(120deg,rgba(25,158,136,0.08),transparent)] px-4 py-2.5">
        <SlidersHorizontal size={15} className="text-teal-600" />
        <h3 className="text-sm font-medium">Extracted Fields</h3>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {field("CPT Code(s)", "cpt_codes", (clinical.cpt_codes || []).join(", "))}
        {field("ICD-10 Code(s)", "icd10_codes", (clinical.icd10_codes || []).join(", "))}
        {field("Billed Amount", "billed_amount", String(clinical.billed_amount ?? ""))}
        {field("Patient Zip", "patient_zip", clinical.patient_zip ?? "")}
        {field("Provider NPI", "provider_npi", clinical.provider_npi ?? "")}
        {field(
          "Requested Service Description",
          "requested_service_description",
          clinical.requested_service_description ?? ""
        )}
      </div>
    </div>
  );
}
