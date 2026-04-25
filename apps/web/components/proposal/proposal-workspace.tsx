"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  BookmarkPlus,
  Download,
  Loader2,
  PanelRight,
  Printer,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Upload,
  Wand2,
} from "lucide-react";
import { UserButton, SignInButton } from "@clerk/nextjs";
import type { MemoryPatternItem, ProposalSavedRunPublic } from "@bidforge/web-sdk";
import { BidForgeApiError, normalizedDocumentToPlain } from "@bidforge/web-sdk";
import type { BrainMode } from "@/lib/store";
import { useProposalStore } from "@/lib/store";
import { WorkspaceWritingLayout } from "@/components/bidforge/workspace-writing-layout";
import { ScorePanel } from "@/components/bidforge/score-panel";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ProposalDocument } from "@/components/proposal/proposal-document";
import { useProposalRun } from "@/lib/api/hooks/use-proposal-run";
import {
  fallbackProposalExportTitle,
  issuesToScoreBreakdown,
  printProposalAsPdf,
  publicRunToMarkdown,
  publicRunToProposalSections,
} from "@/lib/api/proposal-markdown";
import { ThemeToggle } from "@/components/bidforge/theme-toggle";
import { WorkspaceModeToggle } from "@/components/app/workspace-mode-toggle";
import { useDebouncedCallback } from "@/lib/use-debounced-callback";
import { toast } from "sonner";

export type ProposalWorkspaceProps = {
  initialRunId?: string | null;
  /** When "new", the workspace must not auto-hydrate any prior runs. */
  mode?: "default" | "new";
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

export function ProposalWorkspace({ initialRunId = null, mode = "default" }: ProposalWorkspaceProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const effectiveRunId = useMemo(() => {
    const q = searchParams.get("run")?.trim();
    if (q) return q;
    if (mode === "new") return null;
    return (initialRunId ?? "").trim() || null;
  }, [searchParams, initialRunId, mode]);
  const fileRef = useRef<HTMLInputElement>(null);
  const pendingLearningRef = useRef<string | null>(null);
  /** RFP text that last completed run / hydration used — when `briefDraft` diverges, titles must not stay on the old job. */
  const lastCommittedBriefRef = useRef<string | null>(null);
  const prevEffectiveRunIdRef = useRef<string | null>(null);
  /** After explicit "New" (`/proposal` with no `run`), skip auto `?run=` redirect once. */
  const skipLatestRunHydrateOnceRef = useRef(false);
  const latestRunHydratedRef = useRef(false);
  const [briefDraft, setBriefDraft] = useState("");
  /** Mirrors textarea — avoids auto `?run=` hydration overwriting in-progress typing before debounce lands in the store. */
  const briefDraftRef = useRef("");
  const [titleDraft, setTitleDraft] = useState("");
  const [patternOpen, setPatternOpen] = useState(false);
  const [patternBody, setPatternBody] = useState("");
  const [patternTitle, setPatternTitle] = useState("Win pattern");
  const [patternTags, setPatternTags] = useState("");
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [rightTab, setRightTab] = useState<"proposal" | "memory" | "review">("proposal");
  const [memoryPatterns, setMemoryPatterns] = useState<MemoryPatternItem[] | null>(null);

  const generated = useProposalStore((s) => s.generated);
  const score = useProposalStore((s) => s.score);
  const issues = useProposalStore((s) => s.issues);
  const scoreBreakdown = useProposalStore((s) => s.scoreBreakdown);
  const brainMode = useProposalStore((s) => s.brainMode);
  const proposalTitle = useProposalStore((s) => s.proposalTitle);
  const persistedRunId = useProposalStore((s) => s.persistedRunId);
  const proposalSections = useProposalStore((s) => s.proposalSections);
  const memoryUsed = useProposalStore((s) => s.memoryUsed);
  const setJobDescription = useProposalStore((s) => s.setJobDescription);
  const setBrainMode = useProposalStore((s) => s.setBrainMode);
  const setProposalTitle = useProposalStore((s) => s.setProposalTitle);
  const setResult = useProposalStore((s) => s.setResult);
  const resetDraftStore = useProposalStore((s) => s.reset);

  const { state, runDebounced, runNow, reset: resetRunState, rfpMaxChars, isAuthReady, isSignedIn, apiClient } =
    useProposalRun();

  const postPatternIfPersisted = useCallback(
    async (pattern: "strong" | "weak" | "saved") => {
      const rid = persistedRunId?.trim();
      if (!rid) {
        toast.message("Run not saved yet", {
          description: "Finish a generation first so Strong / Weak / Improve can tag this draft.",
        });
        return;
      }
      const label = pattern === "strong" ? "Strong" : pattern === "weak" ? "Weak" : "Saved";
      try {
        await apiClient.postProposalPattern({ proposalId: rid, pattern });
        toast.success(`${label} pattern saved`, {
          id: `pattern-${rid}-${pattern}`,
          description: "Stored for this proposal run.",
        });
      } catch {
        toast.error("Could not save pattern", {
          id: `pattern-err-${rid}-${pattern}`,
          description: "Generation will still continue. Check Supabase if this persists.",
        });
      }
    },
    [apiClient, persistedRunId],
  );

  const [draftIntensity, setDraftIntensity] = useState<"balanced" | "strong" | "weak">("balanced");
  const settingsHydrated = useRef(false);

  const debouncedSyncBrief = useDebouncedCallback((value: string) => {
    setJobDescription(value);
  }, 450);

  const debouncedRetitleOnBriefDrift = useDebouncedCallback(() => {
    const cur = briefDraft.trim();
    const last = lastCommittedBriefRef.current;
    if (last === null || cur === last) return;
    setProposalTitle(null);
    setTitleDraft(fallbackProposalExportTitle(briefDraft, generated, null));
  }, 400);

  /** Hard reset on explicit New Proposal route. */
  useEffect(() => {
    if (mode !== "new") return;
    resetRunState();
    resetDraftStore();
    setBriefDraft("");
    setTitleDraft("");
    setPatternOpen(false);
    setActionMsg(null);
    setRightTab("proposal");
    lastCommittedBriefRef.current = null;
    pendingLearningRef.current = null;
    latestRunHydratedRef.current = true; // never auto-hydrate latest while in new mode
    skipLatestRunHydrateOnceRef.current = true;
  }, [mode, resetDraftStore, resetRunState]);

  useEffect(() => {
    briefDraftRef.current = briefDraft;
  }, [briefDraft]);

  useEffect(() => {
    debouncedRetitleOnBriefDrift();
  }, [briefDraft, generated, debouncedRetitleOnBriefDrift]);

  /** Leaving `?run=` for a blank workspace — drop prior run from client so "new proposal" is not a stale cache. */
  useEffect(() => {
    const cur = effectiveRunId;
    const prev = prevEffectiveRunIdRef.current;
    prevEffectiveRunIdRef.current = cur;
    if (prev && !cur) {
      resetRunState();
      resetDraftStore();
      setBriefDraft("");
      setTitleDraft("");
      setPatternOpen(false);
      setActionMsg(null);
      setRightTab("proposal");
      lastCommittedBriefRef.current = null;
      pendingLearningRef.current = null;
      latestRunHydratedRef.current = false;
      skipLatestRunHydrateOnceRef.current = true;
    }
  }, [effectiveRunId, resetDraftStore, resetRunState]);

  useEffect(() => {
    const t = (proposalTitle ?? "").trim();
    if (t) setTitleDraft(t);
  }, [proposalTitle]);

  useEffect(() => {
    if (!isAuthReady || !isSignedIn || settingsHydrated.current) return;
    settingsHydrated.current = true;
    let cancelled = false;
    void (async () => {
      try {
        const s = await apiClient.getSettingsForHydration();
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
    if (!isAuthReady || !isSignedIn) return;
    if (mode === "new") return;
    if (effectiveRunId) return;
    if (latestRunHydratedRef.current) return;
    if (skipLatestRunHydrateOnceRef.current) {
      skipLatestRunHydrateOnceRef.current = false;
      latestRunHydratedRef.current = true;
      return;
    }
    // Do not append `?run=` while the user is already typing — debounced store sync can lag behind the textarea.
    if (briefDraftRef.current.trim().length > 0) {
      latestRunHydratedRef.current = true;
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const runs = await apiClient.listProposalsForHydration();
        if (cancelled) return;
        latestRunHydratedRef.current = true;
        if (!runs.length) return;
        const top = runs[0]?.id?.trim();
        if (!top || typeof window === "undefined") return;
        const url = new URL(window.location.href);
        if (url.searchParams.get("run") === top) return;
        url.searchParams.set("run", top);
        router.replace(`${url.pathname}${url.search}${url.hash}`, { scroll: false });
      } catch {
        if (!cancelled) latestRunHydratedRef.current = false;
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiClient, effectiveRunId, isAuthReady, isSignedIn, router, mode]);

  useEffect(() => {
    const rid = effectiveRunId;
    if (!rid || !isSignedIn || !isAuthReady) return;
    if (rid === persistedRunId) return;
    let cancelled = false;
    void (async () => {
      setActionMsg(null);
      try {
        const d = await apiClient.getProposalRun(rid);
        if (cancelled) return;
        const full = d as ProposalSavedRunPublic;
        const { rfp_input, pipeline_mode, ...run } = full;
        const md = publicRunToMarkdown(run);
        const sections = publicRunToProposalSections(run);
        const rfp = typeof rfp_input === "string" ? rfp_input : "";
        if (rfp.trim()) {
          setJobDescription(rfp);
          setBriefDraft(rfp);
          lastCommittedBriefRef.current = rfp.trim();
        } else {
          lastCommittedBriefRef.current = briefDraftRef.current.trim() || null;
        }
        setBrainMode(pipeline_mode === "freelance" ? "freelance" : "enterprise");
        setTitleDraft((full.title || "").trim());
        setProposalTitle((full.title || "").trim() ? full.title.trim() : null);
        const breakdown = issuesToScoreBreakdown(run.issues ?? []);
        setResult({
          run,
          generatedMarkdown: md,
          proposalSections: sections,
          scoreBreakdown: breakdown,
          traceId: run.proposal_id,
        });
        setRightTab("proposal");
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
  }, [
    effectiveRunId,
    isSignedIn,
    isAuthReady,
    apiClient,
    setJobDescription,
    setBrainMode,
    setProposalTitle,
    setResult,
    persistedRunId,
  ]);

  useEffect(() => {
    if (state.status !== "success") return;
    const run = state.data;
    const md = publicRunToMarkdown(run);
    const sections = publicRunToProposalSections(run);
    const breakdown = issuesToScoreBreakdown(run.issues);
    setResult({
      run,
      generatedMarkdown: md,
      proposalSections: sections,
      scoreBreakdown: breakdown,
      traceId: run.proposal_id,
    });
    setTitleDraft((run.title || "").trim());
    setProposalTitle((run.title || "").trim() ? run.title.trim() : null);
    setPatternOpen(false);
    setActionMsg(null);
    setRightTab("proposal");
    const pid = run.proposal_id?.trim();
    if (pid) {
      toast.success("Proposal saved", {
        id: `proposal-saved-${pid}`,
        description: "Your draft is in saved runs. Use Save to copy the link.",
      });
    }
    if (pid && typeof window !== "undefined") {
      const url = new URL(window.location.href);
      if (url.searchParams.get("run") !== pid) {
        url.searchParams.set("run", pid);
        router.replace(`${url.pathname}${url.search}${url.hash}`, { scroll: false });
      }
    }
    lastCommittedBriefRef.current = briefDraftRef.current.trim() || null;
    pendingLearningRef.current = null;
  }, [state, setResult, setProposalTitle, router]);

  useEffect(() => {
    if (rightTab !== "memory" || !isSignedIn) return;
    let cancelled = false;
    void (async () => {
      try {
        const rows = await apiClient.listMemoryPatterns();
        if (!cancelled) setMemoryPatterns(rows);
      } catch {
        if (!cancelled) setMemoryPatterns([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [rightTab, isSignedIn, apiClient]);

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
      toast.message("Add pattern text", { description: "Paste or type the pattern before saving." });
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
        pattern_kind: brainMode === "freelance" ? "freelance_win_pattern" : "win_pattern",
      });
      pendingLearningRef.current = body.slice(0, 4000);
      toast.success("Pattern saved to memory", {
        description: "Your next generation can use this as a cue.",
      });
      setMemoryPatterns(null);
      setActionMsg(null);
      setPatternOpen(false);
    } catch (e) {
      const msg =
        e instanceof BidForgeApiError ? e.message : (e as Error).message || "Request failed";
      toast.error("Could not save pattern", { description: msg });
      setActionMsg(msg);
    } finally {
      setActionBusy(false);
    }
  }, [apiClient, brainMode, patternBody, patternTags, patternTitle, setMemoryPatterns]);

  const briefDrifted =
    lastCommittedBriefRef.current !== null && briefDraft.trim() !== lastCommittedBriefRef.current;

  const onPrintPdf = useCallback(() => {
    const apiTitleForFallback = briefDrifted ? null : proposalTitle;
    const docTitle =
      (titleDraft || "").trim() ||
      (proposalTitle || "").trim() ||
      fallbackProposalExportTitle(briefDraft, generated, apiTitleForFallback);
    printProposalAsPdf(generated, undefined, docTitle);
  }, [briefDrifted, briefDraft, generated, proposalTitle, titleDraft]);

  const onDownloadServerPdf = useCallback(async () => {
    if (!proposalSections) {
      setActionMsg("Generate a proposal before exporting PDF.");
      return;
    }
    setActionBusy(true);
    setActionMsg(null);
    try {
      const apiTitleForFallback = briefDrifted ? null : proposalTitle;
      const exportTitle =
        (titleDraft || "").trim() ||
        (proposalTitle || "").trim() ||
        fallbackProposalExportTitle(briefDraft, generated, apiTitleForFallback);
      const s = proposalSections;
      const blob = await apiClient.exportProposalPdf({
        title: exportTitle,
        sections: {
          opening: s.opening ?? s.hook ?? s.executive_summary,
          hook: s.opening ?? s.hook ?? s.executive_summary,
          executive_summary: s.executive_summary,
          understanding: s.understanding ?? s.what_ill_deliver ?? "",
          solution: s.solution ?? "",
          what_ill_deliver: s.understanding ?? s.what_ill_deliver ?? "",
          execution_plan: s.execution_plan ?? s.technical_approach,
          technical_approach: s.technical_approach,
          timeline: s.timeline ?? s.timeline_block ?? "",
          timeline_block: s.timeline ?? s.timeline_block ?? "",
          deliverables: s.deliverables ?? s.deliverables_block ?? "",
          deliverables_block: s.deliverables ?? s.deliverables_block ?? "",
          delivery_plan: s.delivery_plan,
          experience: s.experience ?? s.relevant_experience ?? "",
          relevant_experience: s.experience ?? s.relevant_experience ?? "",
          risks: s.risks ?? s.risk_reduction ?? "",
          risk_reduction: s.risks ?? s.risk_reduction ?? "",
          risk_management: s.risk_management,
          next_step: s.next_step ?? s.call_to_action ?? "",
          call_to_action: s.next_step ?? s.call_to_action ?? "",
        },
        timeline: [],
        pipeline_mode: brainMode === "freelance" ? "freelance" : "enterprise",
        score: score ?? undefined,
        issues: issues.slice(0, 12),
        memory_insight_bullets: undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "proposal-export.pdf";
      a.click();
      URL.revokeObjectURL(url);
      toast.success("PDF downloaded");
      setActionMsg(null);
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
    proposalSections,
    score,
    brainMode,
    briefDrifted,
    briefDraft,
    generated,
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
  const briefTextareaRows = useMemo(
    () => Math.min(42, Math.max(14, briefDraft.split(/\r?\n/).length + 6)),
    [briefDraft],
  );
  const canSubmit =
    isAuthReady &&
    isSignedIn &&
    briefForSubmit.length > 0 &&
    !loading &&
    briefForSubmit.length <= rfpMaxChars;

  const isFreelanceRun = brainMode === "freelance";

  const tabBtn = (id: "proposal" | "memory" | "review", label: string) => (
    <button
      key={id}
      type="button"
      onClick={() => setRightTab(id)}
      className={cn(
        "rounded-t-lg px-4 py-2.5 text-[14px] font-medium transition-colors",
        rightTab === id
          ? "border border-b-0 border-border bg-background text-foreground"
          : "border border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
    </button>
  );

  const flushTitle = useCallback(() => {
    const t = titleDraft.trim();
    setProposalTitle(t.length ? t : null);
  }, [titleDraft, setProposalTitle]);

  const onSaveLink = useCallback(() => {
    if (persistedRunId) {
      const url = `${window.location.origin}/proposal?run=${encodeURIComponent(persistedRunId)}`;
      void navigator.clipboard.writeText(url).then(
        () => {
          toast.success("Link copied", { description: "Share this URL to reopen this saved run." });
          setActionMsg(null);
        },
        () => {
          toast.error("Could not copy link");
          setActionMsg("Could not copy link.");
        },
      );
      return;
    }
    if (generated.trim()) {
      setActionMsg(
        "This draft has no saved run id yet—copy or export it. If this keeps happening, the API cannot write to Supabase (check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY).",
      );
      return;
    }
    setActionMsg("Generate a proposal first—it is added to your saved runs automatically.");
  }, [generated, persistedRunId]);

  const runGenerate = useCallback(() => {
    setJobDescription(briefDraft);
    runDebounced(
      briefForSubmit,
      pipelineFromBrainMode(brainMode),
      draftIntensity,
      () => {
        const learn = pendingLearningRef.current?.trim();
        if (learn) pendingLearningRef.current = null;
        return {
          continuationRunId: persistedRunId ?? undefined,
          learningSnippet: learn || undefined,
        };
      },
    );
  }, [briefDraft, briefForSubmit, brainMode, draftIntensity, persistedRunId, runDebounced, setJobDescription]);

  const openPatternFromOutput = useCallback(() => {
    const hookBlock = generated.split(/^## Hook\s*$/m)[1]?.split(/^## /m)[0]?.trim() ?? "";
    setPatternTitle("Saved win pattern");
    setPatternBody((hookBlock || generated).slice(0, 4000));
    setPatternOpen(true);
    setActionMsg(null);
  }, [generated]);

  const workspaceHeader = (
    <div className="flex min-h-14 flex-wrap items-center gap-3 px-4 py-2 lg:gap-4 lg:px-6">
      <div className="hidden shrink-0 items-center gap-3 lg:flex">
        <Link href="/dashboard" className="flex items-center gap-2.5 rounded-xl pr-1">
          <span className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-violet-600 text-xs font-bold text-white shadow-md shadow-blue-500/25">
            BF
          </span>
          <span className="font-display text-[15px] font-semibold tracking-[-0.02em]">BidForge</span>
        </Link>
        <Link
          href="/proposal/new"
          className="text-[13px] font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          New
        </Link>
      </div>
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
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {/* One scroll surface for brief + helpers — avoid nested scroll vs the textarea */}
        <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-y-contain scroll-smooth px-6 pb-4 pt-8 md:px-8 md:pb-6 md:pt-10">
          <label htmlFor="proposal-brief" className="sr-only">
            RFP or job brief
          </label>
          <textarea
            id="proposal-brief"
            value={briefDraft}
            onChange={(e) => {
              const v = e.target.value;
              setBriefDraft(v);
              debouncedSyncBrief(v);
            }}
            onBlur={() => setJobDescription(briefDraft)}
            spellCheck
            rows={briefTextareaRows}
            placeholder=""
            className={cn(
              "box-border w-full max-w-none resize-none border-0 bg-transparent py-2 text-lg leading-[1.7] text-foreground outline-none ring-0 placeholder:text-muted-foreground md:text-[18px] md:leading-[1.75]",
              "min-h-[max(400px,min(42dvh,520px))] [field-sizing:content]",
            )}
          />
          <div className="mt-8 flex flex-col gap-5 border-t border-border/60 pt-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm tabular-nums text-muted-foreground md:text-[15px]">
                {briefDraft.length.toLocaleString()} / {rfpMaxChars.toLocaleString()} characters
              </p>
              <WorkspaceModeToggle size="compact" className="md:hidden" />
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
                Upload PDF / Word / TXT
              </Button>
            </div>
            {errorMsg ? (
              <div className="rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-[14px] text-destructive" role="alert">
                {errorMsg}
              </div>
            ) : null}
            {actionMsg ? (
              <p className="text-[14px] text-muted-foreground md:text-[15px]" role="status">
                {actionMsg}
              </p>
            ) : null}
          </div>
        </div>
        <div className="shrink-0 border-t border-border bg-background/95 px-6 py-4 backdrop-blur-md supports-[backdrop-filter]:bg-background/90 md:px-8">
          <Button
            type="button"
            disabled={!canSubmit}
            onClick={runGenerate}
            className="h-12 w-full gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 text-[15px] font-semibold text-white shadow-sm hover:brightness-110 disabled:opacity-50 md:h-12 md:text-[16px]"
          >
            {loading ? <Loader2 className="size-5 animate-spin" aria-hidden /> : <Sparkles className="size-5" aria-hidden />}
            Generate
          </Button>
        </div>
      </div>
    </div>
  );

  const outputPanel = (
    <div className="relative flex h-full min-h-0 flex-1 flex-col">
      <div className="absolute right-3 top-3 z-20 md:right-4 md:top-4">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-10 gap-2 rounded-xl border-border/80 bg-background/95 px-4 text-[14px] shadow-sm backdrop-blur"
          onClick={() => setDrawerOpen(true)}
        >
          <PanelRight className="size-4" aria-hidden />
          Context
        </Button>
      </div>
      <div className="shrink-0 border-b border-border bg-muted/10 px-4 pt-2 md:px-6">
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Proposal workspace">
          {tabBtn("proposal", "Proposal")}
          {tabBtn("memory", "Memory")}
          {tabBtn("review", "Review")}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-y-contain scroll-smooth">
        <div className="mx-auto w-full max-w-[900px] px-5 pb-32 pt-8 md:px-8 md:pb-36 md:pt-10">
          {rightTab === "proposal" ? (
            <>
              {generated.trim() ? (
                <ProposalDocument
                  markdown={generated}
                  sectionAttributions={null}
                  memorySummary={null}
                  presentation={isFreelanceRun ? "freelance" : "enterprise"}
                  density="reader"
                  showSectionActions={false}
                />
              ) : null}
              {loading ? (
                <div
                  className={cn(
                    "flex gap-3 text-[15px] leading-relaxed text-muted-foreground md:text-[16px]",
                    generated.trim() ? "items-start py-10" : "min-h-[40vh] flex-col items-center justify-center py-20 text-center",
                  )}
                >
                  <Loader2 className="size-5 shrink-0 animate-spin" aria-hidden />
                  <p className={cn(generated.trim() ? "min-w-0 pt-0.5" : "max-w-sm")}>
                    Running the proposal graph (route → brief intel → solution → write → verify). The brief stays in
                    the left column.
                  </p>
                </div>
              ) : null}
            </>
          ) : null}
          {rightTab === "memory" ? (
            <div className="space-y-4">
              <p className="text-[14px] leading-relaxed text-muted-foreground">
                Saved win hooks and patterns (no embeddings or raw retrieval logs).
              </p>
              {memoryPatterns === null ? (
                <p className="text-[14px] text-muted-foreground">Loading…</p>
              ) : memoryPatterns.length === 0 ? (
                <p className="text-[14px] text-muted-foreground">
                  No indexed patterns yet — save a strong proposal to build this library.
                </p>
              ) : (
                <ul className="space-y-4">
                  {memoryPatterns.map((p, i) => (
                    <li
                      key={`${p.label.slice(0, 24)}-${i}`}
                      className="rounded-xl border border-border/70 bg-background/80 px-4 py-3 text-[15px] leading-snug text-foreground/90"
                    >
                      <p className="font-medium text-foreground">{p.outcome}</p>
                      <p className="mt-1 text-[14px] text-muted-foreground">{p.label}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}
          {rightTab === "review" ? (
            <div className="max-w-lg">
              <ScorePanel
                variant="minimal"
                score={score}
                issues={issues}
                breakdown={scoreBreakdown ?? emptyBreakdown}
              />
              {memoryUsed === true ? (
                <p className="mt-4 text-[13px] text-muted-foreground">Indexed memory influenced this generation.</p>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );

  const contextPanel = (
    <div className="flex flex-col gap-6 text-[14px] leading-relaxed text-muted-foreground">
      <p>
        Use <span className="font-medium text-foreground">Proposal / Memory / Score</span> tabs on the right. Patterns
        and PDF export are in the bar below.
      </p>
    </div>
  );

  const bottomBar = (
    <div className="flex flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between md:px-6">
      <div className="flex flex-wrap items-center justify-center gap-2 md:justify-start">
        <Button
          type="button"
          disabled={!canSubmit}
          onClick={runGenerate}
          className="h-11 min-h-11 gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-5 text-[15px] font-semibold text-white shadow-sm hover:brightness-110 disabled:opacity-50 md:hidden"
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
            void (async () => {
              setDraftIntensity("balanced");
              setJobDescription(briefDraft);
              await postPatternIfPersisted("saved");
              void runNow(
                briefForSubmit,
                pipelineFromBrainMode(brainMode),
                "balanced",
                {
                  continuationRunId: persistedRunId ?? undefined,
                  learningSnippet: pendingLearningRef.current?.trim() || undefined,
                },
                { skipCooldown: true },
              );
            })();
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
            void (async () => {
              setDraftIntensity("strong");
              setJobDescription(briefDraft);
              await postPatternIfPersisted("strong");
              void runNow(
                briefForSubmit,
                pipelineFromBrainMode(brainMode),
                "strong",
                {
                  continuationRunId: persistedRunId ?? undefined,
                  learningSnippet: pendingLearningRef.current?.trim() || undefined,
                },
                { skipCooldown: true },
              );
            })();
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
            void (async () => {
              setDraftIntensity("weak");
              setJobDescription(briefDraft);
              await postPatternIfPersisted("weak");
              void runNow(
                briefForSubmit,
                pipelineFromBrainMode(brainMode),
                "weak",
                {
                  continuationRunId: persistedRunId ?? undefined,
                  learningSnippet: pendingLearningRef.current?.trim() || undefined,
                },
                { skipCooldown: true },
              );
            })();
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
