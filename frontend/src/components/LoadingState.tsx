import { Loader2 } from "lucide-react";

export default function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="mx-auto flex max-w-2xl items-center justify-center gap-2 p-12 text-muted-foreground">
      <Loader2 size={18} className="animate-spin text-teal-500" />
      <span className="text-sm">{label}</span>
    </div>
  );
}
