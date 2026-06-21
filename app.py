import streamlit as st
import sqlglot
import google.generativeai as genai
import json
import re
from src.analyzer import analyze_query
from src.formatter import format_explanation

st.set_page_config(
    page_title="SQL Explainer",
    page_icon="🔍",
    layout="wide",
)

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.main-title {
    font-size: 2rem; font-weight: 600; letter-spacing: -0.5px;
    color: #0f172a; margin-bottom: 0;
}
.subtitle { color: #64748b; font-size: 0.95rem; margin-top: 4px; }

.badge {
    display: inline-block; padding: 3px 10px; border-radius: 999px;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em;
    text-transform: uppercase; margin-right: 6px;
}
.badge-warning  { background: #fef3c7; color: #92400e; }
.badge-danger   { background: #fee2e2; color: #991b1b; }
.badge-info     { background: #dbeafe; color: #1e40af; }
.badge-success  { background: #dcfce7; color: #166534; }

.section-card {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 10px; padding: 1.1rem 1.3rem; margin-bottom: 1rem;
}
.section-card h4 { margin: 0 0 0.5rem; font-size: 0.85rem; color: #475569;
    text-transform: uppercase; letter-spacing: 0.07em; font-weight: 600; }
.section-card p, .section-card li { color: #1e293b; font-size: 0.93rem; line-height: 1.7; }

.issue-row {
    border-left: 3px solid #f59e0b; background: #fffbeb;
    border-radius: 0 8px 8px 0; padding: 0.7rem 1rem; margin-bottom: 0.6rem;
}
.issue-row.critical { border-color: #ef4444; background: #fff1f2; }
.issue-row.good     { border-color: #22c55e; background: #f0fdf4; }

.step-num {
    display: inline-flex; width: 24px; height: 24px; border-radius: 50%;
    background: #6366f1; color: white; font-size: 0.75rem; font-weight: 700;
    align-items: center; justify-content: center; margin-right: 8px;
    flex-shrink: 0;
}
.step-row { display: flex; align-items: flex-start; margin-bottom: 0.55rem; }
.step-text { color: #1e293b; font-size: 0.92rem; line-height: 1.6; padding-top: 3px; }

code, .mono { font-family: 'JetBrains Mono', monospace; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-title">🔍 SQL Query Explainer</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Paste any SQL query → get a plain-English breakdown, performance tips, and bug warnings.</p>', unsafe_allow_html=True)
st.markdown("---")

# ── Sidebar: API Key + dialect ────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    api_key = st.text_input("Gemini API Key", type="password",
                            help="Get a free key at aistudio.google.com/app/apikey")
    model_name = st.selectbox("Gemini Model", ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
                              help="Flash models are faster and free-tier friendly")
    dialect = st.selectbox("SQL Dialect", ["auto", "mysql", "postgres", "sqlite",
                                           "bigquery", "snowflake", "spark"],
                           help="Choose the dialect for smarter parsing")
    show_ast = st.checkbox("Show parsed AST", value=False,
                           help="See how sqlglot parsed your query")
    st.markdown("---")
    st.markdown("**Example queries**")
    examples = {
        "Simple JOIN": """SELECT e.name, d.dept_name, e.salary
FROM employees e
JOIN departments d ON e.dept_id = d.id
WHERE e.salary > 50000
ORDER BY e.salary DESC;""",
        "Subquery + GROUP BY": """SELECT dept_id, AVG(salary) as avg_sal
FROM employees
WHERE dept_id IN (
    SELECT id FROM departments WHERE location = 'Mumbai'
)
GROUP BY dept_id
HAVING AVG(salary) > 60000;""",
        "Window Function": """SELECT name, salary, dept_id,
    RANK() OVER (PARTITION BY dept_id ORDER BY salary DESC) as rank_in_dept,
    SUM(salary) OVER (PARTITION BY dept_id) as dept_total
FROM employees;""",
        "CTE + DELETE": """WITH old_orders AS (
    SELECT order_id FROM orders
    WHERE created_at < NOW() - INTERVAL '2 years'
)
DELETE FROM orders WHERE order_id IN (SELECT order_id FROM old_orders);""",
    }
    for label, sql in examples.items():
        if st.button(label, use_container_width=True):
            st.session_state["query_input"] = sql

# ── Query input ───────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_area(
        "Paste your SQL query here",
        value=st.session_state.get("query_input", ""),
        height=200,
        placeholder="SELECT * FROM ...",
        key="query_text",
    )

with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    explain_btn = st.button("▶ Explain Query", type="primary", use_container_width=True)
    clear_btn   = st.button("Clear", use_container_width=True)
    if clear_btn:
        st.session_state["query_input"] = ""
        st.rerun()

# ── Analysis ──────────────────────────────────────────────────────────────────
if explain_btn and query.strip():
    if not api_key:
        st.error("Please add your Gemini API key in the sidebar.")
        st.stop()

    with st.spinner("Analyzing your query..."):
        # 1. Static analysis (sqlglot — no API call)
        static = analyze_query(query, dialect if dialect != "auto" else None)

        # 2. LLM explanation
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        prompt = f"""You are a senior SQL expert. Analyze the following SQL query and return a JSON object with exactly these keys:

{{
  "one_liner": "One sentence (max 25 words) describing what this query does",
  "plain_english": "2-4 sentence plain English explanation of the full query logic",
  "execution_steps": ["step 1 description", "step 2 description", ...],
  "performance_issues": [
    {{"severity": "warning|critical|ok", "issue": "short label", "detail": "explanation"}}
  ],
  "bugs": [
    {{"description": "bug description", "fix": "how to fix it"}}
  ],
  "optimized_sql": "rewritten optimized SQL or empty string if already optimal",
  "complexity": "simple|moderate|complex",
  "tables_used": ["table1", "table2"]
}}

Rules:
- execution_steps should be 3-7 steps showing the logical execution order
- performance_issues can be empty list if no issues
- bugs can be empty list if no bugs
- optimized_sql is a string with the rewritten query, or "" if already optimal
- Return ONLY valid JSON. No markdown, no explanation outside the JSON.

SQL Query:
{query}

SQL Dialect hint: {dialect}
Static analysis findings: {json.dumps(static)}"""

        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=1500,
                    temperature=0.3,
                ),
            )
            raw = response.text.strip()
        except Exception as e:
            st.error(f"Gemini API error: {e}")
            st.stop()

        # strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            st.error("Could not parse LLM response. Try again.")
            st.code(raw)
            st.stop()

    # ── Display results ───────────────────────────────────────────────────────
    st.markdown("---")

    # Complexity + one-liner header
    complexity_colors = {"simple": "success", "moderate": "warning", "complex": "danger"}
    c = result.get("complexity", "moderate")
    st.markdown(
        f'<span class="badge badge-{complexity_colors.get(c, "info")}">{c}</span>'
        f'<span style="font-size:1.15rem; font-weight:600; color:#f1f5f9;">'
        f'{result.get("one_liner", "")}</span>',
        unsafe_allow_html=True
    )
    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📖 Explanation", "⚠️ Issues & Bugs", "⚡ Optimized SQL", "🔬 Parse Details"])

    with tab1:
        col_a, col_b = st.columns([3, 2])

        with col_a:
            st.markdown('<div class="section-card"><h4>Plain English</h4><p>' +
                        result.get("plain_english", "") + '</p></div>', unsafe_allow_html=True)

            # Execution steps
            steps_html = '<div class="section-card"><h4>Execution order</h4>'
            for i, step in enumerate(result.get("execution_steps", []), 1):
                steps_html += (f'<div class="step-row">'
                               f'<span class="step-num">{i}</span>'
                               f'<span class="step-text">{step}</span></div>')
            steps_html += '</div>'
            st.markdown(steps_html, unsafe_allow_html=True)

        with col_b:
            # Tables & clauses from static analysis
            tables = result.get("tables_used") or static.get("tables", [])
            if tables:
                st.markdown('<div class="section-card"><h4>Tables involved</h4>' +
                            "".join(f'<p>📋 <code>{t}</code></p>' for t in tables) +
                            '</div>', unsafe_allow_html=True)

            clauses = static.get("clauses", [])
            if clauses:
                st.markdown('<div class="section-card"><h4>Clauses detected</h4>' +
                            "".join(f'<p>• <code>{cl}</code></p>' for cl in clauses) +
                            '</div>', unsafe_allow_html=True)

    with tab2:
        perf = result.get("performance_issues", [])
        bugs = result.get("bugs", [])

        if not perf and not bugs:
            st.success("✅ No performance issues or bugs detected.")
        else:
            if perf:
                st.markdown("**Performance issues**")
                for item in perf:
                    sev = item.get("severity", "warning")
                    css_class = "critical" if sev == "critical" else ("good" if sev == "ok" else "")
                    badge_cls = "danger" if sev == "critical" else ("success" if sev == "ok" else "warning")
                    st.markdown(
                        f'<div class="issue-row {css_class}">'
                        f'<span class="badge badge-{badge_cls}">{sev}</span>'
                        f'<strong>{item.get("issue","")}</strong><br>'
                        f'<span style="color:#475569;font-size:0.88rem;">{item.get("detail","")}</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

            if bugs:
                st.markdown("**Bugs found**")
                for bug in bugs:
                    st.markdown(
                        f'<div class="issue-row critical">'
                        f'<span class="badge badge-danger">bug</span>'
                        f'<strong>{bug.get("description","")}</strong><br>'
                        f'<span style="color:#475569;font-size:0.88rem;">Fix: {bug.get("fix","")}</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

    with tab3:
        opt = result.get("optimized_sql", "").strip()
        if opt:
            st.markdown("**Suggested rewrite**")
            st.code(opt, language="sql")
            st.caption("Copy the above — it addresses the performance issues detected.")
        else:
            st.success("✅ Your query is already well-structured. No rewrite needed.")
        st.markdown("**Original query**")
        st.code(query, language="sql")

    with tab4:
        if show_ast:
            try:
                d = dialect if dialect != "auto" else None
                parsed = sqlglot.parse_one(query, dialect=d)
                st.code(parsed.sql(pretty=True), language="sql")
                st.markdown("**AST (JSON)**")
                st.json(json.loads(parsed.dump()))
            except Exception as e:
                st.warning(f"AST parse failed: {e}")
        else:
            st.info("Enable 'Show parsed AST' in the sidebar to see the parse tree.")

        st.markdown("**Static analysis output**")
        st.json(static)

elif explain_btn:
    st.warning("Please enter a SQL query first.")
