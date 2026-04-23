"""LangGraph node implementations for the QA agent.

Each `make_*_node` is a factory that closes over the dependencies the node
needs (LLM, schema, database). This keeps nodes pure functions of state
while staying trivially testable.
"""

from __future__ import annotations

import json
from typing import Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from agent import prompts
from agent.state import AgentState
from database.db import Database

# `retries` is incremented inside `run_sql` on every failure. As soon as
# `retries >= MAX_RETRIES`, `should_retry` routes to `format_answer` and the
# error-aware branch of that node explains the failure to the user.
MAX_RETRIES = 2


def _clean_sql(text: str) -> str:
    """Strip common LLM artefacts (markdown fences, trailing semicolon)."""
    s = text.strip()
    if s.startswith("```"):
        lines = [ln for ln in s.splitlines() if not ln.strip().startswith("```")]
        s = "\n".join(lines).strip()
    if s.endswith(";"):
        s = s[:-1].rstrip()
    return s


def make_generate_sql_node(
    llm: BaseChatModel, schema: str
) -> Callable[[AgentState], dict]:
    """Produce a node that asks the LLM for SQL given the state's question."""

    system = SystemMessage(content=prompts.SQL_SYSTEM_PROMPT.format(schema=schema))

    def generate_sql(state: AgentState) -> dict:
        previous_error = state.get("error")
        if previous_error:
            user_text = prompts.SQL_RETRY_USER_PROMPT.format(
                question=state["question"],
                previous_sql=state.get("sql", ""),
                error=previous_error,
            )
        else:
            user_text = prompts.SQL_USER_PROMPT.format(question=state["question"])

        response = llm.invoke([system, HumanMessage(content=user_text)])
        sql = _clean_sql(str(response.content))
        return {"sql": sql, "error": None}

    return generate_sql


def make_run_sql_node(database: Database) -> Callable[[AgentState], dict]:
    """Produce a node that executes the state's SQL against the database."""

    def run_sql(state: AgentState) -> dict:
        try:
            rows = database.execute(state["sql"])
            return {"results": rows, "error": None}
        except Exception as exc:  # noqa: BLE001 -- we want to feed errors back to the LLM
            return {
                "results": [],
                "error": f"{type(exc).__name__}: {exc}",
                "retries": state.get("retries", 0) + 1,
            }

    return run_sql


def make_format_answer_node(llm: BaseChatModel) -> Callable[[AgentState], dict]:
    """Produce a node that formats the final NL answer (or an error message)."""

    system = SystemMessage(content=prompts.ANSWER_SYSTEM_PROMPT)

    def format_answer(state: AgentState) -> dict:
        if state.get("error") and state.get("retries", 0) >= MAX_RETRIES:
            user_text = prompts.ANSWER_ERROR_PROMPT.format(question=state["question"])
        else:
            user_text = prompts.ANSWER_USER_PROMPT.format(
                question=state["question"],
                sql=state.get("sql", ""),
                results=json.dumps(state.get("results", []), default=str),
            )
        response = llm.invoke([system, HumanMessage(content=user_text)])
        return {"answer": str(response.content).strip()}

    return format_answer


def should_retry(state: AgentState) -> str:
    """Routing function after `run_sql`.

    Returns the name of the next node: retry `generate_sql` on recoverable
    errors, otherwise proceed to `format_answer`.
    """
    if not state.get("error"):
        return "format_answer"
    if state.get("retries", 0) < MAX_RETRIES:
        return "generate_sql"
    return "format_answer"
