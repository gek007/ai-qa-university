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
# Always load this file — bare ``load_dotenv()`` only searches ``os.getcwd()`` (often wrong in IDEs).
ENV_FILE = PROJECT_ROOT / ".env"

_CONFIGURED = False


def _truthy(name: str, default: str = "false") -> bool:
    """True if the env var reads as 1/true/yes/on (case-insensitive)."""

    v = (os.getenv(name) or default).strip().lower()
    return v in ("1", "true", "yes", "on")


def _root_has_stream_handler(root: logging.Logger) -> bool:
    """True if root already has a console/stream handler (e.g. from an imported library)."""

    return any(isinstance(h, logging.StreamHandler) for h in root.handlers)


def _root_has_file_handler(root: logging.Logger, path: Path) -> bool:
    """True if a RotatingFileHandler already targets this path."""

    want = path.resolve()
    for h in root.handlers:
        if isinstance(h, RotatingFileHandler):
            try:
                if Path(h.baseFilename).resolve() == want:
                    return True
            except OSError:
                continue
    return False


def configure(level: int | str | None = None) -> None:
    """Attach formatters/handlers to the root logger once per process."""

    global _CONFIGURED
    load_dotenv(dotenv_path=ENV_FILE, override=False)
    if _CONFIGURED:
        return

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
    added_console = False
    added_file = False

    stream_name = (os.getenv("LOG_STREAM") or "stdout").strip().lower()
    stream = sys.stdout if stream_name in ("stdout", "out", "1") else sys.stderr

    if console_on and not _root_has_stream_handler(root):
        ch = logging.StreamHandler(stream)
        ch.setFormatter(formatter)
        root.addHandler(ch)
        added_console = True

    if file_on:
        rel = os.getenv("LOG_FILE", "logs/ai-qa-university.log")
        log_path = Path(rel)
        if not log_path.is_absolute():
            log_path = (PROJECT_ROOT / rel).resolve()
        else:
            log_path = log_path.resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if not _root_has_file_handler(root, log_path):
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
            added_file = True
            try:
                fh.flush()
            except OSError:
                pass

    if not root.handlers:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        root.addHandler(ch)
        logging.getLogger("log_config").warning(
            "No LOG_TO_CONSOLE/LOG_TO_FILE enabled; using stdout as fallback"
        )

    boot = logging.getLogger("log_config")
    boot.info(
        "Logging ready (env from %s): console=%s file=%s LOG_TO_FILE=%r",
        ENV_FILE,
        added_console or _root_has_stream_handler(root),
        added_file,
        os.getenv("LOG_TO_FILE"),
    )

    _CONFIGURED = True
