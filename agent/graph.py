"""Build the QA LangGraph: generate_sql → run_sql → (retry or) format_answer → END.

Schema is read once at compile time and baked into the SQL system prompt."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import logging
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    MAX_RETRIES,
    make_format_answer_node,
    make_generate_sql_node,
    make_run_sql_node,
    should_retry,
)
from agent.state import AgentState
from database.db import Database

logger = logging.getLogger(__name__)


def _default_llm() -> BaseChatModel:
    """`ChatOpenAI` at temperature 0; used when `build_graph` is called without an `llm`."""

    return ChatOpenAI(model="gpt-4o", temperature=0)


def build_graph(database: Database, llm: Optional[BaseChatModel] = None):
    """Compile the graph: generate SQL, run it, maybe retry, then format the answer.

    Uses `llm` if given, else `_default_llm()`. Call `.invoke` with a `question` and optional state."""
    chat_model = llm if llm is not None else _default_llm()
    schema = database.get_schema()

    builder = StateGraph(AgentState)
    builder.add_node("generate_sql", make_generate_sql_node(chat_model, schema))
    builder.add_node("run_sql", make_run_sql_node(database))
    builder.add_node("format_answer", make_format_answer_node(chat_model))

    builder.add_edge(START, "generate_sql")
    builder.add_edge("generate_sql", "run_sql")
    builder.add_conditional_edges(
        "run_sql",
        should_retry,
        {"generate_sql": "generate_sql",
         "format_answer": "format_answer"},
    )
    builder.add_edge("format_answer", END)

    compiled = builder.compile()
    logger.debug(
        "LangGraph compiled: generate_sql -> run_sql -> format_answer (SQL retries < %d)",
        MAX_RETRIES,
    )
    return compiled
