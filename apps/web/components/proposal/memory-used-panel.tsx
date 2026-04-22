"use client";

import type { MemorySummary } from "@bidforge/web-sdk";
import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

type MemoryUsedPanelProps = {
  memorySummary: MemorySummary | null;
  memoryGrounded: boolean | null;
  /** After at least one completed run in this session, empty states use post-run copy. */
  hasCompletedRun: boolean;
  pipelineMode?: "enterprise" | "freelance" | null;
  className?: string;
};

function ListBlock({
  title,
  items,
}: {
  title: string;
  items: { key: string; line: string }[];
}) {
  if (!items.length) return null;
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {title}
      </p>
      <ul className="mt-3 space-y-2">
        {items.map((it) => (
          <li key={it.key} className="text-[14px] leading-snug text-foreground/90">
            {it.line}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function MemoryUsedPanel({
  memorySummary,
  memoryGrounded,
  hasCompletedRun,
  className,
}: MemoryUsedPanelProps) {
  const fw = memorySummary?.freelance_win_patterns ?? [];
  const patterns = (memorySummary?.win_patterns ?? []).map((w, i) => ({
    key: `wp-${w.id ?? i}`,
    line: `${String(w.label ?? "Pattern")}${w.outcome ? ` (${String(w.outcome)})` : ""}`,
  }));
  const freelanceWins = fw
    .filter((w) => String(w.outcome ?? "").toLowerCase() !== "synthetic_seed")
    .map((w, i) => ({
      key: `fw-${w.id ?? i}`,
      line: `${String(w.label ?? "Win pattern")}${w.outcome ? ` (${String(w.outcome)})` : ""}`,
    }));
  const hasPatterns = patterns.length > 0 || freelanceWins.length > 0;
  const showPatterns = memoryGrounded === true && hasPatterns;

  if (!hasCompletedRun && memoryGrounded === null) {
    return (
      <div
        className={cn(
          "flex h-full min-h-0 flex-col border-b border-border px-4 py-5 xl:border-b-0",
          className,
        )}
      >
        <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          <Sparkles className="size-4 shrink-0 opacity-80" aria-hidden />
          Memory
        </p>
        <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">
          No relevant past wins for this proposal yet.
        </p>
      </div>
    );
  }

  if (!showPatterns) {
    return (
      <div
        className={cn(
          "flex h-full flex-col border-b border-border px-4 py-5 xl:border-b-0",
          className,
        )}
      >
        <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          <Sparkles className="size-4 shrink-0 opacity-80" aria-hidden />
          Memory
        </p>
        <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">
          No relevant past wins for this proposal yet.
        </p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex h-full flex-col overflow-y-auto border-b border-border px-4 py-5 xl:border-b-0",
        className,
      )}
    >
      <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        <Sparkles className="size-4" aria-hidden />
        Memory
      </p>
      <div className="mt-5 space-y-6">
        <ListBlock title="Enterprise patterns" items={patterns} />
        <ListBlock title="Freelance signals" items={freelanceWins} />
      </div>
    </div>
  );
}
