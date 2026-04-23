"""Compile the LangGraph QA graph.

The graph is intentionally small:

    START -> generate_sql -> run_sql --(ok)--> format_answer -> END
                  ^                  |
                  |--(error, retry)--+

Schema is fetched once at build time and embedded into the SQL prompt.
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.language_models import BaseChatModel
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
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model="gpt-4o", temperature=0)


def build_graph(database: Database, llm: Optional[BaseChatModel] = None):
    """Build and compile the QA LangGraph.

    Args:
        database: the DB facade the agent will query.
        llm: a chat model (defaults to `ChatOpenAI(model="gpt-4o")`).

    Returns:
        A compiled LangGraph ready to `.invoke({"question": ...})`.
    """
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
        {"generate_sql": "generate_sql", "format_answer": "format_answer"},
    )
    builder.add_edge("format_answer", END)

    compiled = builder.compile()
    logger.debug(
        "LangGraph compiled: generate_sql -> run_sql -> format_answer (SQL retries < %d)",
        MAX_RETRIES,
    )
    return compiled
