import { create } from "zustand";
import type { ProposalPublicRunResponse, ProposalSections } from "@bidforge/web-sdk";
import type { ScoreBreakdown } from "@/components/bidforge/score-panel";

export type BrainMode = "auto" | "enterprise" | "freelance";

type ProposalDraft = {
  jobDescription: string;
  brainMode: BrainMode;
  /** Markdown built only from the public run contract (Proposal tab). */
  generated: string;
  score: number | null;
  issues: string[];
  scoreBreakdown: ScoreBreakdown | null;
  traceId: string | null;
  memoryUsed: boolean | null;
  proposalTitle: string | null;
  persistedRunId: string | null;
  executiveSummary: string;
  proposalSections: ProposalSections | null;
};

type ProposalState = ProposalDraft & {
  setJobDescription: (value: string) => void;
  setBrainMode: (value: BrainMode) => void;
  setProposalTitle: (value: string | null) => void;
  setResult: (payload: {
    run: ProposalPublicRunResponse;
    generatedMarkdown: string;
    proposalSections: ProposalSections | null;
    scoreBreakdown: ScoreBreakdown;
    traceId?: string | null;
  }) => void;
  reset: () => void;
};

const initial: ProposalDraft = {
  jobDescription: "",
  brainMode: "enterprise",
  generated: "",
  score: null,
  issues: [],
  scoreBreakdown: null,
  traceId: null,
  memoryUsed: null,
  proposalTitle: null,
  persistedRunId: null,
  executiveSummary: "",
  proposalSections: null,
};

export const useProposalStore = create<ProposalState>((set) => ({
  ...initial,
  setJobDescription: (jobDescription) => set({ jobDescription }),
  setBrainMode: (brainMode) => set({ brainMode }),
  setProposalTitle: (proposalTitle) => set({ proposalTitle }),
  setResult: ({
    run,
    generatedMarkdown,
    proposalSections,
    scoreBreakdown,
    traceId,
  }) =>
    set({
      generated: generatedMarkdown,
      score: run.score,
      issues: run.issues,
      scoreBreakdown,
      traceId: traceId ?? run.proposal_id,
      memoryUsed: run.memory_used,
      proposalTitle: run.title?.trim() ? run.title.trim() : null,
      persistedRunId: run.proposal_id?.trim() ? run.proposal_id.trim() : null,
      executiveSummary: run.executive_summary ?? "",
      proposalSections,
    }),
  reset: () => set(initial),
}));
