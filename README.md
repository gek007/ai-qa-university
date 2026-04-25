# University QA Agent

A natural-language question-answering system over a university database, built with **LangGraph**, **SQLAlchemy**, **OpenAI GPT-4o**, and a **Gradio** UI.


## Frontend UI screenshot: 
![1777148340307](image/README/1777148340307.png)

## DB Tables screenshot: 
![1777148441308](image/README/1777148441308.png)

## Console logs and logs from LanchChain Smith:
![1776986754756](image/README/1776986754756.png)

## LangGraph Agent's visual graph      
![1777148689078](image/README/1777148689078.png)


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
│   └── seed.py  # Sample data (5 teachers, 20 students, 8 courses, ...)
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
uv run python -m database.seed
```

This creates `data/university.db` and inserts:

| Table | Rows |
|---|---|
| teachers | 5 |
| students | 20 |
| courses | 8 |
| course_offerings | 15 (across Fall 2024, Spring 2025, Fall 2025) |
| enrollments | 60 (with varied grades) |

> **Tip:** Re-running `python -m database.seed` drops and re-populates everything from scratch.

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
29 passed in ~6s
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
| `tests/agent/test_nodes.py` | 14 | `_clean_sql`, `should_retry`, `generate_sql` (initial + retry prompt), `run_sql` (success / error), `format_answer` (success + max-retry branch) |
| `tests/agent/test_graph.py` | 5 | Happy path, retry recovery, max-retry error answer, complex JOIN, minimal input |

All tests use an **in-memory SQLite database** and a **mock LLM** — no real API calls, no files written.

---

## Logging

Configuration is in [`log_config.py`](log_config.py). It runs when you start `app.py` or `python -m database.seed`. If something else (e.g. `pytest`) already attached handlers to the root logger, `configure()` does nothing.

### Where output goes

| Destination | Default | Env vars |
|-------------|---------|----------|
| **Console** | On, **`stdout`** | `LOG_TO_CONSOLE` (`true`/`false`), `LOG_STREAM` (`stdout` or `stderr`) |
| **Rotating files** | Off | `LOG_TO_FILE` (`true`/`false`), `LOG_FILE` (path under the project, default `logs/ai-qa-university.log`) |

**Rotating file behavior:** `logging.handlers.RotatingFileHandler` — when the active file reaches `LOG_MAX_BYTES` (default 1,048,576 bytes), it is rolled to `.1`, previous `.1` → `.2`, etc. `LOG_BACKUP_COUNT` (default **10**) is how many such backup files are kept, after which the oldest is deleted. The `logs/` directory is created automatically and is **gitignored**.

### Log level

| Level   | What you will see (examples) |
|--------|------------------------------|
| **INFO** | App startup, user questions, SQL execution recovery attempts, LangSmith status, population summary |
| **WARNING** | Dropping the schema, blocking non-SELECT SQL, max SQL retries, missing LangSmith key |
| **ERROR** | Uncaught exceptions (e.g. `database.seed` main failure) |
| **DEBUG** | Per-query row counts, engine URL, graph compile message, `generate_sql` question preview |

Example `.env`:

```dotenv
LOG_LEVEL=DEBUG
LOG_TO_CONSOLE=true
LOG_STREAM=stdout
LOG_TO_FILE=true
LOG_FILE=logs/ai-qa-university.log
LOG_MAX_BYTES=1048576
LOG_BACKUP_COUNT=10
```

Or via the shell:

```bash
LOG_LEVEL=DEBUG LOG_TO_FILE=true uv run python app.py
```

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

## Task 8 — Production considerations

The codebase is a strong **local / learning demo**. Shipping it to real users would mean more than tuning prompts: you would **treat the LLM, DB, and API as production systems**. The points below are a **practical checklist** — things to think about, not work already done in this repo.

### At a glance

| Topic | In one sentence |
|--------|-----------------|
| **Reliability** | Don’t let slow or failing models hang the app; catch errors at the HTTP boundary. |
| **Scalability** | Reuse the graph, prefer async + a real server database when traffic grows. |
| **Security** | Keep the existing `SELECT`-only rule; add guardrails (limits, caps, who sees what). |
| **Monitoring** | Use LangSmith and metrics so you see latency, errors, and “too many SQL retries.” |
| **Deployment** | Package in containers; load secrets from a store; use managed DB in the cloud. |
| **Cost** | Cache and route cheaper models for simple questions. |
| **Schema** | The prompt’s schema is read from the DB, so some migrations don’t need a code redeploy. |

### Reliability

*You want clear failure behavior when the model or network misbehaves.*

- Time out LLM calls (e.g. `ChatOpenAI(request_timeout=30)`).
- Wrap `graph.invoke` in `try` / `except` at the API layer so the client always gets a controlled response.
- If the provider is down, consider **circuit breaking** or **degraded mode** so users see a message instead of a long hang.

### Scalability

*One process should build the graph once and serve many requests efficiently.*

- Build `build_graph()` **once** and reuse it (singleton-style) in a long-lived process.
- Put it behind a framework like **FastAPI** and use `graph.ainvoke` for async handlers.
- Prefer **PostgreSQL** (or similar) over SQLite when you have concurrent writers or stricter operations needs.

### Security

*Non-`SELECT` SQL is already blocked; production usually needs more than that.*

- Add **per-query time limits** and **row count caps** so one bad question cannot DoS the DB.
- If you have sensitive columns, plan **access rules** (who can see which fields).

### Monitoring

*You need to notice drift before users complain.*

- Run **LangSmith** with a production-appropriate project and data retention.
- Measure **latency and errors per node**; **alert** when **SQL retry rate** jumps (often prompt or data-quality issues).

### Deployment

*Same app, boring infrastructure — that’s a good sign.*

- **Docker (or similar)** with pinned Python and lockfiles in the image.
- Store `OPENAI_API_KEY` and `LANGSMITH_API_KEY` in a **secrets manager** (e.g. AWS, GCP), not only flat files on a VM.
- Use **managed PostgreSQL** in cloud-like deployments instead of a local SQLite file.

### Cost control

*Traffic gets expensive if every question hits the biggest model.*

- **Cache** frequent **question → SQL** pairs (e.g. **Redis**).
- Send easy questions to **`gpt-4o-mini`**, **reserve `gpt-4o`** (or better) for harder ones.

### Schema changes

*How much do you have to redeploy when the DB changes?*

- `get_schema()` uses SQLAlchemy `inspect()` on the **live** database, so many schema updates reach the LLM **without a new deploy** — still **test** after each migration.

**“Production-ready” in practice** means: stable under load, room to grow, visible when things break, and safe enough to run outside your own machine.

---

