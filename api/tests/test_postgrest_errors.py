from __future__ import annotations

from app.integrations.postgrest_errors import (
    column_missing_log_suffix,
    is_column_missing_error,
    is_missing_relation_error,
    missing_relation_log_suffix,
)


def test_pgrst205_detected() -> None:
    class E(Exception):
        pass

    assert is_missing_relation_error(E("Could not find the table 'public.proposals' in the schema cache"))


def test_suffix_for_missing() -> None:
    class E(Exception):
        pass

    s = missing_relation_log_suffix(E("PGRST205"))
    assert "migration" in s.lower() or "reload" in s.lower()


def test_suffix_empty_for_other_errors() -> None:
    assert missing_relation_log_suffix(RuntimeError("timeout")) == ""


def test_column_missing_detected() -> None:
    assert is_column_missing_error(Exception("42703 column users.id does not exist"))
    assert column_missing_log_suffix(Exception("42703")) != ""
