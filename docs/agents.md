# BidForge proposal generation — **5-node DAG**

One deterministic execution graph per `POST /api/proposal/run` (after pre-pipeline workspace prep). **Exactly one node performs long-form proposal writing:** `proposal` (`proposal_agent` implementation).

---

## Vocabulary

| Term | Meaning |
|------|--------|
| **DAG node** | A unit traced in `public.proposal_events` with stable `node_id` (`api/app/pipeline/dag_run.py`). |
| **Node module** | Python per DAG node: `router_agent`, `job_intel_agent`, `solution_agent`, `proposal_agent`, `verifier_agent` under `packages/agents/bidforge_agents/`. |
| **Pre-pipeline** | Workspace shaping **before** the DAG; not DAG nodes. |

---

## Pre-pipeline (HTTP only — **not** the proposal DAG)

Runs in `api/app/modules/proposal/router.py` before `execute_proposal_pipeline`:

| Step | Function | Package |
|------|----------|---------|
| 1 | `run_document_normalizer_agent` | `api/app/workspace/agents.py` |
| 2 | `run_workspace_builder_agent` | `api/app/workspace/agents.py` |
| 3 | `run_settings_injector_agent` | `api/app/workspace/agents.py` |

---

## Proposal DAG — **5 nodes** (mandatory order)

**Orchestrator:** `api/app/pipeline/orchestrator.py`  
**Trace + cache + events:** `api/app/pipeline/dag_run.py` → `public.proposal_events`, `public.proposal_node_cache`  
**Bundled helpers:** `packages/agents/bidforge_agents/proposal_dag.py` composes `solution` → `proposal` → `verifier` calls for the orchestrator.

| # | `node_id` | Role | Writer? |
|---|-----------|------|--------|
| 1 | `router` | Classify `freelance` \| `enterprise`; routing only | No |
| 2 | `job_intel` | Enterprise: extract + requirement matrix + RAG. Freelance: job signals + RAG. | No |
| 3 | `solution` | Blueprint + strategy; single source of truth for tasks / timeline / deliverables / positioning | No |
| 4 | `proposal` | Full business proposal from solution output (**only** long-form writer) | **Yes** |
| 5 | `verifier` | Score, structure checks, timeline/deliverable validation (read-only) | No |

Composite prompt version strings (enterprise vs freelance) live on keys like `job_intel_enterprise`, `solution_freelance`, `verifier_enterprise` in `default_node_prompt_versions()`.

---

## Run summary (Supabase)

After persistence, `DagRun.emit_run_summary` appends an additional `proposal_events` row with logical id **`dag_summary`**. Its `output` JSON includes `proposal_id`, `pipeline_mode`, `nodes` (snapshot of per-node outputs: `router`, `job_intel`, `solution`, `proposal`, `verifier`), `version`, `timestamp`, and `model: "openrouter"`.

---

## What is *not* in the DAG

No separate traced nodes for: critique-as-rewrite, formatter-only pass, freelance hook agent, duplicate strategy layers, or cross-proposal diff **writing**. Cross-diff may exist as an empty product placeholder only.

---

## Persistence

When **`ENV=production`** or **`STRICT_PROPOSAL_PERSISTENCE=1`**, `POST /api/proposal/run` requires Supabase and **`public.proposals`** + **`public.proposal_events`**. `ENV=test` relaxes strict persistence for unit tests.

---

## Code map

| Layer | Path |
|--------|------|
| HTTP + pre-pipeline | `api/app/modules/proposal/router.py`, `api/app/workspace/agents.py` |
| DAG orchestration | `api/app/pipeline/orchestrator.py` |
| Node trace + cache + summary | `api/app/pipeline/dag_run.py` |
| Stage implementations | `packages/agents/bidforge_agents/*.py` (including `proposal_dag.py` stage helpers) |
| Prompts | `packages/prompts/bidforge_prompts/` |
| Contracts | `packages/schemas/bidforge_schemas/pipeline.py` |

## Web app

The Next.js UI (`apps/web`) calls the same `POST /api/proposal/run` contract as before (`pipeline_mode`, brief text, workspace echo). Copy is aligned with the **five traced nodes**; the browser does not receive per-node traces unless you add a dedicated API for operators. `GET /api/meta/version` field `pipeline` is **`5-node-dag-v1`** for integration checks.
