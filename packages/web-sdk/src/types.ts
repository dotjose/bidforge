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
  opening?: string;
  understanding?: string;
  solution?: string;
  execution_plan?: string;
  timeline?: string;
  deliverables?: string;
  experience?: string;
  risks?: string;
  next_step?: string;
  hook?: string;
  what_ill_deliver?: string;
  timeline_block?: string;
  deliverables_block?: string;
  relevant_experience?: string;
  risk_reduction?: string;
  call_to_action?: string;
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
  /** Server: `grounded` when indexed memory was used; `general` otherwise (legacy `empty` tolerated). */
  memory?: "empty" | "grounded" | "general";
  /** Stable ids of retrieval rows used for this run (may be empty). */
  source?: string[];
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
    opening?: string;
    understanding?: string;
    solution?: string;
    experience?: string;
    next_step?: string;
    risks?: string;
    execution_tasks?: string[];
    timeline?: string[];
    deliverables?: string[];
    hook?: string;
    understanding_need?: string;
    approach?: string;
    relevant_experience?: string;
    call_to_action?: string;
    risks_mitigation?: string;
    timeline_weeks?: string[];
    deliverables_list?: string[];
    body?: string;
    proof?: string;
    closing?: string;
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
  /** OpenRouter chat model id when set in user_settings (e.g. anthropic/claude-3.5-sonnet). */
  openrouter_model_primary: string;
  rag_config: WorkspaceRagConfig;
  proposal_mode: "auto" | "enterprise" | "freelance";
  updated_at: string | null;
};

export type WorkspaceSettingsUpdate = {
  company_profile?: Record<string, unknown>;
  tone?: string;
  writing_style?: string;
  openrouter_model_primary?: string | null;
  rag_config?: WorkspaceRagConfig;
  proposal_mode?: "auto" | "enterprise" | "freelance";
};

/** Optional per-run overlay merged server-side before SettingsInjector. */
export type ProposalWorkspaceInput = {
  tone?: string;
  writing_style?: string;
  openrouterModelPrimary?: string;
  proposal_mode?: "auto" | "enterprise" | "freelance";
  rag?: {
    enabled?: boolean;
    enterprise_case_studies?: boolean;
    freelance_win_memory?: boolean;
  };
  company_profile?: Record<string, unknown>;
};

export type WorkspaceStateEcho = Record<string, unknown>;

/** Sanitized POST /api/proposal/run — public proposal payload only (no DAG internals, RAG dumps, or critique). */
export type ProposalSectionPublic = {
  title: string;
  content: string;
};

export type CrossProposalDiffPublic = {
  delta_score: number;
  improvements: string[];
};

export type ProposalPublicRunResponse = {
  proposal_id: string;
  title: string;
  executive_summary: string;
  sections: ProposalSectionPublic[];
  score: number;
  issues: string[];
  memory_used: boolean;
  cross_proposal_diff: CrossProposalDiffPublic;
};

/** GET /api/proposal/runs/{id} — public run + brief echo + mode for the editor (no internals). */
export type ProposalSavedRunPublic = ProposalPublicRunResponse & {
  rfp_input: string;
  pipeline_mode: "enterprise" | "freelance";
};

export type MemoryPatternItem = {
  label: string;
  outcome: string;
};

export type ProposalRunSummary = {
  id: string;
  title: string;
  score: number;
  trace_id: string;
  pipeline_mode: string;
  created_at: string;
};

export type ApiVersionResponse = {
  version: string;
  /** Backend proposal graph identifier (currently the five-node DAG contract). */
  pipeline: string;
  rfp_max_chars: number;
  pipeline_timeout_s: number;
  /** HTTP timeout budget for individual LLM calls (not “N agents”). */
  per_agent_timeout_s: number;
  /** API loaded non-empty Supabase URL + service role key (inserts may still fail if schema/RLS/network). */
  supabase_env_loaded?: boolean;
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
