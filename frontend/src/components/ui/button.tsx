import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 active:scale-[0.98]",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-soft hover:bg-primary/90",
        gradient:
          "text-white shadow-elevated bg-[linear-gradient(120deg,#264683,#199e88)] hover:brightness-110",
        radiant:
          "text-white shadow-elevated bg-[linear-gradient(120deg,#b30000,#e00000)] hover:brightness-110",
        success:
          "bg-teal-600 text-white shadow-soft hover:bg-teal-700",
        destructive:
          "bg-destructive text-destructive-foreground shadow-soft hover:bg-destructive/90",
        outline:
          "border border-border bg-card/60 backdrop-blur hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-11 rounded-lg px-6 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, children, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    // Gradient CTAs get a light sweep on hover — a subtle "futuristic" sheen
    // instead of a flat brightness bump. Skipped for asChild (Slot merges
    // props onto a single child, so we can't inject a sibling overlay span).
    const shimmer = !asChild && (variant === "gradient" || variant === "radiant");
    return (
      <Comp
        className={cn(
          buttonVariants({ variant, size, className }),
          shimmer && "group relative overflow-hidden"
        )}
        ref={ref}
        {...props}
      >
        {children}
        {shimmer && (
          <span
            aria-hidden
            className="pointer-events-none absolute inset-0 -translate-x-full bg-[linear-gradient(115deg,transparent_40%,rgba(255,255,255,0.4)_50%,transparent_60%)] group-hover:animate-shimmer"
          />
        )}
      </Comp>
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
