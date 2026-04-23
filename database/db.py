"""Database facade.

Exposes a thin `Database` wrapper around a SQLAlchemy engine. The agent only
ever calls `get_schema()` and `execute()` -- swapping the underlying engine
(SQLite, PostgreSQL, ...) is a one-line change to the connection URL.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from database.models import Base

DEFAULT_URL = "sqlite:///university.db"

_SELECT_ONLY_RE = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


class Database:
    """Minimal DB-agnostic facade used by the QA agent."""

    def __init__(self, url: str = DEFAULT_URL) -> None:
        self.url = url
        self.engine: Engine = create_engine(url, future=True)
        self._SessionFactory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        """Create all tables defined on the ORM metadata."""
        Base.metadata.create_all(self.engine)

    def drop_schema(self) -> None:
        """Drop all tables (primarily used in tests)."""
        Base.metadata.drop_all(self.engine)

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
        for table_name in inspector.get_table_names():
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
            raise ValueError("Only SELECT / WITH statements are allowed.")
        if ";" in sql.rstrip().rstrip(";"):
            raise ValueError("Multiple statements are not allowed.")

        with self.engine.connect() as conn:
            result = conn.execute(text(sql))
            return [dict(row) for row in result.mappings().all()]
