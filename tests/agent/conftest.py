"""Shared fixtures and a minimal mock chat model for agent tests."""

from __future__ import annotations

from typing import Any, Iterable

import pytest
from langchain_core.messages import AIMessage, BaseMessage

from database.db import Database
from database.seed import seed


class MockChatModel:
    """Tiny stand-in for a LangChain chat model.

    Returns canned responses in order and records every call it receives so
    tests can assert on the exact prompts reaching the LLM.
    """

    def __init__(self, responses: Iterable[str]) -> None:
        self._responses: list[str] = list(responses)
        self.calls: list[list[BaseMessage]] = []

    def invoke(self, messages: list[BaseMessage], **_: Any) -> AIMessage:
        self.calls.append(list(messages))
        if not self._responses:
            raise RuntimeError("MockChatModel: no more canned responses left")
        return AIMessage(content=self._responses.pop(0))


@pytest.fixture()
def db() -> Database:
    """An in-memory SQLite DB seeded with deterministic sample data."""
    database = Database("sqlite:///:memory:")
    seed(database)
    return database
