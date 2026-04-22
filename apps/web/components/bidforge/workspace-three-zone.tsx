import { cn } from "@/lib/utils";

type WorkspaceThreeZoneProps = {
  brief: React.ReactNode;
  output: React.ReactNode;
  sidebar: React.ReactNode;
  className?: string;
};

/**
 * Production workspace: brief (left) · structured output (center) · memory / insights (right).
 */
export function WorkspaceThreeZone({ brief, output, sidebar, className }: WorkspaceThreeZoneProps) {
  return (
    <div
      className={cn(
        "flex min-h-[min(100dvh-7.5rem,920px)] flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm",
        "xl:flex-row xl:items-stretch",
        className,
      )}
    >
      <aside className="flex min-h-0 min-w-0 flex-col border-b border-border bg-muted/20 dark:bg-white/[0.02] xl:w-[min(32%,420px)] xl:shrink-0 xl:border-b-0 xl:border-r">
        {brief}
      </aside>
      <main className="flex min-h-0 min-w-0 flex-1 flex-col border-b border-border bg-background xl:border-b-0 xl:border-r">
        {output}
      </main>
      <aside className="flex min-h-[220px] min-w-0 flex-col bg-muted/10 dark:bg-[#070a10]/80 xl:w-[min(30%,380px)] xl:shrink-0">
        {sidebar}
      </aside>
    </div>
  );
}
