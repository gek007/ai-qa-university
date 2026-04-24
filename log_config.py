"""Root logging setup for app, seed scripts, and CLI.

Env-driven console and optional rotating file handlers; see `.env.example`."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent


def _truthy(name: str, default: str = "false") -> bool:
    """True if the env var reads as 1/true/yes/on (case-insensitive)."""
    v = (os.getenv(name) or default).strip().lower()
    return v in ("1", "true", "yes", "on")


def configure(level: int | str | None = None) -> None:
    """Attach formatters/handlers to the root logger once; no-op if already configured."""
    if logging.getLogger().handlers:
        return
    load_dotenv(override=False)
    lv = level or os.getenv("LOG_LEVEL", "INFO")
    if isinstance(lv, str):
        lv = getattr(logging, lv.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%H:%M:%S"
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    root = logging.getLogger()
    root.setLevel(lv)

    console_on = _truthy("LOG_TO_CONSOLE", "true")
    file_on = _truthy("LOG_TO_FILE", "false")

    stream_name = (os.getenv("LOG_STREAM") or "stdout").strip().lower()
    stream = sys.stdout if stream_name in ("stdout", "out", "1") else sys.stderr

    if console_on:
        ch = logging.StreamHandler(stream)
        ch.setFormatter(formatter)
        root.addHandler(ch)

    if file_on:
        rel = os.getenv("LOG_FILE", "logs/ai-qa-university.log")
        log_path = Path(rel)
        if not log_path.is_absolute():
            log_path = (PROJECT_ROOT / rel).resolve()
        else:
            log_path = log_path.resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        max_bytes = int(os.getenv("LOG_MAX_BYTES", str(1_048_576)))  # default 1 MiB
        backup = int(os.getenv("LOG_BACKUP_COUNT", "10"))
        fh = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup,
            encoding="utf-8",
        )
        fh.setFormatter(formatter)
        root.addHandler(fh)
        _boot = logging.getLogger("log_config")
        _boot.info(
            "File logging: %s (max %d bytes, %d backup file(s))",
            log_path,
            max_bytes,
            backup,
        )

    if not root.handlers:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        root.addHandler(ch)
        logging.getLogger("log_config").warning(
            "No LOG_TO_CONSOLE/LOG_TO_FILE enabled; using stdout as fallback"
        )
