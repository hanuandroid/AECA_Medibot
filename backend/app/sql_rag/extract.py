"""Step 2a - extract just the SQL statement from raw LLM output.

Handles: ```sql fenced blocks, bare ``` fences, "Here is the SQL:" style prefixes, trailing
explanations, "SQL:" labels, and a trailing semicolon.
"""

from __future__ import annotations

import re

_FENCE_RE = re.compile(r"```[ \t]*(?:sql|sqlite)?[ \t]*\n?(.*?)```", re.IGNORECASE | re.DOTALL)
_START_RE = re.compile(r"\b(WITH|SELECT)\b", re.IGNORECASE)
# Lines that clearly start prose after the statement ends.
_PROSE_LINE_RE = re.compile(
    r"^\s*(This query|This SQL|Explanation|Note:|The query|The above|It |Here )", re.IGNORECASE
)


class SQLExtractionError(ValueError):
    pass


def extract_sql(raw: str) -> str:
    """Return a single SQL statement (without trailing ';') from LLM output."""
    if not raw or not raw.strip():
        raise SQLExtractionError("LLM returned no SQL")
    text = raw.strip()

    fenced = _FENCE_RE.findall(text)
    if fenced:
        # Prefer the first fenced block that actually contains a query.
        candidates = [b for b in fenced if _START_RE.search(b)]
        text = (candidates or fenced)[0].strip()
    elif text.count("```") == 1:  # unterminated fence
        text = text.split("```", 1)[1]
        text = re.sub(r"^\s*(sql|sqlite)\b", "", text, flags=re.IGNORECASE).strip()

    match = _START_RE.search(text)
    if not match:
        raise SQLExtractionError(f"No SELECT statement found in LLM output: {raw[:200]!r}")
    text = text[match.start() :]

    # Cut at the first statement terminator; anything after it is not executed.
    if ";" in text:
        text = text.split(";", 1)[0]

    kept: list[str] = []
    for line in text.splitlines():
        if kept and (not line.strip() and _looks_finished(kept)):
            break
        if kept and _PROSE_LINE_RE.match(line):
            break
        kept.append(line)
    sql = "\n".join(kept).strip()
    if not sql:
        raise SQLExtractionError("Empty SQL after extraction")
    return sql


def _looks_finished(lines: list[str]) -> bool:
    """A blank line ends the statement unless we are inside open parentheses."""
    joined = "\n".join(lines)
    return joined.count("(") <= joined.count(")")
