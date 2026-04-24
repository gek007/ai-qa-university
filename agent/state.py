"""Typed dict for LangGraph `AgentState` (partial updates per node)."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """`total=False`: only `question` is required to invoke; nodes fill the rest."""

    question: str
    sql: str
    results: list[dict[str, Any]]
    answer: str
    error: str | None
    retries: int
