"""
Canonical Supabase/PostgREST resource names.

The Python client uses ``Client.table(name)`` which targets the ``public`` schema
by default — there is no separate API for ``public.proposals`` vs ``proposals``.
Constants here document the **fully qualified** intent for logs and reviews.
"""

from __future__ import annotations

POSTGRES_SCHEMA = "public"

# Core persistence (migration_003)
T_PROPOSALS = "proposals"  # public.proposals — pipeline runs
T_PROPOSAL_EVENTS = "proposal_events"  # public.proposal_events — append-only DAG node traces
T_PROPOSAL_NODE_CACHE = "proposal_node_cache"  # public.proposal_node_cache — deterministic node outputs
T_PROPOSAL_TEMPLATES = "proposal_templates"  # public.proposal_templates — dynamic job-type templates
T_WORKSPACE_SETTINGS = "workspace_settings"  # public.workspace_settings — legacy shape
T_USER_SETTINGS = "user_settings"  # public.user_settings — API read/write path
T_USERS = "users"
T_PROPOSAL_PATTERNS = "proposal_patterns"
T_FREELANCE_WIN_MEMORY = "freelance_win_memory"
T_LEGACY_CANONICAL_PROPOSALS = "legacy_canonical_proposals"
T_PROPOSAL_MEMORY = "proposal_memory"
T_DOCUMENTS = "documents"

# Optional (migration_004 / 005)
T_PROPOSAL_DRAFTS = "proposal_drafts"
T_MEMORY_USAGE_LOG = "memory_usage_log"
T_PROPOSAL_RUNS = "proposal_runs"  # public.proposal_runs — audit companion to proposals


def fq(name: str) -> str:
    """Qualified name for log messages only."""
    return f"{POSTGRES_SCHEMA}.{name}"
