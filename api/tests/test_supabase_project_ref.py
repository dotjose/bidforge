from __future__ import annotations

from app.integrations.supabase import supabase_project_ref_from_url


def test_supabase_project_ref_from_host() -> None:
    assert supabase_project_ref_from_url("https://abc123.supabase.co") == "abc123"
    assert supabase_project_ref_from_url("https://abc123.supabase.co/") == "abc123"
    assert supabase_project_ref_from_url("") is None
    assert supabase_project_ref_from_url("https://example.com") is None
