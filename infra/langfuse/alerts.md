# Langfuse alerting strategy (BidForge)

Langfuse Cloud and self-hosted projects support **notifications** tied to metrics, score regressions, or usage anomalies. Use the scores and metadata emitted by the API (see `dashboards.md`) as the signal source rather than log text.

## Recommended thresholds

| Condition | Severity | Rationale |
| --- | --- | --- |
| **Average `proposal_quality` below 60** | Warning | Verifier indicates weak proposals; investigate prompts, RAG coverage, or model drift before customer impact spreads. |
| **Failure rate above 5%** | Alert | `metadata.status = failed` on `proposal_run` traces over a rolling 1h / 24h window; indicates pipeline or upstream LLM instability. |
| **`pipeline_latency` above 10,000 ms (10 s)** | Alert | User-facing slowness; often LLM timeouts, cold starts, or RAG latency. Tune timeouts or capacity after confirming `failed_step` metadata. |

## How to operationalize in Langfuse

1. **Create saved views** (filters) for: production environment, `name = proposal_run`, last 1 hour.
2. **Attach alerts** (where the Langfuse product supports it) to:
   - aggregate **average** or **percentile (p95)** of `pipeline_latency`;
   - **count** of traces with `metadata.status = failed` divided by total traces (failure rate);
   - **minimum** or **5th percentile** of `proposal_quality` dropping under 60.
3. **Route notifications** to Slack / PagerDuty / email with a link to the filtered trace list and to your primary on-call rotation.

## Runbook (when an alert fires)

1. Open the most recent **failed** or **slow** traces; read `metadata.failed_step` and child span errors.
2. Compare **`proposal_quality`**, **`issue_count`**, and **`compliance_risk_count`** before and after the incident window.
3. If failures cluster on one **agent** span, treat it as a localized regression (prompt, tool, or provider); if spread across agents, check **OpenRouter** status and API **rate limits**.

## Limits of in-process metrics

The API currently records **per-trace scores** (not a separate metrics server). For SLO reporting (e.g. monthly error budgets), export Langfuse data to your warehouse or use Langfuse’s analytics APIs in addition to these alerts.
