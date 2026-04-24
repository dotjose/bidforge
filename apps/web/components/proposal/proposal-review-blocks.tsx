"use client";

import { useMemo } from "react";
import type { TimelinePhase } from "@bidforge/web-sdk";
import { issuesToScoreBreakdown, stripReaderMarkdownArtifacts } from "@/lib/api/proposal-markdown";
import { cn } from "@/lib/utils";

const BUCKETS: {
  key: "coverage" | "weakClaims" | "risks" | "memoryGrounding";
  label: string;
  description: string;
}[] = [
  { key: "coverage", label: "Requirements coverage", description: "Gaps vs the stated brief or RFP." },
  { key: "weakClaims", label: "Specificity & tone", description: "Claims that read generic or hard to verify." },
  { key: "risks", label: "Compliance & risk", description: "Regulatory, contractual, or delivery risk flags." },
  { key: "memoryGrounding", label: "Evidence & positioning", description: "Memory, patterns, or differentiation signals." },
];

export function ProposalTimelineSection({
  timeline,
  className,
}: {
  timeline: TimelinePhase[];
  className?: string;
}) {
  const phases = useMemo(
    () =>
      timeline
        .map((t) => ({
          phase: stripReaderMarkdownArtifacts(t.phase || ""),
          duration: stripReaderMarkdownArtifacts(t.duration || ""),
        }))
        .filter((t) => t.phase || t.duration),
    [timeline],
  );

  if (!phases.length) return null;

  return (
    <section className={cn("mt-14 border-t border-border/60 pt-12", className)}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-xl font-semibold tracking-tight text-foreground md:text-2xl">
            Delivery timeline
          </h2>
          <p className="mt-1 max-w-xl text-[14px] leading-relaxed text-muted-foreground">
            Phases and timeboxes inferred for this opportunity — not a contractual schedule.
          </p>
        </div>
        <span className="rounded-full border border-border/80 bg-muted/40 px-3 py-1 text-[12px] font-medium tabular-nums text-muted-foreground">
          {phases.length} {phases.length === 1 ? "phase" : "phases"}
        </span>
      </div>

      <ol className="relative mt-8 space-y-0 pl-1">
        <span
          className="absolute left-[11px] top-3 bottom-3 w-px bg-gradient-to-b from-border via-border to-transparent md:left-[13px]"
          aria-hidden
        />
        {phases.map((row, i) => (
          <li key={i} className="relative pb-8 pl-10 last:pb-0 md:pl-11">
            <span
              className="absolute left-0 top-2 flex size-[22px] items-center justify-center rounded-full border-2 border-background bg-gradient-to-br from-blue-500/90 to-violet-600/90 text-[11px] font-bold text-white shadow-sm md:top-1.5 md:size-6 md:text-[12px]"
              aria-hidden
            >
              {i + 1}
            </span>
            <div className="rounded-2xl border border-border/80 bg-card/80 px-4 py-3.5 shadow-sm md:px-5 md:py-4">
              <p className="text-[15px] font-semibold leading-snug text-foreground md:text-[16px]">
                {row.phase || "Phase"}
              </p>
              {row.duration ? (
                <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground md:text-[15px]">{row.duration}</p>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function ProposalVerifierNotesSection({
  issues,
  className,
}: {
  issues: string[];
  className?: string;
}) {
  const breakdown = useMemo(() => issuesToScoreBreakdown(issues), [issues]);
  const blocks = useMemo(
    () => BUCKETS.map((b) => ({ ...b, items: breakdown[b.key].filter((x) => String(x).trim()) })).filter((b) => b.items.length > 0),
    [breakdown],
  );

  if (!blocks.length) return null;

  return (
    <section className={cn("mt-14 border-t border-border/60 pt-12", className)}>
      <details className="group rounded-2xl border border-border/60 bg-muted/10 px-4 py-3 dark:bg-muted/5 md:px-5 md:py-4">
        <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="font-display text-lg font-semibold tracking-tight text-foreground md:text-xl">
                Reviewer notes
              </h2>
              <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-muted-foreground">
                Verifier flags — optional; expand to tighten claims. Not a penalty list.
              </p>
            </div>
            <span className="shrink-0 rounded-full border border-border/70 bg-background px-2.5 py-1 text-[11px] font-medium text-muted-foreground group-open:hidden">
              Show
            </span>
            <span className="hidden shrink-0 rounded-full border border-border/70 bg-background px-2.5 py-1 text-[11px] font-medium text-muted-foreground group-open:inline-block">
              Hide
            </span>
          </div>
        </summary>
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {blocks.map((b) => (
            <div
              key={b.key}
              className="rounded-2xl border border-border/70 bg-muted/20 px-4 py-4 shadow-inner dark:bg-muted/10 md:px-5 md:py-5"
            >
              <p className="text-[13px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">{b.label}</p>
              <p className="mt-1 text-[12px] leading-snug text-muted-foreground/90">{b.description}</p>
              <ul className="mt-4 space-y-2.5">
                {b.items.map((item, j) => (
                  <li
                    key={`${b.key}-${j}`}
                    className="flex gap-2.5 text-[14px] leading-snug text-foreground/90 md:text-[15px]"
                  >
                    <span className="mt-2 size-1 shrink-0 rounded-full bg-amber-500/80 dark:bg-amber-400/90" aria-hidden />
                    <span>{stripReaderMarkdownArtifacts(item)}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </details>
    </section>
  );
}
