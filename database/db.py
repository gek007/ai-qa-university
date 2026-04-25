"""Thin SQLAlchemy facade: `get_schema` + read-only `execute` for the agent.

Swap `DATABASE_URL` to change backend without touching call sites."""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from database.models import Base

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def _default_url() -> str:
    """`DATABASE_URL` if set, else project `data/university.db` (ensures `data/` exists)."""

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
    """String for debug logs: full `sqlite:…` URL, else `scheme://host/path` without credentials."""

    if url.startswith("sqlite:"):
        return url

    parts = urlsplit(url)
    host = parts.hostname or "?"
    return f"{parts.scheme}://{host}{parts.path or ''}"


class Database:
    """Session factory, schema DDL, schema text for prompts, and guarded SELECT execution."""

    def __init__(self, url: str = DEFAULT_URL) -> None:
        self.url = url
        self.engine: Engine = create_engine(url, future=True)
        self._SessionFactory = sessionmaker(bind=self.engine, expire_on_commit=False)
        logger.debug("Database engine ready: %s", _log_engine_target(url))

    def create_schema(self) -> None:
        """`create_all` from ORM metadata."""

        Base.metadata.create_all(self.engine)
        logger.debug("Schema created (all tables)")

    def drop_schema(self) -> None:
        """`drop_all`; typical caller is tests or `seed(..., reset=True)`."""

        Base.metadata.drop_all(self.engine)
        logger.warning("All tables dropped (drop_schema)")

    def session(self) -> Session:
        """New SQLAlchemy session; caller closes or uses as context manager."""

        return self._SessionFactory()

    def get_schema(self) -> str:
        """Table/column/FK text via the Inspector (works across supported dialects)."""

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
        """Run a single SELECT or WITH; returns row dicts. Rejects DML/DDL and multiple statements."""

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


if __name__ == "__main__":
    from database.models import Course, Student, Teacher

    db_url = os.getenv("DB_URL", "sqlite:///:memory:")
    db = Database(db_url)
    db.create_schema()

    with db.session() as session:
        session.add_all(
            [
                Teacher(name="Ada Lovelace"),
                Student(name="Alan Turing"),
                Course(title="LLM and AI"),
            ]
        )
        session.commit()

    print("--- Database Schema ---")
    print(db.get_schema())
    print("-----------------------")

    try:
        print("Teachers:", db.execute("SELECT * FROM teachers"))
    except Exception as e:
        print("Error running SELECT:", e)

    try:
        db.execute("DELETE FROM teachers WHERE id=0")
    except Exception as e:
        print("Properly blocked DELETE statement:", e)

    try:
        db.execute("SELECT * FROM students WHERE id=0")
    except Exception as e:
        print("Properly blocked multiple statements:", e)

    try:
        db.execute("SELECT * FROM Courses")
    except Exception as e:
        print("Properly blocked SELECT statement:", e)
