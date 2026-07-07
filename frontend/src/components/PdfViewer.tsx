import { useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { ChevronLeft, ChevronRight, FileText } from "lucide-react";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";
import { Button } from "@/components/ui/button";
import { API_URL } from "@/store/api";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

const PRICE_RE = /\$\s?[\d,]+(?:\.\d{2})?/;

// Matches the billed amount regardless of whether the PDF renders it with a
// thousands separator, a trailing ".00", or neither (e.g. 1234, 1,234, 1234.00).
function billedAmountVariants(billedAmount?: number): string[] {
  if (billedAmount == null || Number.isNaN(billedAmount)) return [];
  const fixed = billedAmount.toFixed(2);
  const withCommas = billedAmount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const noDecimals = String(Math.trunc(billedAmount));
  return Array.from(new Set([fixed, withCommas, noDecimals]));
}

// DEMO-REAL: react-pdf's customTextRenderer runs once per real text item in
// the actual rendered PDF text layer — this isn't a canned overlay image.
// CPT/ICD-10/billed-amount highlights match against values Intake actually
// extracted for this case (not a blind digit-pattern regex) so a 5-digit zip
// code can't be mistaken for a CPT code. Any other dollar figure (deductible,
// copay, subtotal, etc.) is highlighted distinctly so it's never confused
// with the billed amount being adjudicated.
function makeHighlighter(cptCodes: string[], icd10Codes: string[], billedAmount?: number) {
  const billedVariants = billedAmountVariants(billedAmount);
  return ({ str }: { str: string }): string => {
    if (billedVariants.some((v) => str.includes(v))) {
      return `<mark style="background:rgba(224,0,0,0.35)">${str}</mark>`;
    }
    if (PRICE_RE.test(str)) return `<mark style="background:rgba(148,163,184,0.4)">${str}</mark>`;
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
  { color: "bg-radiant", label: "Billed Amount" },
  { color: "bg-slate-400", label: "Other $ amount" },
];

export default function PdfViewer({
  caseId,
  cptCodes = [],
  icd10Codes = [],
  billedAmount,
}: {
  caseId: string;
  cptCodes?: string[];
  icd10Codes?: string[];
  billedAmount?: number;
}) {
  const [numPages, setNumPages] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);
  const highlight = useMemo(
    () => makeHighlighter(cptCodes, icd10Codes, billedAmount),
    [cptCodes, icd10Codes, billedAmount]
  );

  const containerRef = useRef<HTMLDivElement>(null);
  const [pageWidth, setPageWidth] = useState(380);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width) setPageWidth(Math.max(240, Math.min(width - 24, 900)));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

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
            aria-label="Previous page"
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
            aria-label="Next page"
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
      <div ref={containerRef} className="flex-1 overflow-auto bg-muted/40 p-3">
        <Document
          file={`${API_URL}/api/v1/review/${caseId}/pdf`}
          onLoadSuccess={({ numPages }) => setNumPages(numPages)}
          loading={<p className="p-4 text-sm text-muted-foreground">Loading document...</p>}
          error={<p className="p-4 text-sm text-radiant">Could not load the PDF.</p>}
          className="flex justify-center"
        >
          <Page
            pageNumber={pageNumber}
            width={pageWidth}
            customTextRenderer={highlight}
            className="overflow-hidden rounded-lg shadow-elevated"
          />
        </Document>
      </div>
    </div>
  );
}
