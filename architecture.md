# Architecture — University QA Agent

## Overview

This system implements a natural-language question answering agent over a relational university database.
It allows users to ask complex questions (aggregations, joins, filters) and receive accurate, human-readable answers.

The architecture is designed with the following goals:

* **Database-agnostic design**
* **Full traceability and debuggability**
* **Modular and explainable components**
* **Support for multi-step reasoning via LangGraph**

---

## High-Level Flow

```
User Question
      ↓
LangGraph Agent
  ├── generate_sql     (LLM: NL → SQL)
  ├── run_sql          (DB execution)
  └── format_answer    (LLM: results → natural language)
      ↓
Answer + SQL + Results
      ↓
LangSmith Trace
```

---

## LangGraph Execution Model

The system is implemented as a LangGraph state machine with a controlled retry loop:

```
generate_sql → run_sql → check_error
                         ├── no error → format_answer
                         └── error → retry (max 2 times)
                                      ↓
                                format_answer (error explanation)
```

### Key properties:

* Errors in SQL generation are **fed back into the LLM prompt**
* The agent can **self-correct invalid queries**
* Final fallback always returns a **user-friendly explanation**

---

## Core Components

### 1. Database Layer (`database/`)

Encapsulates all database-specific logic.

**Responsibilities:**

* Define schema using SQLAlchemy ORM
* Provide schema introspection for the LLM
* Execute SQL safely

**Public interface:**

```python
db.get_schema()   # → string representation of schema
db.execute(sql)   # → list[dict]
```

### Design decision:

The agent interacts only with this interface, making the system **fully DB-agnostic**.

Switching databases (e.g., SQLite → PostgreSQL) requires only changing the connection string.

---

### 2. Agent Layer (`agent/`)

Implements the LangGraph workflow.

#### State

```python
AgentState = {
    question: str,
    sql: str,
    results: list,
    answer: str,
    error: str,
    retries: int
}
```

#### Nodes

* **generate_sql**

  * Converts natural language into SQL using schema context
* **run_sql**

  * Executes SQL and captures errors
* **format_answer**

  * Converts raw results into a human-readable answer
* **retry logic**

  * Determines whether to regenerate SQL based on errors

---

### 3. Prompt Design

Prompts are isolated in `agent/prompts.py`.

They include:

* SQL generation instructions
* Error-aware retry prompts
* Answer formatting templates

### Design decision:

Separating prompts allows:

* independent tuning
* easier debugging
* faster iteration without touching logic

---

### 4. Tracing & Observability

Tracing is implemented via **LangSmith**.

Captured automatically:

* user input
* each LangGraph node execution
* LLM prompts and responses
* generated SQL
* database results

### Trace flow:

```
User Input
 → generate_sql
 → run_sql
 → format_answer
 → Final Output
```

### Benefits:

* full transparency of reasoning
* easy debugging of failures
* clear explanation during interview/demo

---

## Error Handling Strategy

The system handles:

* invalid SQL generation
* empty result sets
* ambiguous user queries

### Approach:

* capture DB errors
* inject error into next prompt
* allow LLM to self-correct
* limit retries (max = 2)
* gracefully degrade with explanation

---

## DB-Agnostic Design

The system enforces separation between:

* **data layer (schema, execution)**
* **agent logic (reasoning, orchestration)**

The agent:

* does not depend on specific table names in code
* receives schema dynamically via `get_schema()`

This allows:

* reuse with different schemas
* minimal refactoring for new domains

---

## Testing Strategy

Tests are structured in three levels:

### 1. Database tests

* joins across tables
* aggregations (AVG, COUNT)
* filtering

### 2. Agent node tests

* SQL generation behavior
* retry logic
* error handling

### 3. End-to-end tests

* full pipeline: question → answer
* retry scenarios
* complex queries

All tests use:

* in-memory database
* mocked LLM

---

## Production Considerations

### Reliability

* add timeouts to LLM calls
* handle API failures gracefully

### Scalability

* switch to PostgreSQL
* serve via FastAPI
* reuse compiled LangGraph instance

### Security

* restrict to SELECT queries only
* limit result size
* enforce query timeouts

### Monitoring

* LangSmith tracing
* error rate tracking
* retry frequency alerts

### Cost optimization

* cache frequent queries
* use smaller models for simple tasks

---

## Design Summary

This system prioritizes:

* **clarity over complexity**
* **modularity over tight coupling**
* **traceability over abstraction hiding**

The result is a system that is:

* easy to explain
* easy to debug
* easy to extend
* suitable as a foundation for production systems
