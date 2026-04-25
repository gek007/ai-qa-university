"""LangGraph node factories for the QA flow.

Each `make_*_node` returns a state-to-update callable with the LLM, schema, and
DB closed over so graph wiring and tests stay straightforward.
"""

from __future__ import annotations

import json
import logging
from typing import Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from agent import prompts
from agent.state import AgentState
from database.db import Database

logger = logging.getLogger(__name__)

# `run_sql` increments `retries` on failure; at this cap, `should_retry` sends
# `format_answer` down the user-facing error branch instead of `generate_sql`.
MAX_RETRIES = 2


def _clean_sql(text: str) -> str:
    """Return executable SQL: strip markdown fences and a trailing semicolon."""

    s = text.strip()
    if s.startswith("```"):
        lines = [ln for ln in s.splitlines() if not ln.strip().startswith("```")]
        s = "\n".join(lines).strip()
    if s.endswith(";"):
        s = s[:-1].rstrip()
    return s


def make_generate_sql_node(llm: BaseChatModel, schema: str) -> Callable[[AgentState], dict]:
    """Build a node that maps the question (and prior failure, if any) to SQL."""

    system = SystemMessage(content=prompts.SQL_SYSTEM_PROMPT.format(schema=schema))

    def generate_sql(state: AgentState) -> dict:
        """Emit `sql` and clear `error`; on retry, include last SQL and error in the user prompt."""

        previous_error = state.get("error")
        if previous_error:
            logger.warning(
                "Regenerating SQL after error (retries so far: %s): %s",
                state.get("retries", 0),
                previous_error[:200],
            )
            user_text = prompts.SQL_RETRY_USER_PROMPT.format(
                question=state["question"],
                previous_sql=state.get("sql", ""),
                error=previous_error,
            )
        else:
            logger.debug("generate_sql: question=%r", state["question"][:200])
            user_text = prompts.SQL_USER_PROMPT.format(question=state["question"])

        response = llm.invoke([system, HumanMessage(content=user_text)])
        sql = _clean_sql(str(response.content))
        logger.debug("generate_sql: produced %d char(s) of SQL", len(sql))
        return {"sql": sql, "error": None}

    return generate_sql


def make_run_sql_node(database: Database) -> Callable[[AgentState], dict]:
    """Build a node that executes `state['sql']` and tracks failures for routing."""

    def run_sql(state: AgentState) -> dict:
        """Execute SQL: rows on success, or empty results with `retries` + `error` (for LLM retry, not re-raised)."""

        try:
            rows = database.execute(state["sql"])
            return {"results": rows, "error": None}
        except Exception as exc:  # noqa: BLE001 — feed driver/DB failures into state for the LLM
            nxt = state.get("retries", 0) + 1
            logger.info(
                "run_sql: execution failed, retry may follow (attempt %d, max %d): %s: %s",
                nxt,
                MAX_RETRIES,
                type(exc).__name__,
                exc,
            )
            return {
                "results": [],
                "error": f"{type(exc).__name__}: {exc}",
                "retries": nxt,
            }

    return run_sql


# The reason the node factory function (`make_format_answer_node`) contains an inner function (`format_answer`)
# is to "capture" the arguments or state you want to bake into the node. In this pattern:
#   - The outer function (`make_format_answer_node`) takes configuration or dependencies (like the LLM to use).
#   - It then defines and returns the "node" function (`format_answer`) that will be called by the graph engine.
#   - This allows each node you create to be bound to specific settings (like a particular LLM or fixed prompt).
# Without this pattern, it would be more awkward to pass custom dependencies (like the LLM, prompt, schema, etc)
# into each node function when building the graph.

def make_format_answer_node(llm: BaseChatModel) -> Callable[[AgentState], dict]:
    """Builds and returns a node function that produces the final answer string or, after repeated SQL failure, a terminal error message.

    Why is there a function inside a function? This is known as the factory pattern or closure pattern.
    The outer function (`make_format_answer_node`) accepts dependencies or configuration (here, the language model to use).
    It then creates (defines) an inner function (`format_answer`) that performs the actual node logic,
    with automatic access to the variables from the outer function's scope (like `llm`, `system`).

    This means when you call `make_format_answer_node(llm)` you get back a ready-to-use function,
    already tied to the `llm` you passed in. The LangGraph graph expects nodes as pure functions of state,
    but factory functions allow us to supply dependencies when the graph is assembled—clean, safe, and testable.
    """

    system = SystemMessage(content=prompts.ANSWER_SYSTEM_PROMPT)

    def format_answer(state: AgentState) -> dict:
        """After max SQL failures, use the error-style prompt; otherwise, generate the answer using results."""
        if state.get("error") and state.get("retries", 0) >= MAX_RETRIES:
            logger.warning(
                "format_answer: using user-facing error path (after %d failed SQL attempt(s))",
                MAX_RETRIES,
            )
            user_text = prompts.ANSWER_ERROR_PROMPT.format(question=state["question"])
        else:
            user_text = prompts.ANSWER_USER_PROMPT.format(
                question=state["question"],
                sql=state.get("sql", ""),
                results=json.dumps(state.get("results", []), default=str),
            )
        response = llm.invoke([system, HumanMessage(content=user_text)])
        out = str(response.content).strip()
        logger.debug("format_answer: %d char(s) of answer", len(out))
        return {"answer": out}

    return format_answer


def should_retry(state: AgentState) -> str:
    """Graph router after `run_sql`: next node name (`format_answer` or `generate_sql`)."""
    
    if not state.get("error"):
        return "format_answer"
    if state.get("retries", 0) < MAX_RETRIES:
        logger.debug("should_retry: route to generate_sql (retry %d/%d)", state.get("retries", 0), MAX_RETRIES)
        return "generate_sql"
    logger.warning("should_retry: max retries reached; giving up on SQL and routing to format_answer")
    return "format_answer"
