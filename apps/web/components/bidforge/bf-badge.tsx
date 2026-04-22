import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const bfBadgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
  {
    variants: {
      variant: {
        status: "bg-muted text-muted-foreground ring-1 ring-border/80",
        statusSuccess:
          "bg-emerald-500/12 text-emerald-700 ring-1 ring-emerald-500/25 dark:text-emerald-300 dark:ring-emerald-500/20",
        statusInfo:
          "bg-blue-500/12 text-blue-800 ring-1 ring-blue-500/25 dark:text-blue-200 dark:ring-blue-500/20",
        score:
          "bg-foreground/5 text-foreground tabular-nums ring-1 ring-border dark:bg-white/10 dark:text-zinc-100",
        risk: "bg-amber-500/10 text-amber-900 ring-1 ring-amber-500/25 dark:text-amber-200 dark:ring-amber-500/20",
        neutral: "bg-muted/80 text-muted-foreground",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export type BfBadgeProps = React.HTMLAttributes<HTMLSpanElement> &
  VariantProps<typeof bfBadgeVariants>;

export function BfBadge({ className, variant, ...props }: BfBadgeProps) {
  return (
    <span className={cn(bfBadgeVariants({ variant }), className)} {...props} />
  );
}
