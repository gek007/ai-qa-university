"""Agent tests: `MockChatModel` + seeded in-memory `Database` fixture."""

from __future__ import annotations

from typing import Any, Iterable

import pytest
from langchain_core.messages import AIMessage, BaseMessage

from database.db import Database
from database.populate_db import seed


class MockChatModel:
    """FIFO canned `AIMessage`s; `calls` captures each `invoke` for assertions."""

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
    """In-memory SQLite + `seed()` for graph integration tests."""
    
    database = Database("sqlite:///:memory:")
    seed(database)
    return database
