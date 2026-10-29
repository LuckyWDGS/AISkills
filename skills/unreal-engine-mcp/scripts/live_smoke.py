#!/usr/bin/env python3
"""Read-only live smoke test of the UE skills' tools against a running UE 5.8+ editor.

Runs each tool through its real command line against template content (or the
assets you pass), checks key report fields, and fails if any touched asset's
dirty state changed. Nothing is created, written or saved: material_instance_batch
runs in plan-only mode and the batch step contains reads only.

    python scripts/live_smoke.py --project MyGame
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from ue_mcp import McpError, unwrap_result  # noqa: E402
from ue_mcp.skill_api import connect  # noqa: E402


SKILLS = _HERE.parents[1]
TOOLS = {
    "builtin_mcp": _HERE / "builtin_mcp.py",
    "python_remote": _HERE / "python_remote.py",
    "inspect_blueprint": _HERE / "inspect_blueprint.py",
    "material_audit": SKILLS / "unreal-material-artist" / "tools" / "material_audit.py",
    "material_instance_batch": SKILLS / "unreal-material-artist" / "tools" / "material_instance_batch.py",
    "niagara_audit": SKILLS / "niagara-vfx-artist" / "tools" / "niagara_audit.py",
}
# UE template content (First Person / Level Prototyping); override with flags for other projects.
DEFAULTS = {
    "material": "/Game/LevelPrototyping/Materials/M_PrototypeGrid",
    "instance": "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray",
    "niagara": "/Game/LevelPrototyping/Interactable/JumpPad/Assets/NS_JumpPad",
    "blueprint": "/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter",
}


class CheckFailed(AssertionError):
    pass


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


def run_tool(name: str, *args: str, timeout: float = 300) -> tuple[int, str]:
    env = {**os.environ, "PYTHONUTF8": "1"}
    proc = subprocess.run([sys.executable, str(TOOLS[name]), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, env=env)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def load(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Smoke:
    def __init__(self, args: argparse.Namespace, work: Path) -> None:
        self.args, self.work = args, work
        self.client = connect(project=args.project)
        self.results: list[dict[str, Any]] = []

    def call(self, toolset: str, tool: str, arguments: dict[str, Any]) -> Any:
        return unwrap_result(self.client.call_resolved_tool(toolset, tool, arguments))

    def exists(self, path: str) -> bool:
        return bool(self.call("AssetTools", "exists", {"path": path}))

    def dirty(self, path: str) -> bool:
        return bool(self.call("AssetTools", "is_dirty", {"asset_path": path}))

    def check(self, name: str, assets: list[str], body: Callable[[], str]) -> None:
        started = time.monotonic()
        row: dict[str, Any] = {"check": name}
        missing = [path for path in assets if not self.exists(path)]
        if missing:
            row.update(status="skipped", detail=f"missing asset(s): {missing}")
        else:
            before = {path: self.dirty(path) for path in assets}
            try:
                row.update(status="pass", detail=body())
            except (CheckFailed, McpError, OSError, subprocess.SubprocessError, KeyError, ValueError) as exc:
                row.update(status="fail", detail=f"{type(exc).__name__}: {exc}"[:600])
            changed = [path for path in assets if self.dirty(path) != before[path]]
            if changed:
                row.update(status="fail", detail=f"dirty state changed for {changed}; {row['detail']}")
        row["seconds"] = round(time.monotonic() - started, 1)
        self.results.append(row)
        print(f"[{row['status']:7s}] {name} ({row['seconds']} s) {row['detail']}", flush=True)

    # --- checks -------------------------------------------------------------------------------

    def status(self) -> str:
        code, out = run_tool("builtin_mcp", "status")
        expect(code == 0, out)
        editor = json.loads(out)["editor"]
        if self.args.project:
            expect(editor.get("project", "").lower() == self.args.project.lower(), f"served by {editor.get('project')}")
        return f"{editor.get('project')} {editor.get('engine_version')} session reuse ok"

    def brief(self) -> str:
        code, out = run_tool("builtin_mcp", "describe-toolset", "MaterialTools", "--brief")
        expect(code == 0 and "get_expressions(" in out, out[:300])
        return f"{len(out)} bytes"

    def batch_reads(self) -> str:
        plan = self.work / "reads.jsonl"
        lines = [
            {"label": "pie", "toolset": "EditorAppToolset", "tool": "IsPIERunning", "args": {}},
            {"label": "exists", "toolset": "AssetTools", "tool": "exists", "args": {"path": self.args.material},
             "readback": {"toolset": "AssetTools", "tool": "exists", "args": {"path": self.args.material}}, "expect": True},
        ]
        plan.write_text("\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8")
        code, out = run_tool("builtin_mcp", "batch", str(plan))
        result = json.loads(out)
        expect(code == 0 and result["ok"], out[:300])
        return f"{result['counts']}"

    def remote(self) -> str:
        args = ["--project", self.args.project, "nodes"] if self.args.project else ["nodes"]
        code, out = run_tool("python_remote", *args)
        expect(code == 0, out[:300])
        return f"{len(json.loads(out))} editor(s) answer Remote Execution"

    def niagara(self) -> str:
        out_file = self.work / "niagara.json"
        code, out = run_tool("niagara_audit", self.args.niagara, "--out", str(out_file))
        expect(code == 0, out[-400:])
        report = load(out_file)
        expect(report.get("schema_version", "").startswith("niagara_audit/"), "missing schema_version")
        expect(report["emitters"], "no emitters")
        return f"{len(report['emitters'])} emitters, {len(report['warnings'])} warnings"

    def material(self, source: str) -> str:
        out_file = self.work / f"material-{source}.json"
        extra = ["--project", self.args.project] if self.args.project else []
        code, out = run_tool("material_audit", self.args.material, "--graph-source", source, "--out", str(out_file), *extra)
        expect(code == 0, out[-400:])
        report = load(out_file)
        expect(report.get("schema_version", "").startswith("material_audit/"), "missing schema_version")
        info = report["material_info"]
        expect(info["num_expressions"] > 0 and report["graph_summary"]["output_chains"], "empty graph or no outputs")
        stats = report["analysis"]["shader_stats"]
        return (f"{info['num_expressions']} nodes, {len(report['graph_summary']['dead_nodes'])} dead, "
                f"stats {'ok' if stats.get('ready') else stats.get('error', 'n/a')[:60]}")

    def instance_plan(self) -> str:
        probe = self.args.instance.rsplit("/", 1)[0] + "/MI_LiveSmoke_PlanOnly"
        expect(not self.exists(probe), f"{probe} exists; remove it or pass a different --instance folder")
        spec = self.work / "mi-spec.json"
        spec.write_text(json.dumps({"parent_path": self.args.material, "instances": [{"path": probe, "params": []}]}),
                        encoding="utf-8")
        out_file = self.work / "mi.json"
        extra = ["--project", self.args.project] if self.args.project else []
        code, out = run_tool("material_instance_batch", str(spec), "--out", str(out_file), *extra)  # no --execute
        report = load(out_file)
        expect(code == 0 and report["status"] == "planned", f"{report.get('status')} {report.get('problems')}")
        expect(not self.exists(probe), "plan-only run created an asset")
        return "planned, nothing created"

    def blueprint(self) -> str:
        out_dir = self.work / "blueprint"
        code, out = run_tool("inspect_blueprint", self.args.blueprint, "--out", str(out_dir))
        expect(code == 0, out[-400:])
        result = load(out_dir / "result.json")
        expect(result.get("passed") is True, result.get("error", "capture failed"))
        return "capture passed, dirty unchanged"

    def run(self) -> int:
        a = self.args
        if self.client.pie_running():
            print("Play-In-Editor is running: asset queries report wrong results during PIE "
                  "(existing assets look missing). Stop PIE and run the smoke again.")
            self.client.close()
            return 2
        self.check("builtin_mcp status", [], self.status)
        self.check("describe-toolset --brief", [], self.brief)
        self.check("batch (reads + readback)", [a.material], self.batch_reads)
        self.check("python_remote nodes", [], self.remote)
        self.check("niagara_audit", [a.niagara], self.niagara)
        self.check("material_audit (remote graph)", [a.material], lambda: self.material("remote"))
        if a.full:
            self.check("material_audit (MCP graph)", [a.material], lambda: self.material("mcp"))
        self.check("material_instance_batch (plan only)", [a.material, a.instance], self.instance_plan)
        self.check("inspect_blueprint", [a.blueprint], self.blueprint)
        self.client.close()
        failed = [row for row in self.results if row["status"] == "fail"]
        print(f"\n{len(self.results) - len(failed)}/{len(self.results)} checks without failure")
        return 1 if failed else 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=os.environ.get("UE_MCP_PROJECT"), help="Expected project name")
    for key, value in DEFAULTS.items():
        parser.add_argument(f"--{key}", default=value)
    parser.add_argument("--full", action="store_true", help="Also run the slow MCP-route material audit")
    parser.add_argument("--out", help="Write per-check results as JSON")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ue-live-smoke-") as folder:
        smoke = Smoke(args, Path(folder))
        code = smoke.run()
    if args.out:
        Path(args.out).write_text(json.dumps({"project": args.project, "results": smoke.results}, indent=2) + "\n",
                                  encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
