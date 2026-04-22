import { cn } from "@/lib/utils";

type WorkspaceTwoZoneProps = {
  input: React.ReactNode;
  workspace: React.ReactNode;
  className?: string;
};

/**
 * Primary workspace: large input (≈70%) + tabbed output (≈30%).
 */
export function WorkspaceTwoZone({ input, workspace, className }: WorkspaceTwoZoneProps) {
  return (
    <div
      className={cn(
        "flex min-h-[min(100dvh-7.5rem,920px)] flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm",
        "lg:flex-row lg:rounded-2xl",
        className,
      )}
    >
      <div className="flex min-h-0 min-w-0 flex-[7] flex-col border-b border-border bg-muted/20 lg:min-w-[70%] lg:border-b-0 lg:border-r dark:bg-white/[0.02]">
        {input}
      </div>
      <div className="flex min-h-0 min-w-0 flex-[3] flex-col bg-background lg:max-w-none">
        {workspace}
      </div>
    </div>
  );
}
