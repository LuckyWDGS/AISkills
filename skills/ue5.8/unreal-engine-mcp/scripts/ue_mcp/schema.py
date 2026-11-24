"""Compact views of toolset schemas."""

from __future__ import annotations

import difflib
from typing import Any


def suggest(name: str, candidates: list[str]) -> str | None:
    """The closest candidate for a mistyped name: exact case-insensitive match first, then fuzzy."""
    lowered = {candidate.lower(): candidate for candidate in candidates}
    if name.lower() in lowered:
        return lowered[name.lower()]
    close = difflib.get_close_matches(name.lower(), list(lowered), n=1, cutoff=0.6)
    return lowered[close[0]] if close else None


def argument_problems(tool: dict[str, Any], arguments: dict[str, Any]) -> list[str]:
    """Missing required and unknown argument names, checked locally.

    UE rejects a missing required argument with a full schema dump, and silently
    ignores an unknown one, so a mistyped optional argument would change the result
    without any error.
    """
    schema = tool.get("inputSchema") or {}
    properties = schema.get("properties") or {}
    problems = []
    if properties and not schema.get("additionalProperties"):
        for key in arguments:
            if key not in properties:
                hint = suggest(key, [name for name in properties if name not in arguments])
                problems.append(f"unknown argument {key!r}" + (f" (did you mean {hint!r}?)" if hint else ""))
    for key in schema.get("required") or []:
        if key not in arguments:
            problems.append(f"missing required argument {key!r}")
    return problems


def signature(tool: dict[str, Any]) -> str:
    """``name(arg*: Type, ...) -> Return`` for error messages."""
    row = brief_tools({"tools": [tool]})[0]
    params = ", ".join(f"{p['name']}{'*' if p['required'] else ''}: {p['type']}" for p in row["params"])
    return f"{row['name']}({params})" + (f" -> {row['returns']}" if row["returns"] else "")


def _schema_tools(described: Any) -> list[dict[str, Any]]:
    tools = described.get("tools", []) if isinstance(described, dict) else []
    if isinstance(tools, dict):
        tools = [{"name": name, **value} for name, value in tools.items()]
    return [tool for tool in tools if isinstance(tool, dict)]


def _type_label(schema: Any) -> str:
    if not isinstance(schema, dict):
        return "any"
    if schema.get("type") == "array":
        return f"list[{_type_label(schema.get('items'))}]"
    title = schema.get("title")
    if title:
        # UObject references are titled with their class path, e.g. /Script/Engine.Material.
        return title.rsplit(".", 1)[-1] if title.startswith("/Script/") else title
    return str(schema.get("type") or "any")


def brief_tools(described: Any) -> list[dict[str, Any]]:
    """Compact signatures: name, params (required first), return type, first description line."""
    rows = []
    for tool in _schema_tools(described):
        schema = tool.get("inputSchema") or {}
        required = set(schema.get("required") or [])
        params = [
            {"name": key, "type": _type_label(value), "required": key in required}
            for key, value in (schema.get("properties") or {}).items()
        ]
        params.sort(key=lambda item: not item["required"])
        output = ((tool.get("outputSchema") or {}).get("properties") or {}).get("returnValue")
        summary = next((line.strip() for line in (tool.get("description") or "").splitlines() if line.strip()), "")
        rows.append({
            "name": tool.get("name", "").rsplit(".", 1)[-1],
            "params": params,
            "returns": _type_label(output) if output else "",
            "summary": summary[:120],
        })
    return rows


def render_brief(toolset: str, rows: list[dict[str, Any]]) -> str:
    lines = [f"{toolset} ({len(rows)} tools; * = required; describe-tool <toolset> <tool> for the full schema)"]
    for row in rows:
        params = ", ".join(f"{p['name']}{'*' if p['required'] else ''}: {p['type']}" for p in row["params"])
        returns = f" -> {row['returns']}" if row["returns"] else ""
        lines.append(f"  {row['name']}({params}){returns}  # {row['summary']}")
    return "\n".join(lines)
