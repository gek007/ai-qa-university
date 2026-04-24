"""Gradio UI for the university QA agent (`python app.py` → http://127.0.0.1:7860).

Seeds `data/university.db` on first run. LangSmith follows `.env` when
`LANGSMITH_API_KEY` or `LANGCHAIN_API_KEY` is set."""

from __future__ import annotations

import logging
import os

import gradio as gr
from langchain_openai import ChatOpenAI
from sqlalchemy import select

from agent.graph import build_graph
from agent.tracing import setup_tracing
from database.db import DEFAULT_URL, Database
from database.models import Teacher
from database.populate_db import seed
from log_config import configure

logger = logging.getLogger(__name__)

EXAMPLE_QUESTIONS = [
    "How many students are there in total?",
    "What is the average grade per course?",
    "Which teacher teaches the most courses in Fall 2025?",
    "List students enrolled in Database Systems in Spring 2025.",
    "Who are the top 3 students by average grade?",
]


def _ensure_seeded(database: Database) -> None:
    """Ensure tables exist; seed if empty (idempotent for non-empty DBs)."""

    database.create_schema()
    with database.session() as s:
        already_seeded = s.execute(select(Teacher).limit(1)).first() is not None
    if not already_seeded:
        logger.info("No teachers found; running initial populate_db (reset=False)")
        seed(database, reset=False)
    else:
        logger.info("Database already has data; skipping seed")


def _build_runtime() -> tuple[object, bool]:
    """One-shot init: logging, optional LangSmith, DB, LLM, compiled graph. Returns (graph, tracing_on)."""

    configure()
    tracing_on = setup_tracing()
    database = Database(DEFAULT_URL)
    _ensure_seeded(database)
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    graph = build_graph(database, llm=llm)
    return graph, tracing_on


GRAPH, TRACING_ON = _build_runtime()


def ask(question: str) -> tuple[str, str, list]:
    """Run the graph; return (answer, sql, results). Empty input → three empties. Re-raises on invoke failure."""

    if not question or not question.strip():
        return "", "", []
    q = question.strip()
    logger.info("User question: %r", q[:500])
    try:
        state = GRAPH.invoke({"question": q})
    except Exception:
        logger.exception("Graph invocation failed")
        raise
    return (
        state.get("answer", ""),
        state.get("sql", ""),
        state.get("results", []),
    )


def _build_ui() -> gr.Blocks:
    """Gradio layout: question in, answer + SQL + JSON out, examples, tracing hint."""
    
    with gr.Blocks(title="University QA Agent") as demo:
        gr.Markdown(
            "# University QA Agent\n"
            "Ask natural-language questions about the university database."
        )
        tracing_badge = (
            "LangSmith tracing: **enabled**"
            if TRACING_ON
            else "LangSmith tracing: _disabled_ (no `LANGSMITH_API_KEY` in `.env`)"
        )
        gr.Markdown(tracing_badge)

        with gr.Row():
            question = gr.Textbox(
                label="Question",
                placeholder="How many students are there?",
                scale=4,
                autofocus=True,
            )
            submit = gr.Button("Ask", variant="primary", scale=1)

        answer = gr.Textbox(label="Answer", lines=3)
        with gr.Accordion("Details (SQL + raw results)", open=False):
            sql = gr.Code(label="Generated SQL", language="sql")
            results = gr.JSON(label="Raw results")

        outputs = [answer, sql, results]
        submit.click(ask, inputs=question, outputs=outputs)
        question.submit(ask, inputs=question, outputs=outputs)

        gr.Examples(
            examples=EXAMPLE_QUESTIONS,
            inputs=question,
            label="Example questions",
        )

    return demo


if __name__ == "__main__":
    logger.info("Starting Gradio UI (OpenAI model: gpt-4o, LOG_LEVEL=%s)", os.getenv("LOG_LEVEL", "INFO"))
    _build_ui().launch()
