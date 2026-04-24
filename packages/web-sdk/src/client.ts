import { getApiBaseUrl } from "./env";
import {
  ApiErrorEnvelope,
  ApiVersionResponse,
  BidForgeApiError,
  MemoryPatternItem,
  NormalizedDocumentOutput,
  ProposalPublicRunResponse,
  ProposalRunSummary,
  ProposalSavedRunPublic,
  ProposalWorkspaceInput,
  WorkspaceSettingsResponse,
  WorkspaceSettingsUpdate,
} from "./types";

/** Default for routine API calls (settings, version, etc.). */
const DEFAULT_TIMEOUT_MS = 125_000;
const DEFAULT_RETRIES = 2;

/**
 * Browser `fetch` deadline for `POST /api/proposal/run`.
 * Must exceed the API's `pipeline_timeout_s` (see `/api/version`) plus network slack, or the
 * client aborts with `TIMEOUT` / "Request timed out waiting for the API." while the server is still working.
 */
export function proposalRunFetchTimeoutMs(pipelineTimeoutSeconds: number): number {
  const s = Number(pipelineTimeoutSeconds);
  if (!Number.isFinite(s) || s <= 0) {
    return 720_000;
  }
  return Math.ceil(Math.max(180, s + 120) * 1000);
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

async function parseJsonSafe(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { error: { code: "BAD_REQUEST", message: text.slice(0, 500) } };
  }
}

function isEnvelope(v: unknown): v is ApiErrorEnvelope {
  return (
    typeof v === "object" &&
    v !== null &&
    "error" in v &&
    typeof (v as ApiErrorEnvelope).error === "object" &&
    (v as ApiErrorEnvelope).error !== null &&
    "code" in (v as ApiErrorEnvelope).error &&
    "message" in (v as ApiErrorEnvelope).error
  );
}

export type BidForgeClientOptions = {
  baseUrl?: string;
  timeoutMs?: number;
  maxRetries?: number;
  /** Clerk session token — use `() => getToken()` from `@clerk/nextjs`. */
  getToken?: () => Promise<string | null>;
};

export class BidForgeClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly maxRetries: number;
  private readonly getToken?: () => Promise<string | null>;

  constructor(opts: BidForgeClientOptions = {}) {
    this.baseUrl = opts.baseUrl ?? getApiBaseUrl();
    this.timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.maxRetries = opts.maxRetries ?? DEFAULT_RETRIES;
    this.getToken = opts.getToken;
  }

  async getVersion(): Promise<ApiVersionResponse> {
    const res = await this.request("GET", "/api/version", undefined, {
      auth: false,
      retries: 0,
    });
    return res as ApiVersionResponse;
  }

  /**
   * Identity is enforced server-side from the Bearer token — never send `user_id` in the body.
   */
  async runProposal(input: {
    rfp: string;
    rfpId?: string;
    /** auto | enterprise | freelance — matches API `pipeline_mode`. */
    pipelineMode?: "auto" | "enterprise" | "freelance";
    /** Merged into workspace state before settings injection (optional). */
    workspace?: ProposalWorkspaceInput;
    draftIntensity?: "balanced" | "strong" | "weak";
    /** Prior saved run id for incremental pipeline_state chaining. */
    continuationRunId?: string;
    /** User-saved pattern / cues appended to the generation brief (server-truncated). */
    learningSnippet?: string;
  }): Promise<ProposalPublicRunResponse> {
    const body: Record<string, unknown> = {
      rfp: input.rfp,
      rfp_id: input.rfpId,
      pipeline_mode: input.pipelineMode ?? "auto",
      draft_intensity: input.draftIntensity ?? "balanced",
    };
    if (input.workspace) body.workspace = input.workspace;
    if (input.continuationRunId?.trim()) body.continuation_run_id = input.continuationRunId.trim();
    if (input.learningSnippet?.trim()) body.learning_snippet = input.learningSnippet.trim();
    const res = await this.request("POST", "/api/proposal/run", body, {
      auth: true,
      retries: this.maxRetries,
    });
    return res as ProposalPublicRunResponse;
  }

  async listMemoryPatterns(): Promise<MemoryPatternItem[]> {
    const res = await this.request("GET", "/api/proposal/memory/patterns", undefined, {
      auth: true,
      retries: 0,
    });
    return res as MemoryPatternItem[];
  }

  async getWorkspaceSettings(): Promise<WorkspaceSettingsResponse> {
    const res = await this.request("GET", "/api/workspace/settings", undefined, {
      auth: true,
      retries: 0,
    });
    return res as WorkspaceSettingsResponse;
  }

  async updateWorkspaceSettings(body: WorkspaceSettingsUpdate): Promise<WorkspaceSettingsResponse> {
    const res = await this.request("PUT", "/api/workspace/settings", body, {
      auth: true,
      retries: 0,
    });
    return res as WorkspaceSettingsResponse;
  }

  /**
   * Normalize PDF, DOCX, pasted text, or URL into structured sections (DocumentNormalizerAgent).
   */
  async normalizeWorkspaceDocument(input: {
    source: "text" | "pdf" | "docx" | "url";
    text?: string;
    url?: string;
    file?: File | Blob | null;
    filename?: string;
  }): Promise<NormalizedDocumentOutput> {
    const url = `${this.baseUrl}/api/workspace/document`;
    const fd = new FormData();
    fd.append("source", input.source);
    if (input.text != null && input.text.length > 0) fd.append("text", input.text);
    if (input.url != null && input.url.trim().length > 0) fd.append("url", input.url.trim());
    if (input.file) {
      const name = input.filename ?? (input.file instanceof File ? input.file.name : "upload.bin");
      fd.append("file", input.file, name);
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const headers: Record<string, string> = { Accept: "application/json" };
      if (this.getToken) {
        const token = await this.getToken();
        if (token) headers.Authorization = `Bearer ${token}`;
      }
      const res = await fetch(url, {
        method: "POST",
        headers,
        body: fd,
        signal: controller.signal,
      });
      clearTimeout(timer);
      const data = await parseJsonSafe(res);
      if (!res.ok) {
        if (isEnvelope(data)) throw new BidForgeApiError(res.status, data);
        throw new BidForgeApiError(res.status, {
          error: {
            code: "NORMALIZE_FAILED",
            message: `Document normalize failed (${res.status})`,
            trace_id: null,
          },
        });
      }
      return data as NormalizedDocumentOutput;
    } catch (e) {
      clearTimeout(timer);
      if (e instanceof BidForgeApiError) throw e;
      if ((e as Error).name === "AbortError") {
        throw new BidForgeApiError(504, {
          error: {
            code: "TIMEOUT",
            message: "Request timed out waiting for the API.",
            trace_id: null,
          },
        });
      }
      throw new BidForgeApiError(0, {
        error: {
          code: "INTERNAL_ERROR",
          message: (e as Error).message || "Network error",
          trace_id: null,
        },
      });
    }
  }

  async postMemoryFeedback(input: {
    content: string;
    user_feedback: "positive" | "negative";
    memory_type?: "proposal_section" | "win_pattern" | "methodology";
  }): Promise<{ status: string }> {
    const res = await this.request("POST", "/api/documents/memory/feedback", input, {
      auth: true,
      retries: 0,
    });
    return res as { status: string };
  }

  async ingestMemory(input: {
    text: string;
    title?: string;
    outcome?: "won" | "lost" | "pending";
    tags?: string[];
    memory_type?: "proposal_section" | "win_pattern" | "methodology";
  }): Promise<{ status: string; chunks_indexed: number }> {
    const res = await this.request("POST", "/api/memory/ingest", input, {
      auth: true,
      retries: 0,
    });
    return res as { status: string; chunks_indexed: number };
  }

  async exportProposalPdf(input: {
    title?: string;
    sections: Record<string, string>;
    timeline?: Array<{ phase: string; duration: string }>;
    memory_appendix?: string | null;
    pipeline_mode?: "enterprise" | "freelance";
    score?: number;
    issues?: string[];
    memory_insight_bullets?: string[];
  }): Promise<Blob> {
    const url = `${this.baseUrl}/api/proposal/export/pdf`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const headers: Record<string, string> = {
        Accept: "application/pdf",
        "Content-Type": "application/json",
      };
      if (this.getToken) {
        const token = await this.getToken();
        if (token) headers.Authorization = `Bearer ${token}`;
      }
      const res = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(input),
        signal: controller.signal,
      });
      clearTimeout(timer);
      const data = res.ok ? null : await parseJsonSafe(res);
      if (!res.ok) {
        if (isEnvelope(data)) throw new BidForgeApiError(res.status, data);
        throw new BidForgeApiError(res.status, {
          error: {
            code: "EXPORT_FAILED",
            message: `PDF export failed (${res.status})`,
            trace_id: null,
          },
        });
      }
      return res.blob();
    } catch (e) {
      clearTimeout(timer);
      if (e instanceof BidForgeApiError) throw e;
      if ((e as Error).name === "AbortError") {
        throw new BidForgeApiError(504, {
          error: {
            code: "TIMEOUT",
            message: "Request timed out waiting for the API.",
            trace_id: null,
          },
        });
      }
      throw new BidForgeApiError(0, {
        error: {
          code: "INTERNAL_ERROR",
          message: (e as Error).message || "Network error",
          trace_id: null,
        },
      });
    }
  }

  async postWinPattern(input: {
    content: string;
    title?: string;
    tags?: string[];
    pattern_kind?: "win_pattern" | "freelance_win_pattern";
  }): Promise<{ status: string }> {
    const res = await this.request("POST", "/api/documents/memory/pattern", input, {
      auth: true,
      retries: 0,
    });
    return res as { status: string };
  }

  async listProposalRuns(): Promise<ProposalRunSummary[]> {
    const res = await this.request("GET", "/api/proposal/runs", undefined, {
      auth: true,
      retries: 0,
    });
    return res as ProposalRunSummary[];
  }

  /** Top-level hydration alias (same rows as ``listProposalRuns``). */
  async listProposalsForHydration(): Promise<ProposalRunSummary[]> {
    const res = await this.request("GET", "/api/proposals", undefined, {
      auth: true,
      retries: 0,
    });
    return res as ProposalRunSummary[];
  }

  /** Top-level hydration alias (same payload as ``getWorkspaceSettings``). */
  async getSettingsForHydration(): Promise<WorkspaceSettingsResponse> {
    const res = await this.request("GET", "/api/settings", undefined, {
      auth: true,
      retries: 0,
    });
    return res as WorkspaceSettingsResponse;
  }

  async postProposalPattern(input: {
    proposalId: string;
    pattern: "strong" | "weak" | "saved";
  }): Promise<{ status: string; proposal_id: string; pattern: string }> {
    const res = await this.request(
      "POST",
      "/api/proposal/pattern",
      { proposalId: input.proposalId, pattern: input.pattern },
      { auth: true, retries: 0 },
    );
    return res as { status: string; proposal_id: string; pattern: string };
  }

  async getProposalRun(runId: string): Promise<ProposalSavedRunPublic> {
    const res = await this.request(
      "GET",
      `/api/proposal/runs/${encodeURIComponent(runId)}`,
      undefined,
      { auth: true, retries: 0 },
    );
    return res as ProposalSavedRunPublic;
  }

  private async request(
    method: string,
    path: string,
    jsonBody: unknown | undefined,
    opt: { auth: boolean; retries: number },
  ): Promise<unknown> {
    const url = `${this.baseUrl}${path}`;
    let attempt = 0;
    const maxAttempts = opt.retries + 1;

    while (attempt < maxAttempts) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeoutMs);
      try {
        const headers: Record<string, string> = {
          Accept: "application/json",
        };
        if (jsonBody !== undefined) {
          headers["Content-Type"] = "application/json";
        }
        if (opt.auth && this.getToken) {
          const token = await this.getToken();
          if (token) {
            headers.Authorization = `Bearer ${token}`;
          }
        }

        const res = await fetch(url, {
          method,
          headers,
          body: jsonBody === undefined ? undefined : JSON.stringify(jsonBody),
          signal: controller.signal,
        });

        clearTimeout(timer);
        const data = await parseJsonSafe(res);

        if (res.ok) {
          return data;
        }

        if (
          opt.retries > 0 &&
          attempt + 1 < maxAttempts &&
          (res.status === 502 || res.status === 503)
        ) {
          const backoff = 400 * 2 ** attempt + Math.random() * 120;
          await sleep(backoff);
          attempt += 1;
          continue;
        }

        if (isEnvelope(data)) {
          throw new BidForgeApiError(res.status, data);
        }
        throw new BidForgeApiError(res.status, {
          error: {
            code: "INTERNAL_ERROR",
            message: `Request failed (${res.status})`,
            trace_id: null,
          },
        });
      } catch (e) {
        clearTimeout(timer);
        if (e instanceof BidForgeApiError) throw e;
        if ((e as Error).name === "AbortError") {
          throw new BidForgeApiError(504, {
            error: {
              code: "TIMEOUT",
              message: "Request timed out waiting for the API.",
              trace_id: null,
            },
          });
        }
        if (
          opt.retries > 0 &&
          attempt + 1 < maxAttempts &&
          e instanceof TypeError
        ) {
          const backoff = 400 * 2 ** attempt;
          await sleep(backoff);
          attempt += 1;
          continue;
        }
        throw new BidForgeApiError(0, {
          error: {
            code: "INTERNAL_ERROR",
            message: (e as Error).message || "Network error",
            trace_id: null,
          },
        });
      }
    }

    throw new BidForgeApiError(0, {
      error: {
        code: "INTERNAL_ERROR",
        message: "Max retries exceeded",
        trace_id: null,
      },
    });
  }
}
