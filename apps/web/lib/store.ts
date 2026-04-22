import { create } from "zustand";
import type {
  CrossProposalDiffPayload,
  MemorySummary,
  ProposalSections,
  SectionAttribution,
  TimelinePhase,
} from "@bidforge/web-sdk";
import type { ScoreBreakdown } from "@/components/bidforge/score-panel";

export type BrainMode = "auto" | "enterprise" | "freelance";

type ProposalDraft = {
  jobDescription: string;
  brainMode: BrainMode;
  generated: string;
  score: number | null;
  issues: string[];
  suggestions: string[];
  scoreBreakdown: ScoreBreakdown | null;
  traceId: string | null;
  memoryGrounded: boolean | null;
  groundingWarning: string | null;
  memorySummary: MemorySummary | null;
  sectionAttributions: SectionAttribution[] | null;
  timeline: TimelinePhase[];
  proposalSections: ProposalSections | null;
  lastPipelineMode: "enterprise" | "freelance" | null;
  replyLikelihood0_100: number | null;
  lastCritique: {
    improvements: string[];
    reply_probability_delta?: string;
    top1_style_rewrite?: string;
  } | null;
  lastHook: string | null;
  proposalTitle: string | null;
  persistedRunId: string | null;
  crossProposalDiff: CrossProposalDiffPayload | null;
};

type ProposalState = ProposalDraft & {
  setJobDescription: (value: string) => void;
  setBrainMode: (value: BrainMode) => void;
  setProposalTitle: (value: string | null) => void;
  setResult: (payload: {
    generated: string;
    score: number | null;
    issues: string[];
    suggestions: string[];
    scoreBreakdown: ScoreBreakdown;
    traceId?: string | null;
    memoryGrounded?: boolean | null;
    groundingWarning?: string | null;
    memorySummary?: MemorySummary | null;
    sectionAttributions?: SectionAttribution[] | null;
    timeline?: TimelinePhase[];
    proposalSections?: ProposalSections | null;
    lastPipelineMode?: "enterprise" | "freelance" | null;
    replyLikelihood0_100?: number | null;
    lastCritique?: {
      improvements: string[];
      reply_probability_delta?: string;
      top1_style_rewrite?: string;
    } | null;
    lastHook?: string | null;
    proposalTitle?: string | null;
    persistedRunId?: string | null;
    crossProposalDiff?: CrossProposalDiffPayload | null;
  }) => void;
  reset: () => void;
};

const initial: ProposalDraft = {
  jobDescription: "",
  brainMode: "enterprise",
  generated: "",
  score: null,
  issues: [],
  suggestions: [],
  scoreBreakdown: null,
  traceId: null,
  memoryGrounded: null,
  groundingWarning: null,
  memorySummary: null,
  sectionAttributions: null,
  timeline: [],
  proposalSections: null,
  lastPipelineMode: null,
  replyLikelihood0_100: null,
  lastCritique: null,
  lastHook: null,
  proposalTitle: null,
  persistedRunId: null,
  crossProposalDiff: null,
};

export const useProposalStore = create<ProposalState>((set) => ({
  ...initial,
  setJobDescription: (jobDescription) => set({ jobDescription }),
  setBrainMode: (brainMode) => set({ brainMode }),
  setProposalTitle: (proposalTitle) => set({ proposalTitle }),
  setResult: ({
    generated,
    score,
    issues,
    suggestions,
    scoreBreakdown,
    traceId,
    memoryGrounded,
    groundingWarning,
    memorySummary,
    sectionAttributions,
    timeline,
    proposalSections,
    lastPipelineMode,
    replyLikelihood0_100,
    lastCritique,
    lastHook,
    proposalTitle,
    persistedRunId,
    crossProposalDiff,
  }) =>
    set({
      generated,
      score,
      issues,
      suggestions,
      scoreBreakdown,
      traceId: traceId ?? null,
      memoryGrounded: memoryGrounded ?? null,
      groundingWarning: groundingWarning ?? null,
      memorySummary: memorySummary ?? null,
      sectionAttributions: sectionAttributions ?? null,
      timeline: timeline ?? [],
      proposalSections: proposalSections ?? null,
      lastPipelineMode: lastPipelineMode ?? null,
      replyLikelihood0_100: replyLikelihood0_100 ?? null,
      lastCritique: lastCritique ?? null,
      lastHook: lastHook ?? null,
      proposalTitle: proposalTitle ?? null,
      persistedRunId: persistedRunId ?? null,
      crossProposalDiff: crossProposalDiff ?? null,
    }),
  reset: () => set(initial),
}));
