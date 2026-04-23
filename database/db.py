"""Database facade.

Exposes a thin `Database` wrapper around a SQLAlchemy engine. The agent only
ever calls `get_schema()` and `execute()` -- swapping the underlying engine
(SQLite, PostgreSQL, ...) is a one-line change to the connection URL.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from database.models import Base

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def _default_url() -> str:
    """Resolve the default DB URL.

    Priority:
        1. `DATABASE_URL` env var, if set.
        2. `sqlite:///<project>/data/university.db` (creates `data/` on demand).
    """
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        logger.debug("DATABASE_URL set from environment")
        return env_url
    DATA_DIR.mkdir(exist_ok=True)
    path = (DATA_DIR / "university.db").as_posix()
    logger.debug("Using default sqlite database at data/university.db")
    return f"sqlite:///{path}"


DEFAULT_URL = _default_url()

_SELECT_ONLY_RE = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def _log_engine_target(url: str) -> str:
    """Return a log-safe description of the connection (no credentials)."""
    if url.startswith("sqlite:"):
        return url
    parts = urlsplit(url)
    host = parts.hostname or "?"
    return f"{parts.scheme}://{host}{parts.path or ''}"


class Database:
    """Minimal DB-agnostic facade used by the QA agent."""

    def __init__(self, url: str = DEFAULT_URL) -> None:
        self.url = url
        self.engine: Engine = create_engine(url, future=True)
        self._SessionFactory = sessionmaker(bind=self.engine, expire_on_commit=False)
        logger.debug("Database engine ready: %s", _log_engine_target(url))

    def create_schema(self) -> None:
        """Create all tables defined on the ORM metadata."""
        Base.metadata.create_all(self.engine)
        logger.debug("Schema created (all tables)")

    def drop_schema(self) -> None:
        """Drop all tables (primarily used in tests)."""
        Base.metadata.drop_all(self.engine)
        logger.warning("All tables dropped (drop_schema)")

    def session(self) -> Session:
        """Open a new ORM session. Caller is responsible for closing it."""
        return self._SessionFactory()

    def get_schema(self) -> str:
        """Return a human- and LLM-readable description of the current schema.

        Uses SQLAlchemy's dialect-agnostic Inspector so the same code works
        across SQLite, PostgreSQL, MySQL, etc.
        """
        inspector = inspect(self.engine)
        lines: list[str] = []
        names = inspector.get_table_names()
        logger.debug("Introspected schema: %d table(s)", len(names))
        for table_name in names:
            lines.append(f"Table {table_name}:")
            for col in inspector.get_columns(table_name):
                nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
                lines.append(f"  - {col['name']} ({col['type']}) {nullable}")
            fks = inspector.get_foreign_keys(table_name)
            for fk in fks:
                cols = ", ".join(fk["constrained_columns"])
                ref_table = fk["referred_table"]
                ref_cols = ", ".join(fk["referred_columns"])
                lines.append(f"  FK: {cols} -> {ref_table}({ref_cols})")
            lines.append("")
        return "\n".join(lines).strip()

    def execute(self, sql: str) -> list[dict[str, Any]]:
        """Execute a read-only SQL statement and return rows as dicts.

        Only SELECT / WITH (CTE) statements are allowed -- the agent should
        never mutate data. A single statement per call is enforced.
        """
        if not _SELECT_ONLY_RE.match(sql):
            logger.warning("execute blocked: not a SELECT / WITH: %r", sql[:200])
            raise ValueError("Only SELECT / WITH statements are allowed.")
        if ";" in sql.rstrip().rstrip(";"):
            logger.warning("execute blocked: multiple statements not allowed")
            raise ValueError("Multiple statements are not allowed.")

        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = [dict(row) for row in result.mappings().all()]
        logger.debug("Query returned %d row(s)", len(rows))
        return rows
