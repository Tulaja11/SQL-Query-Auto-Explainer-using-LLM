"""
analyzer.py
Static analysis of SQL queries using sqlglot.
Runs before the LLM call — provides structured facts the prompt can use.
"""

import sqlglot
import sqlglot.expressions as exp


def analyze_query(sql: str, dialect: str | None = None) -> dict:
    """
    Parse the query with sqlglot and extract structural facts.
    Returns a dict that is JSON-serializable and safe to embed in a prompt.
    """
    result = {
        "parse_ok": False,
        "tables": [],
        "columns": [],
        "clauses": [],
        "join_count": 0,
        "subquery_count": 0,
        "has_star_select": False,
        "has_distinct": False,
        "has_limit": False,
        "has_window": False,
        "has_cte": False,
        "statement_type": "UNKNOWN",
        "warnings": [],
    }

    try:
        parsed = sqlglot.parse_one(sql, dialect=dialect, error_level=sqlglot.ErrorLevel.WARN)
    except Exception as e:
        result["warnings"].append(f"Parse error: {str(e)}")
        return result

    result["parse_ok"] = True

    # Statement type
    result["statement_type"] = type(parsed).__name__.upper()

    # Tables
    tables = set()
    for table in parsed.find_all(exp.Table):
        if table.name:
            tables.add(table.name)
    result["tables"] = sorted(tables)

    # Columns referenced
    cols = set()
    for col in parsed.find_all(exp.Column):
        if col.name:
            cols.add(col.name)
    result["columns"] = sorted(cols)[:20]  # cap at 20

    # Clauses present
    clauses = []
    clause_map = {
        exp.Where:   "WHERE",
        exp.Group:   "GROUP BY",
        exp.Having:  "HAVING",
        exp.Order:   "ORDER BY",
        exp.Limit:   "LIMIT",
        exp.Join:    "JOIN",
        exp.With:    "WITH (CTE)",
        exp.Distinct:"DISTINCT",
        exp.Window:  "WINDOW / OVER",
    }
    for node_type, label in clause_map.items():
        if parsed.find(node_type):
            clauses.append(label)
    result["clauses"] = clauses

    # Counts
    result["join_count"] = len(list(parsed.find_all(exp.Join)))
    result["subquery_count"] = len(list(parsed.find_all(exp.Subquery)))
    result["has_star_select"] = bool(parsed.find(exp.Star))
    result["has_distinct"] = bool(parsed.find(exp.Distinct))
    result["has_limit"] = bool(parsed.find(exp.Limit))
    result["has_window"] = bool(parsed.find(exp.Window))
    result["has_cte"] = bool(parsed.find(exp.With))

    # Basic static warnings (heuristic — LLM will give richer analysis)
    if result["has_star_select"]:
        result["warnings"].append("SELECT * found — may pull unnecessary columns")
    if result["subquery_count"] > 2:
        result["warnings"].append(f"{result['subquery_count']} subqueries detected — consider CTEs for readability")
    if result["join_count"] > 4:
        result["warnings"].append(f"{result['join_count']} JOINs detected — review index coverage")
    if not result["has_limit"] and result["statement_type"] == "SELECT":
        result["warnings"].append("No LIMIT clause — query may return large result sets")

    return result
