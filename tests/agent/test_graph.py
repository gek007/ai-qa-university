"""Graph e2e tests: mock LLM, real in-memory SQL execution."""

from __future__ import annotations

from agent.graph import build_graph
from agent.nodes import MAX_RETRIES
from database.db import Database

from .conftest import MockChatModel


def test_happy_path_end_to_end(db: Database) -> None:
    llm = MockChatModel(
        [
            "SELECT COUNT(*) AS n FROM students",
            "There are 20 students enrolled.",
        ]
    )
    graph = build_graph(db, llm=llm)

    state = graph.invoke({"question": "How many students are there?"})

    assert state["sql"] == "SELECT COUNT(*) AS n FROM students"
    assert state["results"] == [{"n": 20}]
    assert state["answer"] == "There are 20 students enrolled."
    assert state.get("error") is None


def test_retry_path_recovers_from_bad_sql(db: Database) -> None:
    llm = MockChatModel(
        [
            "SELECT nope FROM nowhere",
            "SELECT COUNT(*) AS n FROM students",
            "There are 20 students enrolled.",
        ]
    )
    graph = build_graph(db, llm=llm)

    state = graph.invoke({"question": "How many students are there?"})

    assert state["sql"] == "SELECT COUNT(*) AS n FROM students"
    assert state["results"] == [{"n": 20}]
    assert state["answer"] == "There are 20 students enrolled."
    assert state["retries"] == 1
    assert state.get("error") is None


def test_max_retries_routes_to_error_answer(db: Database) -> None:
    # `MAX_RETRIES` bad SQLs, then the final user-facing answer string.
    bad_sqls = ["SELECT nope FROM nowhere"] * MAX_RETRIES
    final_answer = "Sorry, I couldn't answer that question. Please rephrase."
    llm = MockChatModel([*bad_sqls, final_answer])
    graph = build_graph(db, llm=llm)

    state = graph.invoke({"question": "unanswerable"})

    assert state["retries"] == MAX_RETRIES
    assert state["error"] is not None
    assert state["answer"] == final_answer


def test_graph_handles_complex_join_question(db: Database) -> None:
    """Multi-table SQL against seeded data returns one aggregated row."""
    complex_sql = (
        "SELECT c.title AS course, AVG(e.grade) AS avg_grade "
        "FROM enrollments e "
        "JOIN course_offerings co ON co.id = e.offering_id "
        "JOIN courses c ON c.id = co.course_id "
        "WHERE e.grade IS NOT NULL "
        "GROUP BY c.title "
        "ORDER BY avg_grade DESC "
        "LIMIT 1"
    )
    llm = MockChatModel(
        [complex_sql, "The course with the highest average grade is ..."]
    )
    graph = build_graph(db, llm=llm)

    state = graph.invoke({"question": "Which course has the highest average grade?"})

    assert state.get("error") is None
    assert len(state["results"]) == 1
    assert "course" in state["results"][0]
    assert "avg_grade" in state["results"][0]


def test_graph_only_requires_question_in_input(db: Database) -> None:
    """Invoke with only `question` still produces `answer` downstream."""
    llm = MockChatModel(["SELECT 1 AS x", "The answer is 1."])
    graph = build_graph(db, llm=llm)

    state = graph.invoke({"question": "trivial"})

    assert state["answer"] == "The answer is 1."
