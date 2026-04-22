# Langfuse dashboards (BidForge)

BidForge emits **trace-level metadata** and **numeric scores** from the `api/` service (see `api/app/pipeline/orchestrator.py`). Use these definitions in the Langfuse UI (Dashboards / Metrics) so monitoring stays actionable rather than raw log browsing.

## Shared filters

- **Environment**: filter by `metadata.env` or Langfuse environment (`LANGFUSE_TRACING_ENVIRONMENT`).
- **User**: filter by `metadata.user_id` or Langfuse `userId` when propagated.
- **Scores**: `proposal_quality`, `pipeline_latency`, `issue_count`, `compliance_risk_count`, plus span `latency_ms` in observation metadata.

---

## Dashboard 1 — Pipeline health

**Purpose:** availability and latency of the proposal run.

| Metric / chart | How to build it in Langfuse |
| --- | --- |
| **success_rate** | Ratio of traces where `metadata.status` = `completed` vs all `proposal_run` traces in the window. |
| **failure_rate** | Traces with `metadata.status` = `failed` or `metadata.trace_status` = `failed` (same window). |
| **avg_latency** | Average of score **`pipeline_latency`** (ms) for completed runs. |
| **failures_by_agent** | Break down failed traces by `metadata.failed_step` (values align with span names: `requirement_agent`, `rag_retrieval`, etc.). |

**Suggested widgets:** time-series for success/failure counts, table for top `failed_step`, histogram of `pipeline_latency`.

---

## Dashboard 2 — Proposal quality

**Purpose:** verifier output and risk signals.

| Metric / chart | How to build it in Langfuse |
| --- | --- |
| **avg_score** | Average of score **`proposal_quality`**. |
| **score_distribution** | Histogram or bucket chart of **`proposal_quality`**. |
| **issue_frequency** | Average or sum of score **`issue_count`** over time. |
| **compliance_risk_trends** | Time-series of score **`compliance_risk_count`**. |

**Suggested widgets:** line chart for `avg_score` and `compliance_risk_count`, distribution for `proposal_quality`.

---

## Dashboard 3 — User activity

**Purpose:** usage and experience by tenant (`user_id` from JWT, never from client body).

| Metric / chart | How to build it in Langfuse |
| --- | --- |
| **runs per user** | Count of `proposal_run` traces grouped by `metadata.user_id`. |
| **avg score per user** | Average **`proposal_quality`** grouped by `metadata.user_id`. |
| **latency per user** | Average **`pipeline_latency`** grouped by `metadata.user_id`. |

**Suggested widgets:** bar chart for run volume per user, table for top users by latency or low score.

---

## Implementation notes

1. **Score names** are stable: `proposal_quality`, `pipeline_latency`, `issue_count`, `compliance_risk_count`.
2. **Trace metadata** includes `user_id`, `env`, `runtime` (`vercel` when `VERCEL=1`, else `local`), `pipeline_version`, and terminal `status` / `trace_status`.
3. **Per-step latency** lives on each agent span’s `metadata.latency_ms` and `metadata.agent` for drill-down from a failed or slow trace.

For alerting thresholds and operational response, see `alerts.md` in this directory.
