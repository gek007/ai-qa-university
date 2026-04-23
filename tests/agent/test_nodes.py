"""Unit tests for individual agent nodes.

Covers:
    - _clean_sql utility
    - should_retry routing
    - make_generate_sql_node: prompt selection (first vs retry), error clearing
    - make_run_sql_node: success / failure / retry increment
    - make_format_answer_node: success vs max-retry error branch
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from agent import prompts
from agent.nodes import (
    MAX_RETRIES,
    _clean_sql,
    make_format_answer_node,
    make_generate_sql_node,
    make_run_sql_node,
    should_retry,
)
from database.db import Database

from .conftest import MockChatModel


# ---------------------------------------------------------------------------
# _clean_sql
# ---------------------------------------------------------------------------


def test_clean_sql_strips_markdown_fence() -> None:
    raw = "```sql\nSELECT * FROM students\n```"
    assert _clean_sql(raw) == "SELECT * FROM students"


def test_clean_sql_strips_trailing_semicolon_and_whitespace() -> None:
    assert _clean_sql("  SELECT 1 ;  ") == "SELECT 1"


def test_clean_sql_leaves_plain_sql_untouched() -> None:
    assert _clean_sql("SELECT id FROM teachers") == "SELECT id FROM teachers"


# ---------------------------------------------------------------------------
# should_retry
# ---------------------------------------------------------------------------


def test_should_retry_no_error_goes_to_format() -> None:
    assert should_retry({"error": None}) == "format_answer"
    assert should_retry({}) == "format_answer"


def test_should_retry_error_under_budget_retries() -> None:
    assert should_retry({"error": "boom", "retries": 1}) == "generate_sql"


def test_should_retry_error_at_or_above_budget_formats() -> None:
    assert should_retry({"error": "boom", "retries": MAX_RETRIES}) == "format_answer"
    assert (
        should_retry({"error": "boom", "retries": MAX_RETRIES + 5}) == "format_answer"
    )


# ---------------------------------------------------------------------------
# make_generate_sql_node
# ---------------------------------------------------------------------------


def test_generate_sql_uses_initial_prompt_and_clears_error() -> None:
    llm = MockChatModel(["SELECT COUNT(*) FROM students"])
    node = make_generate_sql_node(llm, schema="SCHEMA_TEXT")

    out = node({"question": "How many students?"})

    assert out == {"sql": "SELECT COUNT(*) FROM students", "error": None}
    messages = llm.calls[0]
    assert isinstance(messages[0], SystemMessage)
    assert "SCHEMA_TEXT" in messages[0].content
    assert isinstance(messages[1], HumanMessage)
    assert "How many students?" in messages[1].content
    assert "previous SQL" not in messages[1].content


def test_generate_sql_uses_retry_prompt_when_error_present() -> None:
    llm = MockChatModel(["SELECT COUNT(*) FROM students"])
    node = make_generate_sql_node(llm, schema="SCHEMA")

    out = node(
        {
            "question": "How many students?",
            "sql": "SELECT bogus FROM nowhere",
            "error": "no such table: nowhere",
            "retries": 1,
        }
    )

    assert out["sql"] == "SELECT COUNT(*) FROM students"
    assert out["error"] is None
    user_msg = llm.calls[0][1].content
    assert "previous SQL" in user_msg
    assert "SELECT bogus FROM nowhere" in user_msg
    assert "no such table: nowhere" in user_msg


def test_generate_sql_strips_markdown_fence_from_llm_output() -> None:
    llm = MockChatModel(["```sql\nSELECT 1\n```"])
    node = make_generate_sql_node(llm, schema="SCHEMA")

    out = node({"question": "q"})

    assert out["sql"] == "SELECT 1"


# ---------------------------------------------------------------------------
# make_run_sql_node
# ---------------------------------------------------------------------------


def test_run_sql_success_returns_rows_and_no_error(db: Database) -> None:
    node = make_run_sql_node(db)

    out = node({"sql": "SELECT COUNT(*) AS n FROM students"})

    assert out["error"] is None
    assert out["results"] == [{"n": 20}]


def test_run_sql_failure_captures_error_and_increments_retries(db: Database) -> None:
    node = make_run_sql_node(db)

    out = node({"sql": "SELECT * FROM non_existent_table", "retries": 0})

    assert out["results"] == []
    assert out["error"] is not None
    assert out["retries"] == 1


def test_run_sql_failure_blocks_non_select(db: Database) -> None:
    node = make_run_sql_node(db)

    out = node({"sql": "DROP TABLE students", "retries": 0})

    assert out["error"] is not None
    assert "Only SELECT" in out["error"] or "SELECT" in out["error"]
    assert out["retries"] == 1


# ---------------------------------------------------------------------------
# make_format_answer_node
# ---------------------------------------------------------------------------


def test_format_answer_success_uses_answer_prompt() -> None:
    llm = MockChatModel(["There are 20 students."])
    node = make_format_answer_node(llm)

    out = node(
        {
            "question": "How many students?",
            "sql": "SELECT COUNT(*) AS n FROM students",
            "results": [{"n": 20}],
            "error": None,
        }
    )

    assert out["answer"] == "There are 20 students."
    system_msg = llm.calls[0][0].content
    user_msg = llm.calls[0][1].content
    assert prompts.ANSWER_SYSTEM_PROMPT.strip() in system_msg
    assert "How many students?" in user_msg
    assert "SELECT COUNT(*)" in user_msg
    assert '"n": 20' in user_msg or '"n":20' in user_msg


def test_format_answer_error_branch_used_when_retries_exhausted() -> None:
    llm = MockChatModel(["Sorry, I couldn't answer that. Please rephrase."])
    node = make_format_answer_node(llm)

    out = node(
        {
            "question": "impossible question",
            "sql": "SELECT bogus FROM nowhere",
            "results": [],
            "error": "no such table: nowhere",
            "retries": MAX_RETRIES,
        }
    )

    assert "rephrase" in out["answer"].lower()
    user_msg = llm.calls[0][1].content
    assert "impossible question" in user_msg
    assert "bogus" not in user_msg
