/**
 * Stable API types — must match FastAPI OpenAPI (`api/app`).
 */

export type ApiErrorBody = {
  code: string;
  message: string;
  failed_step?: string | null;
  trace_id?: string | null;
  details?: Record<string, unknown> | null;
};

export type ApiErrorEnvelope = {
  error: ApiErrorBody;
};

export type ProposalSections = {
  executive_summary: string;
  technical_approach: string;
  delivery_plan: string;
  risk_management: string;
};

export type MemorySummary = {
  similar_proposals: Array<{
    id?: string | null;
    title?: string | null;
    outcome?: string | null;
  }>;
  win_patterns: Array<{
    id?: string | null;
    label?: string | null;
    outcome?: string | null;
  }>;
  methodology_blocks: Array<{
    id?: string | null;
    title?: string | null;
  }>;
  freelance_win_patterns?: Array<{
    id?: string | null;
    label?: string | null;
    outcome?: string | null;
  }>;
  pipeline_mode?: string | null;
};

export type SectionAttribution = {
  title: string;
  covers_requirements: string[];
  based_on_memory: string[];
};

export type ProposalPayload = {
  sections: ProposalSections;
  format_notes: string[];
  strategy: Record<string, unknown>;
  memory_summary?: MemorySummary;
  memory_grounded?: boolean;
  grounding_warning?: string | null;
  section_attributions?: SectionAttribution[];
  pipeline_mode?: "enterprise" | "freelance";
  freelance?: {
    hook?: string;
    understanding_need?: string;
    approach?: string;
    relevant_experience?: string;
    call_to_action?: string;
    /** Legacy keys — still populated for PDF/export compatibility */
    opening?: string;
    body?: string;
    proof?: string;
    closing?: string;
  };
  hook?: {
    hook: string;
    trust_signal: string;
    relevance_match: string;
    alternative_hooks?: string[];
  };
};

export type TimelinePhase = {
  phase: string;
  duration: string;
};

export type ProposalRunInsights = {
  warnings?: string[];
  missing_context?: boolean;
  rag_fallback_mode?: boolean;
  degraded?: boolean;
};

export type CrossProposalDiffPayload = {
  stronger_hooks?: string[];
  missing_signals?: string[];
  better_cta?: string[];
  structure_optimization?: string[];
};

export type NormalizedSection = {
  name: string;
  content: string;
};

export type NormalizedDocumentMetadata = {
  client?: string;
  deadline?: string;
  budget?: string;
  job_type_hint?: string;
};

export type NormalizedDocumentOutput = {
  title: string;
  sections: NormalizedSection[];
  metadata: NormalizedDocumentMetadata;
};

export type WorkspaceRagConfig = {
  enabled?: boolean;
  enterprise_case_studies?: boolean;
  freelance_win_memory?: boolean;
  proposal_mode?: "auto" | "enterprise" | "freelance";
};

export type WorkspaceSettingsResponse = {
  user_id: string;
  company_profile: Record<string, unknown>;
  tone: string;
  writing_style: string;
  rag_config: WorkspaceRagConfig;
  proposal_mode: "auto" | "enterprise" | "freelance";
  updated_at: string | null;
};

export type WorkspaceSettingsUpdate = {
  company_profile?: Record<string, unknown>;
  tone?: string;
  writing_style?: string;
  rag_config?: WorkspaceRagConfig;
  proposal_mode?: "auto" | "enterprise" | "freelance";
};

/** Optional per-run overlay merged server-side before SettingsInjector. */
export type ProposalWorkspaceInput = {
  tone?: string;
  writing_style?: string;
  proposal_mode?: "auto" | "enterprise" | "freelance";
  rag?: {
    enabled?: boolean;
    enterprise_case_studies?: boolean;
    freelance_win_memory?: boolean;
  };
  company_profile?: Record<string, unknown>;
};

export type WorkspaceStateEcho = Record<string, unknown>;

export type ProposalRunResponse = {
  proposal: ProposalPayload;
  score: number;
  issues: string[];
  /** Verifier remediation hints; separate from proposal body. */
  suggestions?: string[];
  /** @deprecated Prefer `run_id` — same value, kept for older clients. */
  trace_id: string;
  run_id: string;
  memory_grounded: boolean;
  /** Indexed win / case memory used for grounding; `empty` when none. */
  memory_status?: "empty" | "grounded";
  grounding_warning?: string | null;
  timeline: TimelinePhase[];
  memory_used: MemorySummary;
  status: "success" | "degraded";
  insights: ProposalRunInsights;
  pipeline_metadata: {
    pipeline_timeout_s?: number;
    per_agent_timeout_s?: number;
    rfp_max_chars?: number;
  };
  pipeline_mode: "enterprise" | "freelance";
  input_classification?: Record<string, unknown> | null;
  job_understanding?: Record<string, unknown> | null;
  hook?: {
    hook: string;
    trust_signal: string;
    relevance_match: string;
    alternative_hooks?: string[];
  } | null;
  critique?: {
    improvements: string[];
    reply_probability_delta?: string;
    enterprise_gap_summary?: string;
    /** Freelance: optional full bid in top-1% reply style */
    top1_style_rewrite?: string;
  } | null;
  verifier_metrics?: Record<string, unknown> | null;
  reply_likelihood_0_100?: number | null;
  /** Job-specific title from the API (never a product placeholder). */
  title: string;
  cross_proposal_diff?: CrossProposalDiffPayload | null;
  /** DB row id in `proposal_runs` when the server persisted this run. */
  persisted_run_id?: string | null;
  /** Canonical workspace echo (rfp slice, settings, memory scratch, trace). */
  workspace_state?: WorkspaceStateEcho;
};

export type ProposalRunSummary = {
  id: string;
  title: string;
  score: number;
  trace_id: string;
  pipeline_mode: string;
  created_at: string;
};

export type ProposalRunDetail = ProposalRunSummary & {
  rfp_input: string;
  proposal_output: Record<string, unknown>;
  issues: unknown[];
};

export type ApiVersionResponse = {
  version: string;
  pipeline: string;
  rfp_max_chars: number;
  pipeline_timeout_s: number;
  per_agent_timeout_s: number;
};

export class BidForgeApiError extends Error {
  readonly status: number;
  readonly body: ApiErrorEnvelope;

  constructor(status: number, body: ApiErrorEnvelope) {
    super(body.error.message);
    this.name = "BidForgeApiError";
    this.status = status;
    this.body = body;
  }

  get traceId(): string | undefined {
    return this.body.error.trace_id ?? undefined;
  }

  get code(): string {
    return this.body.error.code;
  }
}
