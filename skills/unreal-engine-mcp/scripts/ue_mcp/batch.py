"""Ordered, validated tool-call batches with readback (the route for writes)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .client import UnrealMcpClient


SCHEMA_VERSION = "builtin_mcp.batch/1"
from .protocol import McpError, unwrap_result
from .schema import argument_problems


def load_batch(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL batch: one {"toolset", "tool", "args"?, "readback"?, "expect"?, "label"?} per line."""
    entries = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        try:
            entry = json.loads(text)
        except json.JSONDecodeError as exc:
            raise McpError(f"{path}:{number}: invalid JSON: {exc}") from exc
        if not isinstance(entry, dict):
            raise McpError(f"{path}:{number}: each line must be a JSON object")
        entries.append({**entry, "_line": number})
    return entries


def _expectation_met(expect: Any, actual: Any) -> bool:
    if isinstance(expect, dict) and set(expect) == {"refPath"} and isinstance(actual, str):
        return expect["refPath"] == actual  # Object references also arrive as bare path strings.
    if isinstance(expect, dict) and isinstance(actual, dict):
        return all(key in actual and _expectation_met(value, actual[key]) for key, value in expect.items())
    if isinstance(expect, list) and isinstance(actual, list):
        return len(expect) == len(actual) and all(map(_expectation_met, expect, actual))
    if isinstance(expect, bool) or isinstance(actual, bool):
        return type(expect) is type(actual) and expect == actual
    numbers = (int, float)
    if isinstance(expect, numbers) and isinstance(actual, numbers):
        # UE stores most values as float32: 0.4 reads back as 0.4000000059604645.
        return math.isclose(expect, actual, rel_tol=1e-6, abs_tol=1e-6)
    return expect == actual


def validate_batch(client: UnrealMcpClient, entries: list[dict[str, Any]]) -> list[str]:
    """Check every call and readback against the live schema before anything runs."""
    problems = []
    for entry in entries:
        for step, spec in (("call", entry), ("readback", entry.get("readback"))):
            if spec is None:
                continue
            where = f"line {entry['_line']} {step}"
            if not isinstance(spec, dict) or not spec.get("toolset") or not spec.get("tool"):
                problems.append(f"{where}: needs \"toolset\" and \"tool\"")
                continue
            if not isinstance(spec.get("args", {}), dict):
                problems.append(f"{where}: \"args\" must be an object")
                continue
            try:
                schema = client.find_tool(spec["toolset"], spec["tool"])
            except McpError as exc:
                problems.append(f"{where}: {exc}")
                continue
            if schema is None:
                problems.append(f"{where}: {client.missing_tool_message(spec['toolset'], spec['tool'])}")
                continue
            # UE marks some documented-optional fields required; pass explicit empty values for them.
            issues = argument_problems(schema, spec.get("args") or {})
            if issues:
                problems.append(f"{where}: {spec['tool']}: {'; '.join(issues)}")
        if "expect" in entry and not entry.get("readback"):
            problems.append(f"line {entry['_line']}: \"expect\" needs a \"readback\"")
    return problems


def run_batch(client: UnrealMcpClient, entries: list[dict[str, Any]], *,
              dry_run: bool = False, continue_on_error: bool = False) -> dict[str, Any]:
    """Run calls sequentially in one session; stop at the first failure unless told otherwise.

    Unlike ProgrammaticToolset scripts, each call is a separate request with its own result,
    so earlier successful steps are reported even when a later one fails. Nothing is retried.
    """
    problems = validate_batch(client, entries)
    if problems or dry_run:
        return {"schema_version": SCHEMA_VERSION, "ok": not problems, "validated": not problems, "dry_run": dry_run,
                "problems": problems,
                "planned": [f"{e['toolset']}.{e['tool']}" for e in entries if not problems]}
    results: list[dict[str, Any]] = []
    stopped = False
    for index, entry in enumerate(entries):
        row: dict[str, Any] = {"index": index, "line": entry["_line"], "label": entry.get("label", ""),
                               "tool": f"{entry['toolset']}.{entry['tool']}"}
        if stopped:
            results.append({**row, "status": "skipped"})
            continue
        try:
            row["result"] = unwrap_result(client.call_resolved_tool(entry["toolset"], entry["tool"], entry.get("args") or {}))
            row["status"] = "ok"
        except McpError as exc:
            row.update(status="error", error=str(exc))
        readback = entry.get("readback")
        if row["status"] == "ok" and readback:
            try:
                actual = unwrap_result(client.call_resolved_tool(readback["toolset"], readback["tool"], readback.get("args") or {}))
                row["readback"] = {"tool": f"{readback['toolset']}.{readback['tool']}", "result": actual}
                if "expect" in entry and not _expectation_met(entry["expect"], actual):
                    row.update(status="mismatch", error=f"readback {actual!r} does not match expect {entry['expect']!r}")
            except McpError as exc:
                row.update(status="readback_error", error=str(exc))
        results.append(row)
        stopped = row["status"] != "ok" and not continue_on_error
    counts: dict[str, int] = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"schema_version": SCHEMA_VERSION, "ok": counts.get("ok", 0) == len(results), "validated": True,
            "counts": counts, "results": results}
