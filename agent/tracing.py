"""LangSmith/LangChain env setup so traces export when an API key is present.

Reads `.env` and sets tracing flags; logs clearly when tracing stays off."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from log_config import ENV_FILE

DEFAULT_PROJECT = "ai-qa-university"

logger = logging.getLogger(__name__)


def setup_tracing() -> bool:
    """Set LangSmith + legacy LangChain env from `LANGSMITH_API_KEY` or `LANGCHAIN_API_KEY`.

    Returns whether tracing is active (key found)."""
    load_dotenv(dotenv_path=ENV_FILE, override=False)

    api_key = os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")
    if not api_key:
        # For debugging: explicitly print .env path and current ENV vars for API keys (user has LANGSMITH_API_KEY in .env, check dotnev loading)
        logger.warning(
            "LangSmith API key not set; tracing disabled. "
            "Set LANGSMITH_API_KEY or LANGCHAIN_API_KEY in .env to enable. "
            f"Checked ENV_FILE={ENV_FILE!r}\n"
            f"LANGSMITH_API_KEY={os.environ.get('LANGSMITH_API_KEY')!r} "
            f"LANGCHAIN_API_KEY={os.environ.get('LANGCHAIN_API_KEY')!r}"
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
