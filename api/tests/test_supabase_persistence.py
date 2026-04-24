"""Unit tests for Supabase-backed persistence (mocked client — no real network)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _select_eq_eq_limit_execute(rows: list[dict]) -> MagicMock:
    """Match chain: table().select(...).eq(...).eq(...).limit(1).execute()"""
    lim = MagicMock()
    lim.execute.return_value = MagicMock(data=rows)
    eq_id = MagicMock()
    eq_id.limit.return_value = lim
    eq_uid = MagicMock()
    eq_uid.eq.return_value = eq_id
    sel = MagicMock()
    sel.eq.return_value = eq_uid
    return sel


def _update_eq_eq_execute() -> MagicMock:
    """Match chain: table().update(...).eq(...).eq(...).execute()"""
    end = MagicMock()
    end.execute.return_value = MagicMock(data=[])
    eq2 = MagicMock()
    eq2.eq.return_value = end
    eq1 = MagicMock()
    eq1.eq.return_value = eq2
    upd = MagicMock()
    upd.eq.return_value = eq1
    return upd


def _list_order_limit_execute(rows: list[dict]) -> MagicMock:
    """Match: select().eq().order().limit().execute()"""
    lim = MagicMock()
    lim.execute.return_value = MagicMock(data=rows)
    ord_m = MagicMock()
    ord_m.limit.return_value = lim
    eq_m = MagicMock()
    eq_m.order.return_value = ord_m
    sel = MagicMock()
    sel.eq.return_value = eq_m
    return sel


def test_insert_proposal_run_writes_proposals_table_and_returns_id() -> None:
    from app.integrations import proposal_store

    new_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": new_id}],
    )

    with (
        patch.object(proposal_store, "get_supabase_client", return_value=mock_sb),
        patch.object(proposal_store, "_insert_proposal_run_audit_row", MagicMock()),
    ):
        from app.integrations.proposal_store import insert_proposal_run

        pid = insert_proposal_run(
            "user_clerk_1",
            rfp_input="RFP body",
            proposal_output={
                "proposal": {"sections": {}},
                "pipeline_state": {"selected_pattern": "strong", "draft_version": 1},
            },
            score=80,
            issues=["a"],
            title="T",
            trace_id="trace-1",
            pipeline_mode="enterprise",
        )

    assert pid == new_id
    mock_sb.table.assert_called_with("proposals")
    ins = mock_sb.table.return_value.insert
    ins.assert_called_once()
    row = ins.call_args[0][0]
    assert row["user_id"] == "user_clerk_1"
    assert row["rfp_text"] == "RFP body"
    assert row["input_text"] == "RFP body"
    assert row["pattern"] == "strong"
    assert row["proposal_content"]["pipeline_state"]["selected_pattern"] == "strong"


def test_insert_proposal_run_returns_none_without_client() -> None:
    from app.integrations import proposal_store

    with patch.object(proposal_store, "get_supabase_client", return_value=None):
        from app.integrations.proposal_store import insert_proposal_run

        assert (
            insert_proposal_run(
                "u",
                rfp_input="x",
                proposal_output={},
                score=0,
                issues=[],
                title="",
                trace_id="t",
                pipeline_mode="enterprise",
            )
            is None
        )


def test_insert_proposal_run_refuses_empty_source_input() -> None:
    from app.integrations import proposal_store

    mock_sb = MagicMock()
    with patch.object(proposal_store, "get_supabase_client", return_value=mock_sb):
        from app.integrations.proposal_store import insert_proposal_run

        assert (
            insert_proposal_run(
                "u",
                rfp_input="   ",
                proposal_output={},
                score=0,
                issues=[],
                title="",
                trace_id="t",
                pipeline_mode="e",
            )
            is None
        )
    mock_sb.table.assert_not_called()


def test_insert_proposal_run_returns_none_on_empty_response() -> None:
    from app.integrations import proposal_store

    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])

    with patch.object(proposal_store, "get_supabase_client", return_value=mock_sb):
        from app.integrations.proposal_store import insert_proposal_run

        assert insert_proposal_run("u", rfp_input="x", proposal_output={}, score=0, issues=[], title="", trace_id="t", pipeline_mode="e") is None


def test_get_proposal_run_maps_row_to_api_shape() -> None:
    from app.integrations import proposal_store

    rid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    db_row = {
        "id": rid,
        "user_id": "user_clerk_1",
        "rfp_text": "hello rfp",
        "proposal_content": {
            "proposal": {"sections": {"executive_summary": "S"}},
            "pipeline_state": {"draft_version": 2},
        },
        "pipeline_state": {"selected_pattern": "weak"},
        "settings_snapshot": {"tone": "formal"},
        "pattern": "weak",
        "title": "My title",
        "score": 77,
        "issues": ["i1"],
        "trace_id": "tr",
        "pipeline_mode": "freelance",
        "created_at": "2026-01-01T00:00:00Z",
    }
    mock_sb = MagicMock()
    t = MagicMock()
    t.select.return_value = _select_eq_eq_limit_execute([db_row])
    mock_sb.table.return_value = t

    with patch.object(proposal_store, "get_supabase_client", return_value=mock_sb):
        from app.integrations.proposal_store import get_proposal_run

        out = get_proposal_run("user_clerk_1", rid)

    assert out is not None
    assert out["id"] == rid
    assert out["rfp_input"] == "hello rfp"
    assert out["proposal_output"]["proposal"]["sections"]["executive_summary"] == "S"
    assert out["proposal_output"]["settings_snapshot"]["tone"] == "formal"
    ps = out["proposal_output"]["pipeline_state"]
    assert ps["selected_pattern"] == "weak"
    assert ps["draft_version"] == 2


def test_get_proposal_run_prefers_input_text_over_rfp_text() -> None:
    from app.integrations import proposal_store

    rid = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    db_row = {
        "id": rid,
        "user_id": "user_clerk_1",
        "rfp_text": "stale",
        "input_text": "canonical brief",
        "input_type": "job_post",
        "proposal_content": {"proposal": {"sections": {}}},
        "pipeline_state": {},
        "settings_snapshot": {},
        "pattern": "saved",
        "title": "T",
        "score": 1,
        "issues": [],
        "trace_id": "tr",
        "pipeline_mode": "enterprise",
        "created_at": "2026-01-01T00:00:00Z",
    }
    mock_sb = MagicMock()
    t = MagicMock()
    t.select.return_value = _select_eq_eq_limit_execute([db_row])
    mock_sb.table.return_value = t

    with patch.object(proposal_store, "get_supabase_client", return_value=mock_sb):
        from app.integrations.proposal_store import get_proposal_run

        out = get_proposal_run("user_clerk_1", rid)

    assert out is not None
    assert out["rfp_input"] == "canonical brief"
    assert out["input_type"] == "job_post"


def test_build_public_from_stored_preserves_rfp_input() -> None:
    from app.contracts.proposal_public import build_public_from_stored_proposal_output

    po = {"proposal": {"sections": {}}, "pipeline_mode": "enterprise"}
    pub = build_public_from_stored_proposal_output(
        po,
        row_title="T",
        row_score=50,
        row_issues=[],
        row_id="rid",
        rfp_input="  original brief  ",
        input_type="rfp",
    )
    assert pub.rfp_input == "original brief"
    assert pub.input_type == "rfp"


def test_list_proposal_runs_queries_proposals() -> None:
    from app.integrations import proposal_store

    rows = [
        {"id": "1", "title": "A", "score": 1, "trace_id": "t", "pipeline_mode": "e", "created_at": "2026-01-02"},
    ]
    mock_sb = MagicMock()
    t = MagicMock()
    t.select.return_value = _list_order_limit_execute(rows)
    mock_sb.table.return_value = t

    with (
        patch.object(proposal_store, "get_supabase_client", return_value=mock_sb),
        patch.object(proposal_store, "resolve_users_uuid_for_clerk", return_value=None),
    ):
        from app.integrations.proposal_store import list_proposal_runs

        out = list_proposal_runs("user_clerk_1", limit=10)

    assert out == rows
    mock_sb.table.assert_called_with("proposals")


def test_merge_proposal_run_output_metadata_updates_row() -> None:
    from app.integrations import proposal_store

    read_row = {
        "proposal_content": {"proposal": {"x": 1}},
        "settings_snapshot": {"tone": "old"},
    }
    proposals_table = MagicMock()
    proposals_table.select.return_value = _select_eq_eq_limit_execute([read_row])
    proposals_table.update.return_value = _update_eq_eq_execute()

    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        assert name == "proposals"
        return proposals_table

    mock_sb.table.side_effect = _table

    with patch.object(proposal_store, "get_supabase_client", return_value=mock_sb):
        from app.integrations.proposal_store import merge_proposal_run_output_metadata

        ok = merge_proposal_run_output_metadata(
            "user_clerk_1",
            "cccccccc-cccc-cccc-cccc-cccccccccccc",
            settings_snapshot={"tone": "warm", "rag_enabled": True},
            rfp_id="rfp-ext-9",
        )

    assert ok is True
    proposals_table.update.assert_called_once()
    upd_payload = proposals_table.update.call_args[0][0]
    assert upd_payload["settings_snapshot"]["tone"] == "warm"
    assert upd_payload["settings_snapshot"]["rag_enabled"] is True
    assert upd_payload["proposal_content"]["settings_snapshot"]["tone"] == "warm"
    assert upd_payload["proposal_content"]["rfp_id"] == "rfp-ext-9"


def test_update_proposal_run_pattern_inserts_pattern_and_updates_proposal() -> None:
    from app.integrations import proposal_store

    read_row = {
        "proposal_content": {"proposal": {}, "pipeline_state": {"draft_version": 1}},
        "pipeline_state": {"selected_pattern": "saved"},
    }
    proposals_table = MagicMock()
    proposals_table.select.return_value = _select_eq_eq_limit_execute([read_row])
    proposals_table.update.return_value = _update_eq_eq_execute()

    patterns_table = MagicMock()
    patterns_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "p1"}])

    def _table(name: str) -> MagicMock:
        if name == "proposals":
            return proposals_table
        if name == "proposal_patterns":
            return patterns_table
        raise AssertionError(name)

    mock_sb = MagicMock()
    mock_sb.table.side_effect = _table
    rid = "dddddddd-dddd-dddd-dddd-dddddddddddd"

    with patch.object(proposal_store, "get_supabase_client", return_value=mock_sb):
        from app.integrations.proposal_store import update_proposal_run_pattern

        ok = update_proposal_run_pattern("user_clerk_1", rid, pattern="strong")

    assert ok is True
    patterns_table.insert.assert_called_once()
    pin = patterns_table.insert.call_args[0][0]
    assert pin["proposal_id"] == rid
    assert pin["pattern"] == "strong"
    proposals_table.update.assert_called_once()
    body = proposals_table.update.call_args[0][0]
    assert body["pattern"] == "strong"
    assert body["proposal_content"]["pipeline_state"]["selected_pattern"] == "strong"


def test_update_proposal_run_pattern_rejects_invalid_pattern() -> None:
    from app.integrations import proposal_store

    mock_sb = MagicMock()
    with patch.object(proposal_store, "get_supabase_client", return_value=mock_sb):
        from app.integrations.proposal_store import update_proposal_run_pattern

        assert update_proposal_run_pattern("u", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", pattern="nope") is False
    mock_sb.table.assert_not_called()


def test_user_settings_upsert_and_get_roundtrip_mapping() -> None:
    from app.integrations import workspace_settings_store

    def _get_execute() -> MagicMock:
        return MagicMock(
            data=[
                {
                    "user_id": "clerk_x",
                    "tone": "Formal",
                    "mode": "freelance",
                    "rag_enabled": False,
                    "preferences": {
                        "writing_style": "Short",
                        "openrouter_model_primary": "openai/gpt-4o-mini",
                        "company_profile": {"industry": "AI"},
                        "rag_config": {
                            "enabled": False,
                            "enterprise_case_studies": True,
                            "freelance_win_memory": False,
                            "proposal_mode": "freelance",
                        },
                    },
                    "updated_at": "2026-04-01T12:00:00Z",
                },
            ],
        )

    mock_sb_get = MagicMock()
    mock_sb_get.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        MagicMock(data=[])
    )

    with patch.object(workspace_settings_store, "get_supabase_client", return_value=mock_sb_get):
        from app.integrations.workspace_settings_store import get_workspace_settings_row

        assert get_workspace_settings_row("unknown") is None

    mock_sb_row = MagicMock()
    mock_sb_row.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        _get_execute()
    )

    with patch.object(workspace_settings_store, "get_supabase_client", return_value=mock_sb_row):
        from app.integrations.workspace_settings_store import get_workspace_settings_row

        row = get_workspace_settings_row("clerk_x")

    assert row is not None
    assert row["tone"] == "Formal"
    assert row["writing_style"] == "Short"
    assert row["company_profile"] == {"industry": "AI"}
    assert row["rag_config"]["enabled"] is False
    assert row["rag_config"]["proposal_mode"] == "freelance"
    assert row["openrouter_model_primary"] == "openai/gpt-4o-mini"

    mock_sb_up = MagicMock()
    mock_sb_up.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{}])

    with patch.object(workspace_settings_store, "get_supabase_client", return_value=mock_sb_up):
        from app.integrations.workspace_settings_store import upsert_workspace_settings_full

        ok = upsert_workspace_settings_full(
            "clerk_x",
            {
                "tone": "Warm",
                "writing_style": "Long",
                "company_profile": {},
                "rag_config": {
                    "enabled": True,
                    "enterprise_case_studies": False,
                    "freelance_win_memory": True,
                    "proposal_mode": "enterprise",
                },
                "openrouter_model_primary": "anthropic/claude-3.5-sonnet",
            },
        )

    assert ok is True
    mock_sb_up.table.assert_called_with("user_settings")
    payload = mock_sb_up.table.return_value.upsert.call_args[0][0]
    assert payload["tone"] == "Warm"
    assert payload["mode"] == "enterprise"
    assert payload["rag_enabled"] is True
    assert payload["preferences"]["writing_style"] == "Long"
    assert payload["preferences"]["openrouter_model_primary"] == "anthropic/claude-3.5-sonnet"


def test_user_settings_upsert_returns_false_without_client() -> None:
    from app.integrations import workspace_settings_store

    with patch.object(workspace_settings_store, "get_supabase_client", return_value=None):
        from app.integrations.workspace_settings_store import upsert_workspace_settings_full

        assert upsert_workspace_settings_full("u", {"tone": "x", "writing_style": "", "company_profile": {}, "rag_config": {}}) is False


@pytest.mark.parametrize(
    "inner,expected",
    [
        ({"pipeline_state": {"selected_pattern": "weak"}}, "weak"),
        ({}, "saved"),
        ({"pipeline_state": {"selected_pattern": "bogus"}}, "saved"),
    ],
)
def test_pattern_from_proposal_output(inner: dict, expected: str) -> None:
    from app.integrations.proposal_store import _pattern_from_proposal_output

    assert _pattern_from_proposal_output(inner) == expected


def test_get_api_proposals_hydration_alias_calls_store() -> None:
    import app.modules.proposal.router as proposal_router

    rows = [
        {
            "id": str(uuid.uuid4()),
            "title": "Hydration",
            "score": 90,
            "trace_id": "tr-h",
            "pipeline_mode": "enterprise",
            "created_at": "2026-04-22T00:00:00Z",
        },
    ]
    with patch.object(proposal_router, "list_proposal_runs", return_value=rows):
        client = TestClient(app)
        r = client.get("/api/proposals")

    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["title"] == "Hydration"
    assert data[0]["score"] == 90


def test_post_api_proposal_pattern_404_when_store_returns_false() -> None:
    import app.modules.proposal.router as proposal_router

    pid = str(uuid.uuid4())
    with patch.object(proposal_router, "update_proposal_run_pattern", return_value=False):
        client = TestClient(app)
        r = client.post("/api/proposal/pattern", json={"proposalId": pid, "pattern": "strong"})

    assert r.status_code == 404


def test_post_api_proposal_pattern_ok_when_store_returns_true() -> None:
    import app.modules.proposal.router as proposal_router

    pid = str(uuid.uuid4())
    with patch.object(proposal_router, "update_proposal_run_pattern", return_value=True):
        client = TestClient(app)
        r = client.post("/api/proposal/pattern", json={"proposalId": pid, "pattern": "saved"})

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["proposal_id"] == pid
    assert body["pattern"] == "saved"


def test_put_api_workspace_settings_503_when_upsert_fails() -> None:
    import app.modules.workspace.router as workspace_router

    with patch.object(workspace_router, "upsert_workspace_settings_full", return_value=False):
        client = TestClient(app)
        r = client.put("/api/workspace/settings", json={"tone": "concise"})

    assert r.status_code == 503
    body = r.json()
    assert body.get("error", {}).get("code") == "STORAGE_UNAVAILABLE"
