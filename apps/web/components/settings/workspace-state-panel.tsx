"use client";

import type { WorkspaceStateEcho } from "@bidforge/web-sdk";

type Props = {
  workspaceState: WorkspaceStateEcho | undefined;
};

function pickStr(v: unknown): string {
  return typeof v === "string" ? v : "";
}

export function WorkspaceStatePanel({ workspaceState }: Props) {
  if (!workspaceState || typeof workspaceState !== "object") return null;
  const rfp = workspaceState.rfp as Record<string, unknown> | undefined;
  const settings = workspaceState.settings as Record<string, unknown> | undefined;
  const memory = workspaceState.memory as Record<string, unknown> | undefined;
  const proposal = workspaceState.proposal as Record<string, unknown> | undefined;

  const title = pickStr(rfp?.title).trim();
  const source = pickStr(rfp?.source).trim();
  const tone = pickStr(settings?.tone).trim();
  const style = pickStr(settings?.writing_style).trim();
  const mode = pickStr(settings?.proposal_mode).trim();
  const rag = settings?.rag as Record<string, unknown> | undefined;
  const lastMode = pickStr(memory?.last_retrieval_mode).trim();

  if (!title && !tone && !style && !mode) return null;

  return (
    <div className="rounded-xl border border-border bg-card/60 p-5">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">Workspace state</p>
      <dl className="mt-4 grid gap-3 text-sm text-muted-foreground">
        {title ? (
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/80">
              Opportunity title
            </dt>
            <dd className="mt-1 text-[15px] font-medium text-foreground">{title}</dd>
          </div>
        ) : null}
        {source ? (
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/80">Source</dt>
            <dd className="mt-1 text-foreground">{source}</dd>
          </div>
        ) : null}
        {mode ? (
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/80">
              Default proposal mode
            </dt>
            <dd className="mt-1 text-foreground">{mode}</dd>
          </div>
        ) : null}
        {tone ? (
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/80">Tone</dt>
            <dd className="mt-1 line-clamp-3 text-foreground">{tone}</dd>
          </div>
        ) : null}
        {style ? (
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/80">
              Writing style
            </dt>
            <dd className="mt-1 line-clamp-3 text-foreground">{style}</dd>
          </div>
        ) : null}
        {rag && typeof rag === "object" ? (
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/80">RAG</dt>
            <dd className="mt-1 text-foreground">
              {rag.enabled === false ? "Off" : "On"}
              {rag.enabled !== false ? (
                <span className="text-muted-foreground">
                  {" "}
                  · enterprise {rag.enterprise_case_studies === false ? "off" : "on"} · freelance{" "}
                  {rag.freelance_win_memory === false ? "off" : "on"}
                </span>
              ) : null}
            </dd>
          </div>
        ) : null}
        {lastMode ? (
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/80">
              Pipeline mode
            </dt>
            <dd className="mt-1 text-foreground">{lastMode}</dd>
          </div>
        ) : null}
        {proposal && typeof proposal.score === "number" ? (
          <div>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground/80">
              Verifier score
            </dt>
            <dd className="mt-1 text-foreground">{String(proposal.score)}</dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}
