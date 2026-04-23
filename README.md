# University QA Agent


![1776985152316](image/README/1776985152316.png)

![1776985236997](image/README/1776985236997.png)



A natural-language question-answering system over a university database, built with **LangGraph**, **SQLAlchemy**, **OpenAI GPT-4o**, and a **Gradio** UI.

Ask questions like:

- *"What is the average grade per course?"*
- *"Which teacher teaches the most courses in Fall 2025?"*
- *"List the top 3 students by average grade."*

Every run is automatically traced to **LangSmith**, giving you full visibility from user question → SQL → DB results → final answer.

---

## Architecture overview

```
User question (Gradio)
       │
       ▼
 agent/graph.py (LangGraph)
  ├── generate_sql   ← GPT-4o translates NL to SQL using the schema
  ├── run_sql        ← SQLAlchemy executes the SQL; errors feed back as retry context
  └── format_answer  ← GPT-4o writes a natural-language answer from the raw rows
       │
       ▼
  Answer + SQL + raw results → Gradio UI + LangSmith trace
```

### Project layout

```
ai-qa-university/
├── database/
│   ├── models.py     # SQLAlchemy ORM models
│   ├── db.py         # Database facade: get_schema(), execute()
│   └── populate_db.py  # Sample data (5 teachers, 20 students, 8 courses, ...)
├── agent/
│   ├── state.py      # AgentState TypedDict
│   ├── prompts.py    # SQL + answer prompt templates
│   ├── nodes.py      # Node functions + retry routing
│   ├── graph.py      # build_graph(database, llm)
│   └── tracing.py    # LangSmith env-var setup
├── app.py            # Gradio UI entry point
├── tests/
│   ├── database/     # DB-layer tests (10)
│   └── agent/        # Node, graph, tracing tests (23)
├── data/             # SQLite file lives here (auto-created, gitignored)
├── pyproject.toml
├── uv.lock
└── .env.example
```

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | ≥ 3.12 | Check with `python --version` |
| [uv](https://docs.astral.sh/uv/) | any recent | Install: `curl -Ls https://astral.sh/uv/install.sh \| sh` |
| OpenAI API key | — | <https://platform.openai.com/api-keys> |
| LangSmith API key | optional | <https://smith.langchain.com> — free tier available |

---

## Step-by-step setup on a fresh machine

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd ai-qa-university
```

### 2. Create the environment and install dependencies

```bash
uv sync --group dev
```

This reads `pyproject.toml` + `uv.lock`, creates a `.venv/` folder, and installs all dependencies (SQLAlchemy, LangGraph, LangChain-OpenAI, Gradio, pytest, etc.).

`--group dev` adds pytest (listed under `[dependency-groups] dev`). Omit it for a runtime-only install.

> **If you see an "Access is denied" error** on Windows and a `.venv/` already exists (e.g. created by a different Python version), delete it first and retry:
> ```bash
> rm -rf .venv
> uv sync --group dev
> ```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your keys:

```dotenv
# Required
OPENAI_API_KEY=sk-...

# Optional — enables LangSmith tracing (strongly recommended)
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=university-qa

# Optional — defaults to sqlite:///data/university.db
DATABASE_URL=sqlite:///data/university.db
```

### 4. Create and populate the database

```bash
uv run python -m database.populate_db
```

This creates `data/university.db` and inserts:

| Table | Rows |
|---|---|
| teachers | 5 |
| students | 20 |
| courses | 8 |
| course_offerings | 15 (across Fall 2024, Spring 2025, Fall 2025) |
| enrollments | 60 (with varied grades) |

> **Tip:** Re-running `python -m database.populate_db` drops and re-populates everything from scratch.

### 5. Run the application

```bash
uv run python app.py
```

Open your browser at **http://127.0.0.1:7860**.

> The app auto-populates the database on first launch if it's empty, so you can also skip step 4.

---

## Using the UI

Type a question in the text box and press **Enter** or click **Ask**.

The UI returns three sections:

| Section | What it shows |
|---|---|
| **Answer** | Human-readable response from GPT-4o |
| **Generated SQL** | The SQL query executed against the database (syntax-highlighted) |
| **Raw results** | The exact rows returned by SQLite, as JSON |

**Example questions to try:**

```
How many students are enrolled in total?
What is the average grade in Introduction to AI?
Which teacher teaches the most courses in Fall 2025?
List students enrolled in Database Systems in Spring 2025.
Who are the top 3 students by average grade?
How many students passed (grade ≥ 70) in Machine Learning?
```

---

## Checking LangSmith traces

When `LANGSMITH_API_KEY` is set, every question automatically produces a full trace.

1. Go to <https://smith.langchain.com>
2. Open your project (`university-qa` by default)
3. Click on any run — you'll see:

```
Run
├── generate_sql   input: {question, schema}  output: {sql}
├── run_sql        input: {sql}               output: {results}  ← real DB rows
└── format_answer  input: {question, sql, results} output: {answer}
```

Each LLM call shows the exact prompt sent and response received. If SQL generation failed and retried, you'll see the retry loop with the error message fed back into the prompt.

> The UI shows a badge confirming whether tracing is enabled when the app starts.

---

## Running the tests

```bash
uv run pytest
```

Expected output:

```
33 passed in ~1.5s
```

### Run a specific test module

```bash
# DB layer only
uv run pytest tests/database/ -v

# Agent nodes only
uv run pytest tests/agent/test_nodes.py -v

# End-to-end graph
uv run pytest tests/agent/test_graph.py -v
```

### What the tests cover

| File | Tests | Covers |
|---|---|---|
| `tests/database/test_db.py` | 10 | Schema creation, row counts, multi-table joins, aggregations (AVG, COUNT), semester filtering, SELECT-only security guard, CTE support |
| `tests/agent/test_nodes.py` | 12 | `_clean_sql`, `should_retry`, `generate_sql` (initial + retry prompt), `run_sql` (success / error), `format_answer` (success + max-retry branch) |
| `tests/agent/test_graph.py` | 5 | Happy path, retry recovery, max-retry error answer, complex JOIN, minimal input |
| `tests/agent/test_tracing.py` | 4 | `setup_tracing` with/without API key, legacy `LANGCHAIN_*` env var convention, custom project name |

All tests use an **in-memory SQLite database** and a **mock LLM** — no real API calls, no files written.

---

## Design decisions

### DB-agnostic agent

The agent never imports anything from `database/` except `Database`. It only calls two methods:

```python
db.get_schema()   # → string describing tables / columns / FKs for the LLM prompt
db.execute(sql)   # → list[dict] of result rows
```

Switching to PostgreSQL is a one-line change to the connection URL:

```python
Database("postgresql+psycopg2://user:pass@host/dbname")
```

### Retry loop

The LangGraph graph has a conditional edge after `run_sql`:

```
run_sql → error? → retry? → generate_sql (with error in prompt)
                → max retries → format_answer (explains failure to user)
```

The LLM receives its own previous SQL and the exact database error, which gives it everything it needs to self-correct.

### Prompts are isolated

All prompt text lives in `agent/prompts.py`. You can tune the SQL generation instruction, the retry hint, or the answer style without touching any node or graph logic.

### LangSmith via env vars only

No tracing code is mixed into the agent. `setup_tracing()` sets the required `LANGSMITH_*` and `LANGCHAIN_*` env vars, and LangGraph + LangChain do the rest automatically.

---

## Production considerations

If you were bringing this system to production, you would need to address:

| Area | What to do |
|---|---|
| **Reliability** | Add timeouts on LLM calls (`ChatOpenAI(request_timeout=30)`); wrap `graph.invoke` in a try/except at the API boundary; implement circuit-breaking if OpenAI is down |
| **Scalability** | Move `build_graph()` to a singleton service; serve via FastAPI with async endpoints (`graph.ainvoke`); replace SQLite with PostgreSQL for concurrent writes |
| **Security** | The `execute()` method already blocks non-SELECT statements; additionally enforce query time limits, row-count caps, and column-level access control for sensitive data |
| **Monitoring** | LangSmith in production mode; add latency/error-rate metrics per node; alert on retry-rate spikes (signal of prompt quality degradation) |
| **Deployment** | Containerise with Docker; store `OPENAI_API_KEY` and `LANGSMITH_API_KEY` in a secrets manager (AWS Secrets Manager, GCP Secret Manager); use managed PostgreSQL |
| **Cost control** | Cache frequent query→SQL pairs in Redis; use `gpt-4o-mini` for simple queries and route to `gpt-4o` only for complex ones |
| **Schema changes** | `get_schema()` is dynamic (reads live DB via `inspect()`), so schema changes are picked up automatically — no redeploy needed for the prompt |


==========================================================


