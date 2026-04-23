"""LangSmith tracing setup.

LangGraph + LangChain auto-export traces to LangSmith when these env vars
are set. This module simply loads `.env` (if present) and verifies the
required variables so problems fail loudly at startup.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

DEFAULT_PROJECT = "university-qa"


def setup_tracing() -> bool:
    """Load `.env` and enable LangSmith tracing if an API key is configured.

    Supports both the new `LANGSMITH_*` env names and the legacy
    `LANGCHAIN_*` names, so users with either convention work out of the box.

    Returns:
        True if tracing is enabled (API key present), False otherwise.
    """
    load_dotenv(override=False)

    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        return False

    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGSMITH_API_KEY", api_key)
    os.environ.setdefault("LANGCHAIN_API_KEY", api_key)
    os.environ.setdefault(
        "LANGSMITH_PROJECT",
        os.getenv("LANGCHAIN_PROJECT", DEFAULT_PROJECT),
    )
    os.environ.setdefault("LANGCHAIN_PROJECT", os.environ["LANGSMITH_PROJECT"])
    return True
