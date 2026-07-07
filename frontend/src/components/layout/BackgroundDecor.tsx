import { cn } from "@/lib/utils";

// Reusable blurred gradient-blob layer. All CSS/SVG-generated so the app stays
// self-contained (no external image fetching). `intense` is used on Login;
// the subtle default sits behind the authed app shell.
export default function BackgroundDecor({
  intense = false,
  className,
}: {
  intense?: boolean;
  className?: string;
}) {
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 -z-10 overflow-hidden", className)}
    >
      <div
        className={cn(
          "absolute -left-40 -top-40 h-[36rem] w-[36rem] rounded-full blur-3xl",
          intense ? "opacity-60" : "opacity-30"
        )}
        style={{ background: "radial-gradient(circle at center, rgba(47,185,160,0.55), transparent 70%)" }}
      />
      <div
        className={cn(
          "absolute -right-40 top-10 h-[32rem] w-[32rem] rounded-full blur-3xl",
          intense ? "opacity-55" : "opacity-25"
        )}
        style={{ background: "radial-gradient(circle at center, rgba(38,70,131,0.55), transparent 70%)" }}
      />
      <div
        className={cn(
          "absolute bottom-[-12rem] left-1/3 h-[30rem] w-[30rem] rounded-full blur-3xl",
          intense ? "opacity-45" : "opacity-20"
        )}
        style={{ background: "radial-gradient(circle at center, rgba(95,212,189,0.45), transparent 70%)" }}
      />
      <div className="absolute inset-0 bg-noise" />
    </div>
  );
}
