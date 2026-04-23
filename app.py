"""Gradio front-end for the University QA agent.

Run:
    python app.py

Opens a local web UI at http://127.0.0.1:7860 where you can ask
natural-language questions about the university database.

On first run the database at `data/university.db` is created and seeded
automatically. LangSmith tracing is enabled when `LANGSMITH_API_KEY`
(or `LANGCHAIN_API_KEY`) is present in `.env`.
"""

from __future__ import annotations

import gradio as gr
from langchain_openai import ChatOpenAI
from sqlalchemy import select

from agent.graph import build_graph
from agent.tracing import setup_tracing
from database.db import DEFAULT_URL, Database
from database.models import Teacher
from database.seed import seed

EXAMPLE_QUESTIONS = [
    "How many students are there in total?",
    "What is the average grade per course?",
    "Which teacher teaches the most courses in Fall 2025?",
    "List students enrolled in Database Systems in Spring 2025.",
    "Who are the top 3 students by average grade?",
]


def _ensure_seeded(database: Database) -> None:
    """Create the schema and seed sample data on first launch."""
    database.create_schema()
    with database.session() as s:
        already_seeded = s.execute(select(Teacher).limit(1)).first() is not None
    if not already_seeded:
        seed(database, reset=False)


def _build_runtime() -> tuple[object, bool]:
    """Wire tracing, database, LLM, and graph once at startup."""
    tracing_on = setup_tracing()
    database = Database(DEFAULT_URL)
    _ensure_seeded(database)
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    graph = build_graph(database, llm=llm)
    return graph, tracing_on


GRAPH, TRACING_ON = _build_runtime()


def ask(question: str) -> tuple[str, str, list]:
    """Invoke the graph for a single question and unpack its final state."""
    if not question or not question.strip():
        return "", "", []
    state = GRAPH.invoke({"question": question.strip()})
    return (
        state.get("answer", ""),
        state.get("sql", ""),
        state.get("results", []),
    )


def _build_ui() -> gr.Blocks:
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
    _build_ui().launch()
