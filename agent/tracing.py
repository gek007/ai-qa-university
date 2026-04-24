"""LangSmith/LangChain env setup so traces export when an API key is present.

Reads `.env` and sets tracing flags; logs clearly when tracing stays off."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

DEFAULT_PROJECT = "university-qa"

logger = logging.getLogger(__name__)


def setup_tracing() -> bool:
    """Set LangSmith + legacy LangChain env from `LANGSMITH_API_KEY` or `LANGCHAIN_API_KEY`.

    Returns whether tracing is active (key found)."""
    load_dotenv(override=False)

    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        logger.warning(
            "LangSmith API key not set; tracing disabled. "
            "Set LANGSMITH_API_KEY or LANGCHAIN_API_KEY in .env to enable."
        )
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
    logger.info(
        "LangSmith tracing enabled: project=%r",
        os.environ["LANGSMITH_PROJECT"],
    )
    return True
