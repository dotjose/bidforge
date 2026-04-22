"use client";

import type { ProposalRunSummary } from "@bidforge/web-sdk";
import { BidForgeClient, BidForgeApiError } from "@bidforge/web-sdk";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { FileText, Loader2 } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type SavedProposalRunsProps = {
  /** Shown when the API returns an empty list (not loading). */
  emptyTitle: string;
  emptyBody: string;
  /** When false, omit the large CTA under the empty message. */
  showEmptyCta?: boolean;
  className?: string;
};

export function SavedProposalRuns({
  emptyTitle,
  emptyBody,
  showEmptyCta = true,
  className,
}: SavedProposalRunsProps) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [runs, setRuns] = useState<ProposalRunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const client = useMemo(
    () => new BidForgeClient({ getToken: () => getToken() }),
    [getToken],
  );

  useEffect(() => {
    if (!isLoaded || !isSignedIn) {
      setRuns(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      setError(null);
      try {
        const list = await client.listProposalRuns();
        if (!cancelled) setRuns(list);
      } catch (e) {
        if (cancelled) return;
        const msg =
          e instanceof BidForgeApiError ? e.message : (e as Error).message || "Could not load history.";
        setError(msg);
        setRuns([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client, isLoaded, isSignedIn]);

  if (!isLoaded) {
    return (
      <div className={cn("flex items-center gap-2 text-sm text-muted-foreground", className)}>
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Loading…
      </div>
    );
  }

  if (!isSignedIn) {
    return (
      <p className={cn("text-base text-muted-foreground", className)}>Sign in to see saved proposals.</p>
    );
  }

  if (runs === null) {
    return (
      <div className={cn("flex items-center gap-2 text-sm text-muted-foreground", className)}>
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Loading proposals…
      </div>
    );
  }

  if (error) {
    return (
      <p className={cn("text-sm text-destructive", className)} role="alert">
        {error}
      </p>
    );
  }

  if (runs.length === 0) {
    return (
      <div className={cn("text-center", className)}>
        {emptyTitle ? (
          <p className="font-display text-lg font-semibold text-foreground">{emptyTitle}</p>
        ) : null}
        {emptyBody ? (
          <p className="mx-auto mt-3 max-w-md text-base leading-relaxed text-muted-foreground">{emptyBody}</p>
        ) : null}
        {showEmptyCta ? (
          <Link
            href="/proposal"
            className={cn(
              buttonVariants({ size: "lg" }),
              "mt-8 inline-flex h-12 items-center justify-center rounded-xl px-8 text-[15px] font-semibold",
            )}
          >
            Open workspace
          </Link>
        ) : null}
      </div>
    );
  }

  return (
    <ul className={cn("divide-y divide-border rounded-xl border border-border bg-card/60", className)}>
      {runs.map((r) => (
        <li key={r.id}>
          <Link
            href={`/proposal?run=${encodeURIComponent(r.id)}`}
            className="flex items-start gap-3 px-4 py-4 transition-colors hover:bg-muted/40 md:px-5"
          >
            <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-foreground">{r.title || "Saved proposal"}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Score {r.score}/100 · {r.pipeline_mode}
                {r.created_at ? ` · ${r.created_at.slice(0, 10)}` : ""}
              </p>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
