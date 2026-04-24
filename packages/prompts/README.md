# bidforge-prompts

Versioned system/user message builders — **one module per DAG node** (plus shared `__init__`). OpenRouter calls are made from the `api/` FastAPI app.

## Modules (5-node DAG)

| Module | DAG node |
|--------|----------|
| `router.py` | `router` — classify enterprise vs freelance |
| `job_intel.py` | `job_intel` — enterprise extract + matrix; freelance job signals |
| `solution.py` | `solution` — blueprint + strategy (enterprise or job) |
| `proposal.py` | `proposal` — sole long-form writer |
| `verifier.py` | `verifier` — enterprise QA JSON or job-post reply scoring |

Each file exports `*_PROMPT_VERSION` strings for cache keys and `dag_run` composites. Import explicitly, e.g. `from bidforge_prompts.proposal import PROPOSAL_PROMPT_VERSION`.
