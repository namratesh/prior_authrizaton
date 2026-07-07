import { useMemo, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { ChevronLeft, ChevronRight, FileText } from "lucide-react";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";
import { Button } from "@/components/ui/button";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const PRICE_RE = /\$\s?[\d,]+(?:\.\d{2})?/;

// // DEMO-REAL: react-pdf's customTextRenderer runs once per real text item in
// the actual rendered PDF text layer — this isn't a canned overlay image.
// CPT/ICD-10 highlights match against the codes Intake actually extracted
// for this case (not a blind digit-pattern regex) so a 5-digit zip code
// can't be mistaken for a CPT code — price still uses a regex since dollar
// amounts aren't in a fixed extracted list.
function makeHighlighter(cptCodes: string[], icd10Codes: string[]) {
  return ({ str }: { str: string }): string => {
    if (PRICE_RE.test(str)) return `<mark style="background:rgba(224,0,0,0.35)">${str}</mark>`;
    if (icd10Codes.some((code) => code && str.includes(code))) {
      return `<mark style="background:rgba(37,99,235,0.35)">${str}</mark>`;
    }
    if (cptCodes.some((code) => code && str.includes(code))) {
      return `<mark style="background:rgba(250,204,21,0.45)">${str}</mark>`;
    }
    return str;
  };
}

const LEGEND = [
  { color: "bg-yellow-300", label: "CPT" },
  { color: "bg-blue-400", label: "ICD-10" },
  { color: "bg-radiant", label: "Price" },
];

export default function PdfViewer({
  caseId,
  cptCodes = [],
  icd10Codes = [],
}: {
  caseId: string;
  cptCodes?: string[];
  icd10Codes?: string[];
}) {
  const [numPages, setNumPages] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);
  const highlight = useMemo(() => makeHighlighter(cptCodes, icd10Codes), [cptCodes, icd10Codes]);

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card shadow-soft">
      <div className="flex items-center justify-between border-b border-border bg-[linear-gradient(120deg,rgba(38,70,131,0.06),rgba(25,158,136,0.06))] px-4 py-2.5">
        <span className="flex items-center gap-1.5 text-sm font-medium">
          <FileText size={15} className="text-navy-600" />
          Uploaded Document
        </span>
        <div className="flex items-center gap-1.5 text-sm">
          <Button
            variant="outline"
            size="icon"
            className="h-7 w-7"
            disabled={pageNumber <= 1}
            onClick={() => setPageNumber((p) => p - 1)}
          >
            <ChevronLeft size={15} />
          </Button>
          <span className="tabular-nums text-muted-foreground">
            {pageNumber} / {numPages || "?"}
          </span>
          <Button
            variant="outline"
            size="icon"
            className="h-7 w-7"
            disabled={pageNumber >= numPages}
            onClick={() => setPageNumber((p) => p + 1)}
          >
            <ChevronRight size={15} />
          </Button>
        </div>
      </div>
      <div className="flex gap-3 border-b border-border px-4 py-2 text-xs">
        {LEGEND.map(({ color, label }) => (
          <span key={label} className="flex items-center gap-1.5">
            <span className={`inline-block h-3 w-3 rounded-sm ${color}`} />
            {label}
          </span>
        ))}
      </div>
      <div className="flex-1 overflow-auto bg-muted/40 p-3">
        <Document
          file={`${API_URL}/api/v1/review/${caseId}/pdf`}
          onLoadSuccess={({ numPages }) => setNumPages(numPages)}
          loading={<p className="p-4 text-sm text-muted-foreground">Loading document...</p>}
          error={<p className="p-4 text-sm text-radiant">Could not load the PDF.</p>}
          className="flex justify-center"
        >
          <Page
            pageNumber={pageNumber}
            width={380}
            customTextRenderer={highlight}
            className="overflow-hidden rounded-lg shadow-elevated"
          />
        </Document>
      </div>
    </div>
  );
}
