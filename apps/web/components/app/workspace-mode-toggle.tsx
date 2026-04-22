"use client";

import { useProposalStore, type BrainMode } from "@/lib/store";
import { cn } from "@/lib/utils";

const modes: { id: BrainMode; label: string }[] = [
  { id: "auto", label: "Auto" },
  { id: "enterprise", label: "Enterprise" },
  { id: "freelance", label: "Freelance win" },
];

type WorkspaceModeToggleProps = {
  className?: string;
  /** Tighter control for headers */
  size?: "default" | "compact";
};

export function WorkspaceModeToggle({ className, size = "default" }: WorkspaceModeToggleProps) {
  const brainMode = useProposalStore((s) => s.brainMode);
  const setBrainMode = useProposalStore((s) => s.setBrainMode);
  const compact = size === "compact";

  return (
    <div
      className={cn(
        "inline-flex flex-wrap items-center gap-0.5 rounded-full border border-border bg-muted/50 p-1 text-[13px] font-medium",
        compact && "text-[12px]",
        className,
      )}
      role="group"
      aria-label="Proposal mode"
    >
      {modes.map(({ id, label }) => (
        <button
          key={id}
          type="button"
          onClick={() => setBrainMode(id)}
          className={cn(
            "rounded-full transition-colors",
            compact ? "px-3 py-1.5" : "px-3.5 py-2",
            brainMode === id
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
