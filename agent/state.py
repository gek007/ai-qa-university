"""Shared state passed between LangGraph nodes."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """State carried through the QA graph.

    `total=False` means every field is optional on input -- we only require
    `question` to be present when invoking the graph; the rest is populated
    by nodes as they execute.
    """

    question: str
    sql: str
    results: list[dict[str, Any]]
    answer: str
    error: str | None
    retries: int
