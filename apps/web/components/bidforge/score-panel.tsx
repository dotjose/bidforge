import { cn } from "@/lib/utils";

export type ScoreBreakdown = {
  coverage: string[];
  weakClaims: string[];
  risks: string[];
  memoryGrounding: string[];
};

type ScorePanelProps = {
  score: number | null;
  /** Consolidated issues shown first */
  issues?: string[];
  breakdown: ScoreBreakdown;
  className?: string;
  /** Freelance surfaces a lighter “first impression” framing; minimal = score + short bullets only. */
  variant?: "enterprise" | "freelance" | "minimal";
};

function List({
  title,
  items,
  dotClass,
}: {
  title: string;
  items: string[];
  dotClass: string;
}) {
  if (items.length === 0) {
    return null;
  }
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {title}
      </p>
      <ul className="mt-2 space-y-2">
        {items.map((item, i) => (
          <li
            key={i}
            className="flex gap-2.5 text-[13px] leading-snug text-muted-foreground"
          >
            <span
              className={cn("mt-2 size-1.5 shrink-0 rounded-full", dotClass)}
              aria-hidden
            />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ScorePanel({
  score,
  issues = [],
  breakdown,
  className,
  variant = "enterprise",
}: ScorePanelProps) {
  const emptyBreakdown =
    breakdown.coverage.length === 0 &&
    breakdown.weakClaims.length === 0 &&
    breakdown.risks.length === 0 &&
    (breakdown.memoryGrounding?.length ?? 0) === 0;

  const minimalBullets = issues.slice(0, 3);

  if (variant === "minimal") {
    return (
      <div
        className={cn(
          "rounded-2xl border border-border bg-gradient-to-br from-blue-500/8 via-card to-violet-500/8 p-6 shadow-sm dark:from-blue-500/10 dark:to-violet-500/10 md:p-8",
          className,
        )}
      >
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Score</p>
        <p className="mt-1 font-display text-5xl font-semibold tabular-nums tracking-tight text-foreground">
          {score ?? "—"}
          {score != null ? <span className="text-xl font-medium text-muted-foreground"> /100</span> : null}
        </p>
        {minimalBullets.length > 0 ? (
          <ul className="mt-6 space-y-2.5 border-t border-border/80 pt-6">
            {minimalBullets.map((item, i) => (
              <li key={i} className="flex gap-2.5 text-[14px] leading-snug text-foreground/90">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-amber-500/80 dark:bg-amber-400/90" aria-hidden />
                <span className="min-w-0">{item}</span>
              </li>
            ))}
          </ul>
        ) : score != null ? (
          <p className="mt-6 border-t border-border/80 pt-6 text-[14px] text-muted-foreground">
            No review notes for this draft.
          </p>
        ) : (
          <p className="mt-6 text-[14px] text-muted-foreground">Generate a proposal to see a score.</p>
        )}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-2xl border border-border bg-gradient-to-br from-blue-500/8 via-card to-violet-500/8 p-6 shadow-sm dark:from-blue-500/10 dark:to-violet-500/10 md:p-8",
        className,
      )}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {variant === "freelance" ? "First impression score" : "Review score"}
      </p>
      <p className="mt-1 font-display text-5xl font-semibold tabular-nums tracking-tight text-foreground">
        {score ?? "—"}
        {score != null ? (
          <span className="text-xl font-medium text-muted-foreground"> /100</span>
        ) : null}
      </p>

      <div className="mt-8 space-y-8 border-t border-border/80 pt-8">
        {issues.length > 0 ? (
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              Flagged items
            </p>
            <ul className="mt-2 space-y-2">
              {issues.map((item, i) => (
                <li
                  key={i}
                  className="rounded-lg border border-border/80 bg-background/60 px-3 py-2 text-[13px] leading-snug text-foreground/90"
                >
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <List
          title="Requirements coverage"
          items={breakdown.coverage}
          dotClass="bg-blue-500/80 dark:bg-sky-400/90"
        />
        <List
          title="Specificity & tone"
          items={breakdown.weakClaims}
          dotClass="bg-zinc-400 dark:bg-zinc-500"
        />
        <List
          title="Compliance & risk"
          items={breakdown.risks}
          dotClass="bg-amber-500 dark:bg-amber-400"
        />
        <List
          title="Evidence & positioning"
          items={breakdown.memoryGrounding ?? []}
          dotClass="bg-violet-500/90 dark:bg-violet-400/90"
        />
        {score == null && issues.length === 0 && emptyBreakdown ? (
          <p className="text-[13px] leading-relaxed text-muted-foreground">
            Generate a proposal to see score, issues, and flags.
          </p>
        ) : null}
      </div>
    </div>
  );
}
