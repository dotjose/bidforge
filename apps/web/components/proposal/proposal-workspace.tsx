"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  BookmarkPlus,
  Download,
  Loader2,
  Printer,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Upload,
  Wand2,
} from "lucide-react";
import { UserButton, SignInButton } from "@clerk/nextjs";
import type {
  CrossProposalDiffPayload,
  MemorySummary,
  ProposalPayload,
  TimelinePhase,
} from "@bidforge/web-sdk";
import { BidForgeApiError, normalizedDocumentToPlain } from "@bidforge/web-sdk";
import type { BrainMode } from "@/lib/store";
import { useProposalStore } from "@/lib/store";
import { WorkspaceWritingLayout } from "@/components/bidforge/workspace-writing-layout";
import { ScorePanel } from "@/components/bidforge/score-panel";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ProposalDocument } from "@/components/proposal/proposal-document";
import { MemoryUsedPanel } from "@/components/proposal/memory-used-panel";
import { filterProposalMarkdownForReader } from "@/components/proposal/filter-proposal-markdown";
import { useProposalRun } from "@/lib/api/hooks/use-proposal-run";
import { memorySummaryToInsightBullets } from "@/lib/memory-insights";
import {
  issuesToScoreBreakdown,
  printProposalAsPdf,
  proposalPayloadToMarkdown,
  timelineToMarkdown,
} from "@/lib/api/proposal-markdown";
import { ThemeToggle } from "@/components/bidforge/theme-toggle";
import { WorkspaceModeToggle } from "@/components/app/workspace-mode-toggle";
import { useDebouncedCallback } from "@/lib/use-debounced-callback";

export type ProposalWorkspaceProps = {
  initialRunId?: string | null;
};

const emptyBreakdown = {
  coverage: [] as string[],
  weakClaims: [] as string[],
  risks: [] as string[],
  memoryGrounding: [] as string[],
};

function pipelineFromBrainMode(m: BrainMode): "auto" | "enterprise" | "freelance" {
  if (m === "auto") return "auto";
  if (m === "freelance") return "freelance";
  return "enterprise";
}

export function ProposalWorkspace({ initialRunId = null }: ProposalWorkspaceProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [briefDraft, setBriefDraft] = useState("");
  const [titleDraft, setTitleDraft] = useState("");
  const [patternOpen, setPatternOpen] = useState(false);
  const [patternBody, setPatternBody] = useState("");
  const [patternTitle, setPatternTitle] = useState("Win pattern");
  const [patternTags, setPatternTags] = useState("");
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const jobDescription = useProposalStore((s) => s.jobDescription);
  const generated = useProposalStore((s) => s.generated);
  const score = useProposalStore((s) => s.score);
  const issues = useProposalStore((s) => s.issues);
  const scoreBreakdown = useProposalStore((s) => s.scoreBreakdown);
  const memoryGrounded = useProposalStore((s) => s.memoryGrounded);
  const memorySummary = useProposalStore((s) => s.memorySummary);
  const sectionAttributions = useProposalStore((s) => s.sectionAttributions);
  const timeline = useProposalStore((s) => s.timeline);
  const brainMode = useProposalStore((s) => s.brainMode);
  const lastPipelineMode = useProposalStore((s) => s.lastPipelineMode);
  const replyLikelihood0_100 = useProposalStore((s) => s.replyLikelihood0_100);
  const lastCritique = useProposalStore((s) => s.lastCritique);
  const proposalTitle = useProposalStore((s) => s.proposalTitle);
  const crossProposalDiff = useProposalStore((s) => s.crossProposalDiff);
  const persistedRunId = useProposalStore((s) => s.persistedRunId);
  const proposalSections = useProposalStore((s) => s.proposalSections);
  const setJobDescription = useProposalStore((s) => s.setJobDescription);
  const setBrainMode = useProposalStore((s) => s.setBrainMode);
  const setProposalTitle = useProposalStore((s) => s.setProposalTitle);
  const setResult = useProposalStore((s) => s.setResult);

  const { state, runDebounced, runNow, rfpMaxChars, isAuthReady, isSignedIn, apiClient } =
    useProposalRun();

  const [draftIntensity, setDraftIntensity] = useState<"balanced" | "strong" | "weak">("balanced");
  const [hookDraft, setHookDraft] = useState("");
  const settingsHydrated = useRef(false);

  const debouncedSyncBrief = useDebouncedCallback((value: string) => {
    setJobDescription(value);
  }, 450);

  useEffect(() => {
    setBriefDraft(jobDescription);
  }, [jobDescription]);

  useEffect(() => {
    setTitleDraft((proposalTitle ?? "").trim());
  }, [proposalTitle]);

  useEffect(() => {
    if (!isAuthReady || !isSignedIn || settingsHydrated.current) return;
    settingsHydrated.current = true;
    let cancelled = false;
    void (async () => {
      try {
        const s = await apiClient.getWorkspaceSettings();
        if (cancelled) return;
        if (s.proposal_mode === "auto" || s.proposal_mode === "enterprise" || s.proposal_mode === "freelance") {
          setBrainMode(s.proposal_mode);
        }
      } catch {
        /* keep default */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiClient, isAuthReady, isSignedIn, setBrainMode]);

  useEffect(() => {
    const rid = initialRunId?.trim();
    if (!rid || !isSignedIn || !isAuthReady) return;
    let cancelled = false;
    void (async () => {
      setActionMsg(null);
      try {
        const d = await apiClient.getProposalRun(rid);
        if (cancelled) return;
        const raw = d.proposal_output?.proposal;
        if (!raw || typeof raw !== "object") {
          setActionMsg("That saved proposal could not be loaded.");
          return;
        }
        const proposal = raw as ProposalPayload;
        const md = proposalPayloadToMarkdown(proposal);
        const issueStrings = Array.isArray(d.issues) ? d.issues.map((x) => String(x)) : [];
        const breakdown = issuesToScoreBreakdown(issueStrings);
        const mem = (d.proposal_output.memory_used as MemorySummary | undefined) ?? {
          similar_proposals: [],
          win_patterns: [],
          methodology_blocks: [],
          freelance_win_patterns: [],
        };
        const po = d.proposal_output as Record<string, unknown>;
        const diffRaw = po.cross_proposal_diff;
        const cross =
          diffRaw && typeof diffRaw === "object" ? (diffRaw as CrossProposalDiffPayload) : null;
        setJobDescription(d.rfp_input);
        setBrainMode(d.pipeline_mode === "freelance" ? "freelance" : "enterprise");
        setResult({
          generated: md,
          score: d.score,
          issues: issueStrings,
          suggestions: [],
          scoreBreakdown: breakdown,
          traceId: d.trace_id,
          memoryGrounded:
            typeof (d.proposal_output as { memory_grounded?: boolean }).memory_grounded === "boolean"
              ? Boolean((d.proposal_output as { memory_grounded?: boolean }).memory_grounded)
              : Boolean(proposal.memory_grounded),
          groundingWarning: null,
          memorySummary: mem,
          sectionAttributions: proposal.section_attributions ?? null,
          timeline: (d.proposal_output.timeline as TimelinePhase[] | undefined) ?? [],
          proposalSections: proposal.sections ?? null,
          lastPipelineMode: d.pipeline_mode === "freelance" ? "freelance" : "enterprise",
          replyLikelihood0_100: null,
          lastCritique: null,
          lastHook: proposal.freelance?.hook ?? proposal.hook?.hook ?? null,
          proposalTitle: d.title?.trim() ? d.title.trim() : null,
          persistedRunId: d.id,
          crossProposalDiff: cross,
        });
        setHookDraft(proposal.freelance?.hook ?? proposal.hook?.hook ?? "");
      } catch (e) {
        if (cancelled) return;
        const msg =
          e instanceof BidForgeApiError ? e.message : (e as Error).message || "Could not load proposal.";
        setActionMsg(msg);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [initialRunId, isSignedIn, isAuthReady, apiClient, setJobDescription, setBrainMode, setResult]);

  useEffect(() => {
    if (state.status !== "success") return;
    const md = proposalPayloadToMarkdown(state.data.proposal);
    const breakdown = issuesToScoreBreakdown(state.data.issues);
    const mem: MemorySummary =
      state.data.memory_used ??
      state.data.proposal.memory_summary ??
      ({
        similar_proposals: [],
        win_patterns: [],
        methodology_blocks: [],
      } as MemorySummary);
    const crit = state.data.critique;
    setResult({
      generated: md,
      score: state.data.score,
      issues: state.data.issues,
      suggestions: [],
      scoreBreakdown: breakdown,
      traceId: state.data.run_id || state.data.trace_id,
      memoryGrounded: state.data.memory_grounded,
      groundingWarning: state.data.grounding_warning ?? null,
      memorySummary: mem,
      sectionAttributions: state.data.proposal.section_attributions ?? null,
      timeline: state.data.timeline ?? [],
      proposalSections: state.data.proposal.sections ?? null,
      lastPipelineMode: state.data.pipeline_mode,
      replyLikelihood0_100: state.data.reply_likelihood_0_100 ?? null,
      lastCritique: crit
        ? {
            improvements: Array.isArray(crit.improvements) ? crit.improvements : [],
            reply_probability_delta:
              typeof crit.reply_probability_delta === "string"
                ? crit.reply_probability_delta
                : undefined,
            top1_style_rewrite:
              typeof crit.top1_style_rewrite === "string" ? crit.top1_style_rewrite : undefined,
          }
        : null,
      lastHook: state.data.hook?.hook ?? null,
      proposalTitle: state.data.title?.trim() ? state.data.title.trim() : null,
      persistedRunId: state.data.persisted_run_id ?? null,
      crossProposalDiff: state.data.cross_proposal_diff ?? null,
    });
    setHookDraft(state.data.hook?.hook ?? "");
    setPatternOpen(false);
    setActionMsg(null);
  }, [state, setResult]);

  const ingestFile = useCallback(
    async (f: File) => {
      if (!isSignedIn) {
        setActionMsg("Sign in to normalize PDF or Word uploads.");
        return;
      }
      const name = f.name.toLowerCase();
      const isTxt = f.type === "text/plain" || name.endsWith(".txt");
      const isPdf = f.type === "application/pdf" || name.endsWith(".pdf");
      const isDocx =
        f.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
        name.endsWith(".docx");

      setActionBusy(true);
      setActionMsg(null);
      try {
        if (isTxt) {
          const reader = new FileReader();
          const text = await new Promise<string>((resolve, reject) => {
            reader.onerror = () => reject(new Error("Could not read file."));
            reader.onload = () => resolve(String(reader.result ?? ""));
            reader.readAsText(f);
          });
          const norm = await apiClient.normalizeWorkspaceDocument({
            source: "text",
            text: text.trim(),
          });
          const plain = normalizedDocumentToPlain(norm);
          setBriefDraft(plain);
          setJobDescription(plain);
          setActionMsg("Brief loaded from text file.");
          return;
        }
        if (isPdf) {
          const norm = await apiClient.normalizeWorkspaceDocument({
            source: "pdf",
            file: f,
            filename: f.name,
          });
          const plain = normalizedDocumentToPlain(norm);
          setBriefDraft(plain);
          setJobDescription(plain);
          setActionMsg("Text extracted from PDF into the brief field.");
          return;
        }
        if (isDocx) {
          const norm = await apiClient.normalizeWorkspaceDocument({
            source: "docx",
            file: f,
            filename: f.name,
          });
          const plain = normalizedDocumentToPlain(norm);
          setBriefDraft(plain);
          setJobDescription(plain);
          setActionMsg("Text extracted from Word into the brief field.");
          return;
        }
        setActionMsg("Use PDF, TXT, or Word—or paste your brief.");
      } catch (err) {
        const msg =
          err instanceof BidForgeApiError ? err.message : (err as Error).message || "Upload failed.";
        setActionMsg(msg);
      } finally {
        setActionBusy(false);
      }
    },
    [apiClient, isSignedIn, setJobDescription],
  );

  const onFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      e.target.value = "";
      if (!f) return;
      await ingestFile(f);
    },
    [ingestFile],
  );

  const submitPattern = useCallback(async () => {
    const body = patternBody.trim();
    if (!body.length) {
      setActionMsg("Add pattern text before saving.");
      return;
    }
    setActionBusy(true);
    setActionMsg(null);
    try {
      const tags = patternTags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      await apiClient.postWinPattern({
        content: body,
        title: patternTitle.trim() || "Win pattern",
        tags,
        pattern_kind: lastPipelineMode === "freelance" ? "freelance_win_pattern" : "win_pattern",
      });
      setActionMsg("Saved to your reusable snippets.");
      setPatternOpen(false);
    } catch (e) {
      const msg =
        e instanceof BidForgeApiError ? e.message : (e as Error).message || "Request failed";
      setActionMsg(msg);
    } finally {
      setActionBusy(false);
    }
  }, [apiClient, lastPipelineMode, patternBody, patternTags, patternTitle]);

  const onPrintPdf = useCallback(() => {
    const docTitle = (titleDraft || proposalTitle || "").trim() || undefined;
    printProposalAsPdf(generated, undefined, docTitle);
  }, [generated, proposalTitle, titleDraft]);

  const onDownloadServerPdf = useCallback(async () => {
    if (!proposalSections) {
      setActionMsg("Generate a proposal before exporting PDF.");
      return;
    }
    setActionBusy(true);
    setActionMsg(null);
    try {
      const exportTitle = (titleDraft || proposalTitle || "").trim();
      const bullets = memorySummaryToInsightBullets(memorySummary ?? undefined);
      const blob = await apiClient.exportProposalPdf({
        title: exportTitle || "Proposal",
        sections: {
          executive_summary: proposalSections.executive_summary,
          technical_approach: proposalSections.technical_approach,
          delivery_plan: proposalSections.delivery_plan,
          risk_management: proposalSections.risk_management,
        },
        timeline,
        pipeline_mode: lastPipelineMode === "freelance" ? "freelance" : "enterprise",
        score: score ?? undefined,
        issues: issues.slice(0, 12),
        memory_insight_bullets: bullets.length ? bullets : undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "proposal-export.pdf";
      a.click();
      URL.revokeObjectURL(url);
      setActionMsg("PDF downloaded.");
    } catch (e) {
      const msg =
        e instanceof BidForgeApiError ? e.message : (e as Error).message || "Export failed";
      setActionMsg(msg);
    } finally {
      setActionBusy(false);
    }
  }, [
    apiClient,
    issues,
    memorySummary,
    proposalSections,
    score,
    timeline,
    lastPipelineMode,
    proposalTitle,
    titleDraft,
  ]);

  const loading = state.status === "loading";
  const errorMsg =
    state.status === "error"
      ? state.code
        ? `${state.code}: ${state.message}`
        : state.message
      : null;

  const briefForSubmit = briefDraft.trim();
  const canSubmit =
    isAuthReady &&
    isSignedIn &&
    briefForSubmit.length > 0 &&
    !loading &&
    briefForSubmit.length <= rfpMaxChars;

  const timelineMd = timelineToMarkdown(timeline);
  const isFreelanceRun = lastPipelineMode === "freelance";
  const runWarnings = state.status === "success" ? (state.data.insights?.warnings ?? []) : [];
  const runDegraded = state.status === "success" && state.data.status === "degraded";
  const verifierSuggestions =
    state.status === "success" ? (state.data.suggestions ?? []).filter((s) => String(s).trim()) : [];

  const readerMarkdown = useMemo(() => filterProposalMarkdownForReader(generated), [generated]);

  const insightsAttributions =
    sectionAttributions?.filter(
      (a) => Array.isArray(a.based_on_memory) && a.based_on_memory.length > 0,
    ) ?? [];

  const flushTitle = useCallback(() => {
    const t = titleDraft.trim();
    setProposalTitle(t.length ? t : null);
  }, [titleDraft, setProposalTitle]);

  const onSaveLink = useCallback(() => {
    if (persistedRunId) {
      const url = `${window.location.origin}/proposal?run=${encodeURIComponent(persistedRunId)}`;
      void navigator.clipboard.writeText(url).then(
        () => setActionMsg("Link to this saved run copied."),
        () => setActionMsg("Could not copy link."),
      );
      return;
    }
    setActionMsg("Generate a proposal first—it is added to your saved runs automatically.");
  }, [persistedRunId]);

  const runGenerate = useCallback(() => {
    setJobDescription(briefDraft);
    runDebounced(briefForSubmit, pipelineFromBrainMode(brainMode), draftIntensity);
  }, [briefDraft, briefForSubmit, brainMode, draftIntensity, runDebounced, setJobDescription]);

  const openPatternFromOutput = useCallback(() => {
    const hookBlock = generated.split(/^## Hook\s*$/m)[1]?.split(/^## /m)[0]?.trim() ?? "";
    setPatternTitle("Saved win pattern");
    setPatternBody((hookBlock || generated).slice(0, 4000));
    setPatternOpen(true);
    setActionMsg(null);
  }, [generated]);

  const workspaceHeader = (
    <div className="flex min-h-14 flex-wrap items-center gap-3 px-4 py-2 lg:gap-4 lg:px-6">
      <Link
        href="/dashboard"
        className="hidden shrink-0 items-center gap-2.5 rounded-xl pr-2 lg:flex"
      >
        <span className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-violet-600 text-xs font-bold text-white shadow-md shadow-blue-500/25">
          BF
        </span>
        <span className="font-display text-[15px] font-semibold tracking-[-0.02em]">BidForge</span>
      </Link>
      <div className="flex min-w-0 flex-1 justify-center px-1 lg:px-4">
        <input
          value={titleDraft}
          onChange={(e) => setTitleDraft(e.target.value)}
          onBlur={flushTitle}
          placeholder="Untitled proposal"
          className="w-full max-w-xl truncate border-0 bg-transparent text-center text-[15px] font-semibold text-foreground outline-none ring-0 placeholder:text-muted-foreground focus-visible:underline md:text-base"
          aria-label="Proposal title"
        />
      </div>
      <div className="ml-auto flex shrink-0 flex-wrap items-center justify-end gap-2">
        <WorkspaceModeToggle size="compact" className="hidden xl:flex" />
        <Button
          type="button"
          disabled={!canSubmit}
          onClick={runGenerate}
          className="h-10 gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-4 text-[14px] font-semibold text-white shadow-sm hover:brightness-110 disabled:opacity-50 md:min-h-11 md:px-5"
        >
          {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
          Generate
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-10 min-h-10 rounded-xl px-4 text-[14px] md:min-h-11"
          onClick={onSaveLink}
        >
          Save
        </Button>
        <WorkspaceModeToggle size="compact" className="xl:hidden" />
        <ThemeToggle />
        {isSignedIn ? (
          <UserButton
            appearance={{
              elements: {
                userButtonAvatarBox: "size-9 ring-1 ring-border",
              },
            }}
          />
        ) : (
          <SignInButton mode="modal">
            <Button type="button" variant="outline" className="h-10 rounded-xl px-4">
              Sign in
            </Button>
          </SignInButton>
        )}
      </div>
    </div>
  );

  const inputPanel = (
    <div
      className={cn(
        "flex h-full min-h-0 flex-1 flex-col",
        dragActive && "ring-2 ring-primary/30 ring-offset-2 ring-offset-background",
      )}
      onDragEnter={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragActive(false);
      }}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        setDragActive(false);
        const f = e.dataTransfer.files?.[0];
        if (f) void ingestFile(f);
      }}
    >
      <div className="flex min-h-0 flex-1 flex-col px-5 pb-5 pt-6 md:px-6 md:pb-6 md:pt-7">
        <textarea
          value={briefDraft}
          onChange={(e) => {
            const v = e.target.value;
            setBriefDraft(v);
            debouncedSyncBrief(v);
          }}
          onBlur={() => setJobDescription(briefDraft)}
          spellCheck
          placeholder="Paste the RFP, job post, or buyer notes. Drop a PDF or .txt anywhere in this panel."
          className="min-h-[500px] w-full flex-1 resize-y border-0 bg-transparent px-1 py-1 text-[17px] leading-[1.65] text-foreground outline-none ring-0 placeholder:text-muted-foreground"
        />
        <div className="mt-4 flex flex-col gap-4 border-t border-border/60 pt-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[14px] tabular-nums text-muted-foreground">
              {briefDraft.length.toLocaleString()} / {rfpMaxChars.toLocaleString()} characters
            </p>
            <WorkspaceModeToggle size="compact" className="lg:hidden" />
          </div>
          <div className="flex flex-wrap gap-2">
            <input
              ref={fileRef}
              type="file"
              className="sr-only"
              accept=".txt,.pdf,.docx,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={onFileChange}
            />
            <Button
              type="button"
              variant="outline"
              className="h-11 min-h-11 gap-2 rounded-xl border-dashed px-5 text-[15px]"
              disabled={actionBusy}
              onClick={() => fileRef.current?.click()}
            >
              <Upload className="size-4" aria-hidden />
              Upload PDF / TXT
            </Button>
          </div>
          {errorMsg ? (
            <div className="rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-[14px] text-destructive" role="alert">
              {errorMsg}
            </div>
          ) : null}
          {actionMsg ? (
            <p className="text-[14px] text-muted-foreground" role="status">
              {actionMsg}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );

  const outputPanel = (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      {runDegraded || runWarnings.length > 0 ? (
        <div
          className="shrink-0 border-b border-amber-500/25 bg-amber-500/10 px-5 py-3 text-[14px] text-amber-950 dark:text-amber-50"
          role="status"
        >
          {runDegraded ? (
            <p className="font-medium text-foreground">This run finished in a limited mode—you still have an editable draft.</p>
          ) : null}
          {runWarnings.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {runWarnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <div className="w-full px-5 pb-32 pt-8 md:px-8 md:pb-40 md:pt-12 lg:px-6 lg:pb-40 lg:pt-10">
          {isFreelanceRun ? (
            <div className="mb-10 space-y-4 rounded-2xl border border-violet-500/20 bg-violet-500/[0.06] p-6 dark:bg-violet-500/10">
              {replyLikelihood0_100 != null ? (
                <div>
                  <p className="text-[14px] text-muted-foreground">Reply likelihood (model)</p>
                  <div className="mt-2 h-2 w-full max-w-sm overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-violet-500 to-blue-500"
                      style={{ width: `${Math.min(100, Math.max(0, replyLikelihood0_100))}%` }}
                    />
                  </div>
                  <p className="mt-2 text-[16px] font-semibold tabular-nums">{replyLikelihood0_100}/100</p>
                </div>
              ) : null}
              <label className="text-[15px] font-medium text-foreground" htmlFor="hook-preview">
                Hook
              </label>
              <textarea
                id="hook-preview"
                value={hookDraft}
                onChange={(e) => setHookDraft(e.target.value)}
                rows={5}
                className="w-full resize-y rounded-xl border border-border bg-background px-4 py-3 text-[16px] leading-relaxed outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
          ) : null}
          {!readerMarkdown.trim() && !loading ? (
            <div className="flex min-h-[50vh] flex-col items-center justify-center px-4 text-center">
              <p className="max-w-md text-[17px] leading-relaxed text-muted-foreground">
                Paste a brief to generate your first proposal.
              </p>
            </div>
          ) : null}
          {readerMarkdown.trim() ? (
            <ProposalDocument
              markdown={readerMarkdown}
              sectionAttributions={sectionAttributions}
              memorySummary={memorySummary}
              presentation={isFreelanceRun ? "freelance" : "enterprise"}
              density="reader"
              showSectionActions={false}
            />
          ) : null}
          {loading ? (
            <div
              className={cn(
                "flex items-center gap-3 text-[16px] text-muted-foreground",
                readerMarkdown.trim() ? "py-10" : "min-h-[40vh] flex-col justify-center py-20",
              )}
            >
              <Loader2 className="size-5 animate-spin" aria-hidden />
              Generating…
            </div>
          ) : null}
          {timelineMd.trim() ? (
            <section className="mt-14 border-t border-border/60 pt-12">
              <h2 className="font-display text-2xl font-semibold tracking-tight text-foreground">Timeline</h2>
              <div className="mt-6">
                <ProposalDocument markdown={timelineMd} density="reader" showSectionActions={false} />
              </div>
            </section>
          ) : null}
          {issues.length > 0 ? (
            <section className="mt-14 border-t border-border/60 pt-12">
              <h2 className="font-display text-2xl font-semibold tracking-tight text-amber-900 dark:text-amber-100">
                Issues
              </h2>
              <ul className="mt-6 space-y-3">
                {issues.map((issue, i) => (
                  <li
                    key={i}
                    className="rounded-xl border border-amber-500/25 bg-amber-500/[0.07] px-4 py-3 text-[16px] leading-relaxed text-foreground dark:bg-amber-500/10"
                  >
                    {issue}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );

  const contextPanel = (
    <div className="flex flex-col gap-8">
      <MemoryUsedPanel
        memorySummary={memorySummary}
        memoryGrounded={memoryGrounded}
        hasCompletedRun={memoryGrounded !== null}
        pipelineMode={lastPipelineMode}
      />
      {verifierSuggestions.length ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Verifier next steps
          </p>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-[15px] text-muted-foreground">
            {verifierSuggestions.map((t, i) => (
              <li key={`vs-${i}`}>{t}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {lastCritique?.improvements?.length ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Critique</p>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-[15px] text-muted-foreground">
            {lastCritique.improvements.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {crossProposalDiff &&
      (crossProposalDiff.stronger_hooks?.length ||
        crossProposalDiff.missing_signals?.length ||
        crossProposalDiff.better_cta?.length ||
        crossProposalDiff.structure_optimization?.length) ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Diff vs recent wins</p>
          <div className="mt-3 space-y-4 text-[14px] text-muted-foreground">
            {crossProposalDiff.stronger_hooks?.length ? (
              <div>
                <p className="font-medium text-foreground">Stronger hooks</p>
                <ul className="mt-1 list-disc pl-5">
                  {crossProposalDiff.stronger_hooks.map((t, i) => (
                    <li key={`h-${i}`}>{t}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {crossProposalDiff.missing_signals?.length ? (
              <div>
                <p className="font-medium text-foreground">Missing signals</p>
                <ul className="mt-1 list-disc pl-5">
                  {crossProposalDiff.missing_signals.map((t, i) => (
                    <li key={`s-${i}`}>{t}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
      {memoryGrounded === true && insightsAttributions.length > 0 ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Signals used</p>
          <ul className="mt-3 space-y-3 text-[14px] text-muted-foreground">
            {insightsAttributions.map((a, i) => (
              <li key={`${a.title}-${i}`}>
                <span className="font-medium text-foreground">{a.title}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {isFreelanceRun && lastCritique?.top1_style_rewrite?.trim() ? (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Style rewrite</p>
          <p className="mt-3 whitespace-pre-wrap text-[14px] leading-relaxed text-muted-foreground">
            {lastCritique.top1_style_rewrite.trim()}
          </p>
        </div>
      ) : null}
      {score != null ? (
        <ScorePanel
          score={score}
          issues={issues}
          breakdown={scoreBreakdown ?? emptyBreakdown}
          variant={isFreelanceRun ? "freelance" : "enterprise"}
        />
      ) : null}
      <p className="text-[13px] leading-relaxed text-muted-foreground">Line-by-line diff is coming soon.</p>
    </div>
  );

  const bottomBar = (
    <div className="flex flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between md:px-6">
      <div className="flex flex-wrap items-center justify-center gap-2 md:justify-start">
        <Button
          type="button"
          disabled={!canSubmit}
          onClick={runGenerate}
          className="h-11 min-h-11 gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-5 text-[15px] font-semibold text-white shadow-sm hover:brightness-110 disabled:opacity-50"
        >
          {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
          Generate
        </Button>
        <Button
          type="button"
          variant="secondary"
          className="h-11 min-h-11 gap-2 rounded-xl px-5 text-[15px]"
          disabled={!canSubmit || actionBusy}
          onClick={() => {
            setDraftIntensity("balanced");
            setJobDescription(briefDraft);
            void runNow(briefForSubmit, pipelineFromBrainMode(brainMode), "balanced");
          }}
        >
          <Wand2 className="size-4" aria-hidden />
          Improve
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-11 min-h-11 gap-2 rounded-xl px-5 text-[15px]"
          disabled={actionBusy || !isSignedIn || !canSubmit}
          onClick={() => {
            setDraftIntensity("strong");
            setJobDescription(briefDraft);
            void runNow(briefForSubmit, pipelineFromBrainMode(brainMode), "strong");
          }}
        >
          <ThumbsUp className="size-4" aria-hidden />
          Strong
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-11 min-h-11 gap-2 rounded-xl px-5 text-[15px]"
          disabled={actionBusy || !isSignedIn || !canSubmit}
          onClick={() => {
            setDraftIntensity("weak");
            setJobDescription(briefDraft);
            void runNow(briefForSubmit, pipelineFromBrainMode(brainMode), "weak");
          }}
        >
          <ThumbsDown className="size-4" aria-hidden />
          Weak
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-11 min-h-11 gap-2 rounded-xl px-5 text-[15px]"
          disabled={!isSignedIn || !generated.trim()}
          onClick={openPatternFromOutput}
        >
          <BookmarkPlus className="size-4" aria-hidden />
          Save as pattern
        </Button>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-2 md:justify-end">
        <Button type="button" variant="ghost" className="h-11 rounded-xl px-4 text-[15px]" onClick={onPrintPdf} disabled={!generated.trim()}>
          <Printer className="mr-2 size-4" aria-hidden />
          Print
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="h-11 rounded-xl px-4 text-[15px]"
          disabled={!generated.trim() || actionBusy || !isSignedIn}
          onClick={() => void onDownloadServerPdf()}
        >
          <Download className="mr-2 size-4" aria-hidden />
          PDF
        </Button>
      </div>
    </div>
  );

  return (
    <>
      <WorkspaceWritingLayout
        header={workspaceHeader}
        input={inputPanel}
        output={outputPanel}
        context={contextPanel}
        drawerOpen={drawerOpen}
        onDrawerOpenChange={setDrawerOpen}
        bottomBar={bottomBar}
      />
      {patternOpen ? (
        <div className="fixed inset-0 z-[80] flex items-end justify-center bg-black/50 p-4 sm:items-center">
          <div
            className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-border bg-background p-6 shadow-2xl"
            role="dialog"
            aria-modal
          >
            <div className="flex items-center justify-between gap-3">
              <p className="font-display text-lg font-semibold">Save pattern</p>
              <Button type="button" variant="ghost" size="sm" onClick={() => setPatternOpen(false)}>
                Close
              </Button>
            </div>
            <label className="mt-4 block text-[14px] font-medium text-foreground">
              Title
              <input
                value={patternTitle}
                onChange={(e) => setPatternTitle(e.target.value)}
                className="mt-2 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-[15px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
            <label className="mt-4 block text-[14px] font-medium text-foreground">
              Tags (comma-separated)
              <input
                value={patternTags}
                onChange={(e) => setPatternTags(e.target.value)}
                placeholder="timeline, government, AI/ML"
                className="mt-2 w-full rounded-xl border border-border bg-background px-3 py-2.5 text-[15px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
            <label className="mt-4 block text-[14px] font-medium text-foreground">
              Pattern text
              <textarea
                value={patternBody}
                onChange={(e) => setPatternBody(e.target.value)}
                rows={6}
                className="mt-2 w-full resize-y rounded-xl border border-border bg-background px-3 py-2.5 text-[15px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
            <Button type="button" className="mt-5 h-11 w-full rounded-xl text-[15px]" disabled={actionBusy || !isSignedIn} onClick={() => void submitPattern()}>
              {actionBusy ? "Saving…" : "Save pattern"}
            </Button>
          </div>
        </div>
      ) : null}
    </>
  );
}
