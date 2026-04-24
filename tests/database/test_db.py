"""`Database`: schema text, `execute` guards, seed data, example queries."""

from __future__ import annotations

import pytest

from database.db import Database
from database.populate_db import COURSES, OFFERINGS, STUDENTS, TEACHERS, seed


@pytest.fixture()
def db() -> Database:
    """In-memory DB + `seed()` for query tests."""
    
    database = Database("sqlite:///:memory:")
    seed(database)
    return database


def test_schema_lists_all_tables(db: Database) -> None:
    schema = db.get_schema()
    for table in ("teachers", "students", "courses", "course_offerings", "enrollments"):
        assert f"Table {table}" in schema
    assert "FK:" in schema


def test_seeded_entity_counts(db: Database) -> None:
    assert db.execute("SELECT COUNT(*) AS n FROM teachers")[0]["n"] == len(TEACHERS)
    assert db.execute("SELECT COUNT(*) AS n FROM students")[0]["n"] == len(STUDENTS)
    assert db.execute("SELECT COUNT(*) AS n FROM courses")[0]["n"] == len(COURSES)
    assert (
        db.execute("SELECT COUNT(*) AS n FROM course_offerings")[0]["n"]
        == len(OFFERINGS)
    )
    enrollments_count = db.execute("SELECT COUNT(*) AS n FROM enrollments")[0]["n"]
    assert enrollments_count == len(STUDENTS) * 3


def test_join_student_offering_course(db: Database) -> None:
    rows = db.execute(
        """
        SELECT s.name AS student, c.title AS course, co.semester AS semester
        FROM enrollments e
        JOIN students s         ON s.id = e.student_id
        JOIN course_offerings co ON co.id = e.offering_id
        JOIN courses c          ON c.id = co.course_id
        ORDER BY student, course, semester
        """
    )
    assert len(rows) == len(STUDENTS) * 3
    assert {"student", "course", "semester"} == set(rows[0].keys())


def test_avg_grade_per_course(db: Database) -> None:
    rows = db.execute(
        """
        SELECT c.title AS course, AVG(e.grade) AS avg_grade, COUNT(e.grade) AS n
        FROM enrollments e
        JOIN course_offerings co ON co.id = e.offering_id
        JOIN courses c           ON c.id = co.course_id
        WHERE e.grade IS NOT NULL
        GROUP BY c.title
        ORDER BY c.title
        """
    )
    assert len(rows) >= 1
    for row in rows:
        assert row["n"] >= 1
        assert 0 <= row["avg_grade"] <= 100


def test_offering_count_per_teacher(db: Database) -> None:
    rows = db.execute(
        """
        SELECT t.name AS teacher, COUNT(co.id) AS offerings
        FROM teachers t
        LEFT JOIN course_offerings co ON co.teacher_id = t.id
        GROUP BY t.name
        ORDER BY offerings DESC
        """
    )
    assert len(rows) == len(TEACHERS)
    assert sum(r["offerings"] for r in rows) == len(OFFERINGS)


def test_filter_by_semester(db: Database) -> None:
    rows = db.execute(
        "SELECT semester, COUNT(*) AS n FROM course_offerings "
        "GROUP BY semester ORDER BY semester"
    )
    semesters = {r["semester"] for r in rows}
    assert semesters == {"Fall 2024", "Spring 2025", "Fall 2025"}


def test_execute_rejects_non_select(db: Database) -> None:
    for stmt in (
        "INSERT INTO students (name) VALUES ('Hacker')",
        "UPDATE students SET name='x' WHERE id=1",
        "DELETE FROM students WHERE id=1",
        "DROP TABLE students",
    ):
        with pytest.raises(ValueError):
            db.execute(stmt)


def test_execute_rejects_multiple_statements(db: Database) -> None:
    with pytest.raises(ValueError):
        db.execute("SELECT 1; SELECT 2")


def test_execute_allows_cte(db: Database) -> None:
    rows = db.execute(
        "WITH t AS (SELECT COUNT(*) AS n FROM students) SELECT n FROM t"
    )
    assert rows == [{"n": len(STUDENTS)}]


def test_execute_returns_list_of_dicts(db: Database) -> None:
    rows = db.execute("SELECT id, name FROM teachers ORDER BY id LIMIT 2")
    assert isinstance(rows, list)
    assert all(isinstance(r, dict) for r in rows)
    assert set(rows[0].keys()) == {"id", "name"}
