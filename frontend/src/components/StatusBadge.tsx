import { CheckCircle2, XCircle, HelpCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const CONFIG: Record<string, { variant: "success" | "destructive" | "warning"; Icon: typeof CheckCircle2 }> = {
  Approved: { variant: "success", Icon: CheckCircle2 },
  Denied: { variant: "destructive", Icon: XCircle },
};

export default function StatusBadge({ status }: { status: string | null | undefined }) {
  const label = status || "Needs Info";
  const { variant, Icon } = CONFIG[label] || { variant: "warning" as const, Icon: HelpCircle };

  return (
    <Badge variant={variant}>
      <Icon size={12} />
      {label}
    </Badge>
  );
}
