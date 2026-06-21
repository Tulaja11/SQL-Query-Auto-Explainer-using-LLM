#  SQL Query Auto-Explainer

> Paste any SQL query → get a plain-English breakdown, execution order, performance warnings, bug detection, and an optimized rewrite — powered by Gemini + sqlglot.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red?logo=streamlit)
![sqlglot](https://img.shields.io/badge/sqlglot-23+-green)
![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?logo=google)

---

## What it does

| Feature | Details |
|---|---|
| **Plain-English explanation** | What the query does in 2-4 readable sentences |
| **Execution order walkthrough** | Step-by-step logical execution (FROM → JOIN → WHERE → GROUP → HAVING → SELECT → ORDER) |
| **Performance issue detection** | SELECT *, missing LIMITs, N+1 subqueries, too many JOINs |
| **Bug identification** | Off-by-one errors, implicit type casts, unsafe DELETEs without WHERE |
| **Optimized SQL rewrite** | Gemini rewrites the query addressing all flagged issues |
| **Static AST analysis** | sqlglot parses the query without an API call — tables, clauses, counts |
| **Multi-dialect support** | MySQL, PostgreSQL, SQLite, BigQuery, Snowflake, Spark |

---

## Demo

```
Input:
  SELECT * FROM orders o
  JOIN customers c ON o.cust_id = c.id
  WHERE o.status IN (SELECT status FROM valid_statuses)
  ORDER BY o.created_at DESC

Output:
  One-liner:  Fetches all order and customer data for valid-status orders, newest first.
  Complexity: Moderate
  Issues:     ⚠ SELECT * (warning) | ⚠ Subquery in WHERE — consider JOIN (warning)
  Optimized:  SELECT o.id, o.amount, c.name, c.email FROM orders o
              JOIN customers c ON o.cust_id = c.id
              JOIN valid_statuses vs ON o.status = vs.status
              ORDER BY o.created_at DESC
```

---

## Architecture

```
sql-explainer/
├── app.py              # Streamlit UI + orchestration
├── src/
│   ├── analyzer.py     # sqlglot static analysis (no API call)
│   └── formatter.py    # Display helpers
├── requirements.txt
└── README.md
```

### Two-stage pipeline

```
User SQL
   │
   ▼
┌─────────────────────────────┐
│  Stage 1: Static Analysis   │  sqlglot (local, instant, free)
│  - Parse AST                │  → tables, clauses, join count,
│  - Detect clauses           │    subquery count, SELECT *,
│  - Flag basic warnings      │    no LIMIT, etc.
└────────────┬────────────────┘
             │ structured facts
             ▼
┌─────────────────────────────┐
│  Stage 2: LLM Analysis      │  Google Gemini API
│  - Plain English             │  → one_liner, plain_english,
│  - Execution steps           │    execution_steps,
│  - Performance issues        │    performance_issues,
│  - Bug detection             │    bugs, optimized_sql,
│  - Optimized rewrite         │    complexity, tables_used
└─────────────────────────────┘
```

The static analysis runs first and its findings are injected into the Gemini prompt — this means the LLM gets pre-computed structural facts and can focus on semantic reasoning rather than counting JOINs.

---

## Tech stack

| Tool | Role | Why |
|---|---|---|
| **Streamlit** | UI framework | Fast to ship, data-app native, no frontend boilerplate |
| **Google Gemini** | LLM reasoning | Free-tier friendly, strong SQL semantic understanding |
| **sqlglot** | SQL parser / AST | Dialect-aware, no DB connection needed, open source |

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/sql-explainer.git
cd sql-explainer
pip install -r requirements.txt
```

### 2. Get an API key

Get a free API key at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).

### 3. Run

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

Enter your Gemini API key in the sidebar and paste any SQL query.

---

## Key design decisions

**Why sqlglot for static analysis?**
sqlglot is a pure-Python, dependency-light SQL parser that supports 20+ dialects. It gives us a structured AST we can traverse without a running database. Running static analysis before the LLM call means we inject real structural facts (exact table names, clause list, join count) into the prompt instead of asking the model to guess — this improves accuracy and reduces hallucination.

**Why not just call the LLM directly?**
LLMs can misccount JOINs or miss a nested subquery. sqlglot doesn't hallucinate — it either parses or throws an error. Using both tools in sequence gives the accuracy of a parser with the reasoning ability of an LLM.

**Why structured JSON output from Gemini?**
Returning structured JSON lets us render each field independently (tabs, badges, cards) instead of parsing free text. The prompt enforces a schema and we strip any markdown fences before `json.loads()`.

---

## Skills demonstrated

- **LLM prompt engineering** — structured JSON output, injecting static context
- **Python parsing** — AST traversal with sqlglot expressions
- **Data analyst tooling** — problem domain is core to analytics workflows
- **Streamlit UI** — multi-tab layout, sidebar settings, dynamic rendering
- **Software design** — two-stage pipeline, separation of concerns

---

## Extending it

Ideas for v2:

- **Execution plan integration** — connect to a live DB and run `EXPLAIN ANALYZE`, overlay cost on the explanation
- **Query history** — SQLite-backed log of past queries with scores
- **Batch mode** — upload a `.sql` file with multiple queries, audit all at once
- **VS Code extension** — right-click any `.sql` file → explain in sidebar
- **dbt model support** — parse Jinja-templated SQL from dbt projects

---

## License

MIT
