# Architecture — University QA Agent

## Overview

NL questions over a relational university DB: joins, filters, and aggregations are turned into SQL, executed behind guards, and summarized in plain language.

Goals:

* **DB-agnostic** — one facade; swap the URL, keep the graph.
* **Observable** — LangSmith traces the full run when configured.
* **Modular** — ORM, prompts, and LangGraph nodes are separate.
* **Multi-step** — LangGraph coordinates SQL → execute → (retry) → answer.

---

## High-Level Flow

```
User Question
      ↓
LangGraph
  generate_sql   (LLM: question + schema → SQL)
  run_sql        (read-only execute)
  format_answer  (LLM: rows → NL, or user-facing error after cap)
      ↓
Answer, SQL, raw rows (UI)
      ↓
LangSmith (optional)
```

---

## LangGraph

Compiled graph: `generate_sql` → `run_sql` → `should_retry` → `generate_sql` or `format_answer` → END.

```
generate_sql → run_sql → should_retry
                           ├ no error     → format_answer
                           ├ error, retries < MAX_RETRIES (2) → generate_sql
                           └ else         → format_answer  (error explanation)
```

* Failed execution strings go back into the next SQL prompt so the model can correct.
* After enough failed runs (`retries` ≥ `MAX_RETRIES`), `format_answer` uses the “couldn’t answer” path instead of result-grounded text.

---

## Components

### 1. Database (`database/`)

**Does:** ORM models, `get_schema()` for the LLM, `execute()` for read-only queries.

**Surface:**

```python
db.get_schema()  # str: tables, columns, FKs
db.execute(sql)  # list[dict]; SELECT/WITH only, single statement
```

The app never hard-codes table names for reasoning; it consumes whatever `get_schema()` returns, so the same agent code can target another schema or engine if the URL and models match.

### 2. Agent (`agent/`)

**State (`AgentState`, partial):** `question`, `sql`, `results`, `answer`, `error`, `retries`.

**Nodes:**

| Node | Role |
|------|------|
| `generate_sql` | First shot or retry with prior SQL + DB error in the user message |
| `run_sql` | `execute` + on failure: set `error`, bump `retries` |
| `format_answer` | Normal answer from `results`, or safe messaging when retries exhausted |
| `should_retry` (router) | After `run_sql`, returns next node name |

### 3. Prompts (`agent/prompts.py`)

All LLM strings live here so tuning does not require node changes.

### 4. Tracing

LangChain/LangGraph emit to **LangSmith** when `LANGSMITH_API_KEY` or `LANGCHAIN_API_KEY` is set. Traces include steps, prompts, model output, SQL, and tool/DB outcomes—useful for debugging and demos.

---

## Errors and Retries

* DB and validation errors from `execute` are **state**, not raised past the node (broad catch so any driver message reaches the next SQL prompt).
* **Retry budget:** `MAX_RETRIES` in `agent/nodes.py` (currently 2) gates how many times `should_retry` sends execution back to `generate_sql` before the terminal error path in `format_answer`.
* Empty results are valid: the answer model is instructed to state that clearly.

---

## DB-Agnostic Split

* **Data:** schema DDL, `get_schema` text, `execute` policy (SELECT-only, one statement).
* **Agent:** question → SQL → rows → natural language, independent of a specific DSN beyond the facade.

---

## Tests

| Layer | Focus |
|-------|--------|
| `tests/database/` | Schema text, `execute` guards, seeded joins/aggregations |
| `tests/agent/test_nodes.py` | `_clean_sql`, router, per-node behavior |
| `tests/agent/test_graph.py` | Full graph, mock LLM + real in-memory SQL |

In-memory SQLite and a canned `MockChatModel` avoid network calls.

---

## Production (extensions)

* **Reliability:** LLM timeouts, retries and backoff on API errors.
* **Scale:** e.g. PostgreSQL, app server (e.g. FastAPI), long-lived compiled graph instance.
* **Security:** keep read-only `execute` rules, cap rows/latency, auth on any public API.
* **Ops / cost:** LangSmith or other APM, alert on error/retry rates; cache or smaller models only where product allows.

---

## Summary

Favor **clear boundaries** (DB vs prompts vs graph), **traceability** in LangSmith, and a **small** graph: one retry loop, explicit state, and a single place to change how SQL is allowed to run.
