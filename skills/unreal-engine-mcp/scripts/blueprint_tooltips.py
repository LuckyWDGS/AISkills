#!/usr/bin/env python3
"""Write and read back Blueprint function/variable descriptions (hover tooltips) and function categories.

Needs the MCPBlueprintMetadata editor plugin (install_blueprint_metadata_plugin.py); stock UE 5.8 has no
write route. Without --write it only reads the current values and lists members without one.

    python scripts/blueprint_tooltips.py /Game/Path/BP_Feature --project MyGame
    python scripts/blueprint_tooltips.py /Game/Path/BP_Feature --spec tooltips.json --write --project MyGame

Spec (JSON, UTF-8):
    {"functions": {"UpdatePreview": {"tooltip": "...", "category": "Feature|Preview"}, "Log": "tooltip only"},
     "variables": {"ThrowSpeed": "..."},
     "locals": {"UpdatePreview": {"LandingHit": "..."}}}

--write marks the Blueprint modified; compile it afterwards (the tooltip reaches call nodes on compile)
and leave saving to the user unless they asked for it.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent

SCRIPT = r"""
import json, unreal
def _codex():
    lib = getattr(unreal, "MCPBlueprintMetadataLibrary", None)
    if lib is None:
        print("CODEX_TOOLTIPS " + json.dumps({"plugin": False}))
        return
    L = unreal.BlueprintEditorLibrary
    bp = unreal.load_asset(__ASSET__)
    spec, write = json.loads(__SPEC__), __WRITE__
    failed = []
    if write:
        for name, value in spec.get("functions", {}).items():
            value = {"tooltip": value} if isinstance(value, str) else value
            if "tooltip" in value and not lib.set_function_tooltip(bp, name, value["tooltip"]):
                failed.append("function " + name)
            if "category" in value and not lib.set_function_category(bp, name, value["category"]):
                failed.append("function category " + name)
        for name, text in spec.get("variables", {}).items():
            if not lib.set_member_variable_tooltip(bp, name, text):
                failed.append("variable " + name)
        for function, names in spec.get("locals", {}).items():
            for name, text in names.items():
                if not lib.set_local_variable_tooltip(bp, function, name, text):
                    failed.append("local " + function + "." + name)
    functions = [str(f.get_editor_property("name")) for f in L.list_functions(bp) if f.get_editor_property("is_implemented")]
    functions = [f for f in functions if f != "UserConstructionScript"]
    variables = [str(v) for v in L.list_member_variable_names(bp) if "/" not in str(v)]  # inherited ones come as paths
    state = {"plugin": True, "failed": failed,
             "functions": {f: {"tooltip": lib.get_function_tooltip(bp, f), "category": lib.get_function_category(bp, f)} for f in functions},
             "variables": {v: lib.get_member_variable_tooltip(bp, v) for v in variables},
             "locals": {f: {n: lib.get_local_variable_tooltip(bp, f, n) for n in names} for f, names in spec.get("locals", {}).items()}}
    print("CODEX_TOOLTIPS " + json.dumps(state, ensure_ascii=False))
_codex()
"""


def run(asset: str, spec: dict, write: bool, project: str | None) -> dict:
    script = (SCRIPT.replace("__ASSET__", json.dumps(asset.split(".")[0]))
              .replace("__SPEC__", repr(json.dumps(spec, ensure_ascii=False))).replace("__WRITE__", "True" if write else "False"))
    command = [sys.executable, str(_HERE / "python_remote.py")] + (["--project", project] if project else [])
    proc = subprocess.run([*command, "exec", "--code", script], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env={**os.environ, "PYTHONUTF8": "1"})
    payload = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else {}
    for row in payload.get("output") or []:
        text = str(row.get("output", ""))
        if text.startswith("CODEX_TOOLTIPS "):
            return json.loads(text[len("CODEX_TOOLTIPS "):])
    raise RuntimeError(f"tooltip script failed: {(payload.get('result') or proc.stderr or proc.stdout)[:400]}")


def report(asset: str, state: dict) -> dict:
    if not state.get("plugin"):
        return {"blueprint": asset, "plugin": False,
                "message": "MCPBlueprintMetadata is not loaded; run install_blueprint_metadata_plugin.py and restart the editor"}
    return {"blueprint": asset, "plugin": True, "failed": state["failed"],
            "missing": {"functions": sorted(f for f, v in state["functions"].items() if not v["tooltip"]),
                        "variables": sorted(v for v, text in state["variables"].items() if not text)},
            "state": {k: state[k] for k in ("functions", "variables", "locals")}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("blueprint")
    parser.add_argument("--spec", type=Path, help="JSON spec of tooltips/categories to write")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--project", default=os.environ.get("UE_MCP_PROJECT"))
    args = parser.parse_args(argv)
    if args.write and not args.spec:
        parser.error("--write needs --spec")
    spec = json.loads(args.spec.read_text(encoding="utf-8")) if args.spec else {}
    result = report(args.blueprint, run(args.blueprint, spec, args.write, args.project))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["plugin"]:
        return 2
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
