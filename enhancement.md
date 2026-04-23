# Enhancement Notes

The current `AGENT.md` plan is mostly aligned with the homework requirements. The main goal should be to keep the implementation small, explainable, and easy to debug.

## Keep

- Flat project structure.
- SQLAlchemy + SQLite.
- One `agent.py`.
- LangSmith tracing through environment variables.
- Simple Gradio UI.
- Small retry loop for failed SQL generation.
- Schema introspection with `sqlalchemy.inspect()`.

## Recommended Improvements

### 1. Make DB-Agnostic Design Explicit

The assignment emphasizes database-agnostic design. The LangGraph agent should depend only on a small database interface:

```python
db.get_schema()
db.execute(sql)
```

`agent.py` should not import ORM models or contain schema-specific code. This makes the agent easier to reuse with another database or schema.

### 2. Add SQL Safety Validation

Before executing generated SQL, validate that it is read-only.

Allow:

- `SELECT`
- `WITH ... SELECT`

Reject:

- `INSERT`
- `UPDATE`
- `DELETE`
- `DROP`
- `ALTER`
- `CREATE`

This keeps the app safer and makes the behavior easier to defend in the interview.

### 3. Handle Empty Results and Ambiguous Questions

Add simple behavior for common failure cases:

- Empty query result: return a clear message such as `No matching records found.`
- Ambiguous question: ask the user for clarification instead of forcing an unreliable SQL query.

### 4. Keep Multi-Step Reasoning Simple

Do not add planner/router nodes unless they become necessary. Most complex questions can be handled by one SQL query using joins, aggregations, subqueries, or CTEs.

### 5. Include SQL Schema in the Deliverables

The assignment asks for SQL schema and seed data. Even if SQLAlchemy creates the tables, include one of the following:

- `schema.sql`
- a README section showing the generated schema

This makes the project easier to review.

### 6. Strengthen Tests

In addition to database joins, aggregations, mocked SQL generation, and end-to-end tests, add tests for:

- unsafe SQL rejection
- empty result handling
- retry after invalid SQL

Mock LLM responses in unit tests. Do not rely on live OpenAI calls for automated tests.

### 7. Document Tracing Clearly

LangSmith through environment variables is enough, but the README should clearly explain:

- how to enable tracing
- which LangGraph nodes appear in the trace
- one example trace flow: question -> generated SQL -> DB results -> final answer

### 8. Make the Model Configurable

Avoid hardcoding the OpenAI model in code. Use an environment variable:

```env
OPENAI_MODEL=gpt-4o
```

This keeps the app simple and easy to update.

## Recommended Simplified Graph

```text
question
  -> generate_sql
  -> validate_sql
  -> run_sql
  -> format_answer
```

Optionally keep a retry edge from `run_sql` back to `generate_sql` when SQL execution fails.

## Avoid Adding

- abstract base classes
- separate tracing module
- vector database
- complex agent memory
- multi-agent setup
- large package structure

## Summary

The current plan is good. The safest improvements are SQL validation, clearer DB abstraction, empty and ambiguous-result handling, and stronger README/tracing documentation. These changes keep the project simple while better matching the assignment requirements.
