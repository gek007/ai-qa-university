"""Tests for LangSmith tracing setup.

`setup_tracing` must fail loudly only when explicitly misconfigured; otherwise
it simply no-ops when no API key is present.
"""

from __future__ import annotations

import pytest

from agent.tracing import DEFAULT_PROJECT, setup_tracing


_ENV_VARS = (
    "LANGSMITH_API_KEY",
    "LANGCHAIN_API_KEY",
    "LANGSMITH_TRACING",
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_PROJECT",
    "LANGCHAIN_PROJECT",
)


@pytest.fixture(autouse=True)
def _clean_tracing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_setup_tracing_returns_false_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("agent.tracing.load_dotenv", lambda **_: False)

    assert setup_tracing() is False


def test_setup_tracing_enables_both_env_conventions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.setattr("agent.tracing.load_dotenv", lambda **_: False)

    assert setup_tracing() is True

    import os

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "test-key"
    assert os.environ["LANGCHAIN_API_KEY"] == "test-key"
    assert os.environ["LANGSMITH_PROJECT"] == DEFAULT_PROJECT
    assert os.environ["LANGCHAIN_PROJECT"] == DEFAULT_PROJECT


def test_setup_tracing_accepts_legacy_langchain_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGCHAIN_API_KEY", "legacy-key")
    monkeypatch.setattr("agent.tracing.load_dotenv", lambda **_: False)

    assert setup_tracing() is True

    import os

    assert os.environ["LANGSMITH_API_KEY"] == "legacy-key"
    assert os.environ["LANGCHAIN_API_KEY"] == "legacy-key"


def test_setup_tracing_respects_custom_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "k")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "my-custom-project")
    monkeypatch.setattr("agent.tracing.load_dotenv", lambda **_: False)

    setup_tracing()

    import os

    assert os.environ["LANGSMITH_PROJECT"] == "my-custom-project"
    assert os.environ["LANGCHAIN_PROJECT"] == "my-custom-project"
