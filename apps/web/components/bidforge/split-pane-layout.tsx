import { cn } from "@/lib/utils";

type SplitPaneLayoutProps = {
  left: React.ReactNode;
  right: React.ReactNode;
  className?: string;
};

/**
 * Notion × Linear style split workspace: equal columns on large screens,
 * stacked on small with clear separation.
 */
export function SplitPaneLayout({ left, right, className }: SplitPaneLayoutProps) {
  return (
    <div
      className={cn(
        "grid gap-6 lg:grid-cols-2 lg:gap-0 lg:overflow-hidden lg:rounded-2xl lg:border lg:border-border lg:bg-card lg:shadow-sm",
        className,
      )}
    >
      <div className="min-h-0 lg:border-r lg:border-border lg:bg-muted/30 dark:lg:bg-white/[0.02]">
        {left}
      </div>
      <div className="min-h-0 lg:bg-card">{right}</div>
    </div>
  );
}
