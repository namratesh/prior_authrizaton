import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { getReview, type ReviewResponse } from "@/store/api";
import StatusBadge from "@/components/StatusBadge";
import DecisionDetail from "./DecisionDetail";
import { Card } from "@/components/ui/card";

// Self-contained inline SVG illustration for the empty-inbox state.
function EmptyInboxArt() {
  return (
    <svg viewBox="0 0 200 140" className="mx-auto mb-4 h-32 w-48" aria-hidden>
      <defs>
        <linearGradient id="tray" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#d6e0f0" />
          <stop offset="100%" stopColor="#adc1e0" />
        </linearGradient>
      </defs>
      <ellipse cx="100" cy="122" rx="66" ry="8" fill="#e2e8f0" />
      <rect x="46" y="52" width="108" height="60" rx="10" fill="url(#tray)" />
      <path d="M46 84 h30 l10 14 h28 l10 -14 h30 v18 a10 10 0 0 1 -10 10 H56 a10 10 0 0 1 -10 -10 Z" fill="#eef2f9" />
      <rect x="70" y="24" width="60" height="40" rx="6" fill="#fff" stroke="#cbf4ea" strokeWidth="2" />
      <line x1="80" y1="36" x2="120" y2="36" stroke="#5fd4bd" strokeWidth="3" strokeLinecap="round" />
      <line x1="80" y1="46" x2="110" y2="46" stroke="#d6e0f0" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export default function InboxView({ caseIds }: { caseIds: string[] }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [reviews, setReviews] = useState<Record<string, ReviewResponse>>({});

  useEffect(() => {
    caseIds.forEach((id) => {
      if (!reviews[id]) {
        getReview(id)
          .then((r) => setReviews((prev) => ({ ...prev, [id]: r })))
          .catch(() => {});
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseIds]);

  if (selected) return <DecisionDetail caseId={selected} onBack={() => setSelected(null)} />;

  if (caseIds.length === 0) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <Card className="p-10 text-center">
          <EmptyInboxArt />
          <p className="font-medium">No past cases yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Submit a request and it will appear here with its decision and cost breakdown.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-3 p-6">
      {caseIds.map((id, i) => {
        const r = reviews[id];
        return (
          <motion.div
            key={id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <button onClick={() => setSelected(id)} className="w-full text-left">
              <Card className="flex items-center justify-between p-4 transition-shadow hover:shadow-elevated">
                <div>
                  <p className="text-sm font-medium">{r?.case_number || "Processing..."}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {r?.clinical?.requested_service_description || "Processing..."}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={r?.final_status} />
                  <ChevronRight size={16} className="text-muted-foreground" />
                </div>
              </Card>
            </button>
          </motion.div>
        );
      })}
    </div>
  );
}
