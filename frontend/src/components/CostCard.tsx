import { motion } from "framer-motion";
import { Wallet } from "lucide-react";
import { Card } from "@/components/ui/card";

export default function CostCard({ estimate }: { estimate: number | null }) {
  if (estimate == null) return null;
  return (
    <Card className="relative overflow-hidden border-teal-100">
      <div
        aria-hidden
        className="pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full blur-2xl"
        style={{ background: "radial-gradient(circle, rgba(47,185,160,0.28), transparent 70%)" }}
      />
      <div className="relative p-6">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Wallet size={16} className="text-teal-600" />
          <h3 className="text-sm font-medium">Estimated Out-of-Pocket Cost</h3>
        </div>
        <motion.p
          initial={{ opacity: 0, filter: "blur(8px)", y: 6 }}
          animate={{ opacity: 1, filter: "blur(0px)", y: 0 }}
          transition={{ duration: 0.5 }}
          className="mt-1 font-display text-4xl font-bold text-gradient"
        >
          ${estimate.toFixed(2)}
        </motion.p>
        <p className="mt-2 text-xs text-muted-foreground">
          Based on the Medicare benchmark rate for your requested service. This is an
          estimate, not your final bill.
        </p>
      </div>
    </Card>
  );
}
