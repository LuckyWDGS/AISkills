#!/usr/bin/env python3
"""Read-only report of a Level Sequence: settings, bindings, tracks, sections, keys, camera cuts, lint.

    python scripts/sequence_inspect.py /Game/Cinematics/LS_Intro --out <dir> [--strict]

Uses official MCP first; stock Python reads only the documented metadata gaps.
Nothing is opened, edited or saved.
Lint rules: no_camera_cuts, cut_without_camera, cut_overlap, cut_gap, cut_unbounded,
unused_camera, empty_track, empty_section, animation_missing, key_outside_range.
--strict exits 1 when an error or warning remains.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from sequencer_tools.inspect import lint, mcp_dump, summarize  # noqa: E402

SCHEMA_VERSION = "sequence_inspect/1"


def dump_sequence(asset: str, project: str | None) -> dict:
    from sequencer_tools.editor import Editor
    editor = Editor(project)
    try:
        return mcp_dump(editor, asset)
    finally:
        editor.close()


def render_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [f"# Sequence: {report['sequence']}", "",
             f"- {s['fps']} fps, frames {s['playback'][0]}-{s['playback'][1]} ({s['seconds']} s)",
             f"- Cameras: {', '.join(s['cameras']) or 'none'}", "", "## Camera cuts", ""]
    lines += [f"- {c['start']}-{c['end']}: {c['camera']}" for c in s["cuts"]] or ["- none"]
    lines += ["", "## Bindings", ""] + [f"- {b['name']}: {', '.join(b['tracks']) or 'no tracks'}" for b in s["bindings"]]
    lines += ["", f"## Lint ({'passed' if report['passed'] else 'failed'})", ""]
    lines += [f"- [{f['severity']}] {f['rule']}: {f['message']}" for f in report["findings"]] or ["- clean"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sequence")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--project", default=os.environ.get("UE_MCP_PROJECT"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    dump = dump_sequence(args.sequence, args.project)
    findings = lint(dump)
    report = {"tool": "sequence_inspect", "schema_version": SCHEMA_VERSION, "sequence": dump["sequence"],
              "summary": summarize(dump), "findings": findings,
              "passed": not any(f["severity"] in ("error", "warning") for f in findings), "dump": dump}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "inspect.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out / "inspect.md").write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    return 1 if args.strict and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
