# bidforge-agents

Pure Python **DAG node** implementations: each function takes typed inputs plus `bidforge_shared.LLMClient` and returns Pydantic models from `bidforge_schemas`. HTTP, Langfuse, and Supabase live in `api/`.

There are **five** node modules aligned with the traced DAG (`router`, `job_intel`, `solution`, `proposal`, `verifier`). `POST /api/proposal/run` also runs **three** workspace helpers *before* the proposal DAG; see [`docs/agents.md`](../../docs/agents.md).

## Active modules

| Module | DAG node |
|--------|----------|
| `router_agent.py` | `router` |
| `job_intel_agent.py` | `job_intel` (extract / matrix / signals + `requirements_for_solution_builder`) |
| `solution_agent.py` | `solution` (blueprint + strategy) |
| `proposal_agent.py` | `proposal` (sole writer) |
| `verifier_agent.py` | `verifier` |
| `proposal_dag.py` | Shared stage helpers for solution → proposal → verifier bundles |
| `proposal_quality_gate.py` | Validates writer / blueprint JSON shape |

See **[`docs/agents.md`](../../docs/agents.md)** for orchestration.
