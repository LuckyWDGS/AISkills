"""Compact views of toolset schemas."""

from __future__ import annotations

from typing import Any


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
