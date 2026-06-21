"""
formatter.py
Helper utilities for formatting and post-processing LLM output.
"""

import re


def format_explanation(text: str) -> str:
    """Clean up and normalise an explanation string from the LLM."""
    text = text.strip()
    # Remove stray markdown bold/italic artifacts
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
    return text


def severity_color(severity: str) -> str:
    """Map severity string to a hex colour for display."""
    return {
        "critical": "#ef4444",
        "warning":  "#f59e0b",
        "ok":       "#22c55e",
    }.get(severity.lower(), "#94a3b8")


def truncate(text: str, max_len: int = 120) -> str:
    """Truncate a string for display use."""
    return text if len(text) <= max_len else text[:max_len - 1] + "…"
