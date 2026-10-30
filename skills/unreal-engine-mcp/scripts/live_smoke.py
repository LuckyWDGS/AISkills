#!/usr/bin/env python3
"""Live smoke test of the UE skills' tools against a running UE 5.8+ editor.

Runs each tool through its real command line against template content (or the
assets you pass), checks key report fields, and fails if any touched asset's
dirty state changed. By default nothing is created, written or saved:
material_instance_batch runs in plan-only mode and the batch step contains reads only.

--write adds the write paths in a scratch folder (default /Game/CodexTemp/LiveSmokeWrite,
which must not exist yet): a recipe build, an MI batch, a texture import fix, a graph
refactor on a candidate and a Niagara plan apply, each read back, then the folder is deleted.

    python scripts/live_smoke.py --project MyGame
    python scripts/live_smoke.py --project MyGame --write
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
    "capture": _HERE / "capture.py",
    "material_audit": SKILLS / "unreal-material-artist" / "tools" / "material_audit.py",
    "material_domain_audit": SKILLS / "unreal-material-artist" / "tools" / "material_domain_audit.py",
    "texture_import_audit": SKILLS / "unreal-material-artist" / "tools" / "texture_import_audit.py",
    "shader_permutation_report": SKILLS / "unreal-material-artist" / "tools" / "shader_permutation_report.py",
    "live_asset_verify": SKILLS / "niagara-vfx-artist" / "tools" / "live_asset_verify.py",
    "material_instance_batch": SKILLS / "unreal-material-artist" / "tools" / "material_instance_batch.py",
    "niagara_audit": SKILLS / "niagara-vfx-artist" / "tools" / "niagara_audit.py",
    "material_toolset_builder": SKILLS / "unreal-material-artist" / "tools" / "material_toolset_builder.py",
    "texture_import_fix": SKILLS / "unreal-material-artist" / "tools" / "texture_import_fix.py",
    "graph_refactor_apply": SKILLS / "unreal-material-artist" / "tools" / "graph_refactor_apply.py",
    "niagara_asset_assistant": SKILLS / "niagara-vfx-artist" / "tools" / "niagara_asset_assistant.py",
}
# UE template content (First Person / Level Prototyping); override with flags for other projects.
DEFAULTS = {
    "material": "/Game/LevelPrototyping/Materials/M_PrototypeGrid",
    "instance": "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray",
    "niagara": "/Game/LevelPrototyping/Interactable/JumpPad/Assets/NS_JumpPad",
    "blueprint": "/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter",
    "texture": "/Game/Characters/Mannequins/Textures/Manny/T_Manny_01_BN",
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

    def domain(self) -> str:
        out_file = self.work / "domain.json"
        extra = ["--project", self.args.project] if self.args.project else []
        code, out = run_tool("material_domain_audit", self.args.material, "--graph-source", "remote",
                             "--out", str(out_file), *extra)
        expect(code == 0, out[-400:])
        report = load(out_file)
        contract = report["domain_contract"]
        expect(contract["domain"] and contract["blend_mode"] and contract["shading_models"], f"empty contract {contract}")
        return f"{contract['domain']} / {contract['blend_mode']} / {','.join(contract['shading_models'])}"

    def texture(self) -> str:
        out_file = self.work / "texture.json"
        code, out = run_tool("texture_import_audit", self.args.texture, "--role", "normal", "--out", str(out_file))
        expect(code == 0, out[-400:])
        row = load(out_file)["textures"][0]
        expect(row["found"] and row["width"] > 0 and row["compression_settings"], f"empty texture row {row}")
        return f"{row['width']}x{row['height']} {row['compression_settings']} sRGB={row['srgb']}"

    def permutations(self) -> str:
        out_file = self.work / "permutations.json"
        folder = self.args.material.rsplit("/", 1)[0]
        code, out = run_tool("shader_permutation_report", "--path-prefix", folder, "--out", str(out_file))
        expect(code == 0, out[-400:])
        summary = load(out_file)["summary"]
        return f"{summary['groups']} group(s), {summary['bases']} base(s)"

    def live_verify(self) -> str:
        out_file = self.work / "live-verify.json"
        code, out = run_tool("live_asset_verify", "--texture-asset-path", self.args.texture, "--material-path",
                             self.args.material, "--renderer-path", self.args.niagara, "--source-policy", "ue-only",
                             "--out", str(out_file))
        expect(code == 0, out[-400:])
        report = load(out_file)
        expect(report["texture_asset_exists"] and report["material_exists"] and report["renderer_exists"],
               "texture, material or renderer not found")
        return f"renderer materials: {report['renderer_material_path'][:80]}"

    def capture(self) -> str:
        camera = lambda: unwrap_result(self.client.call_resolved_tool("EditorAppToolset", "GetCameraTransform", {}))
        before = camera()
        code, out = run_tool("capture", "asset", self.args.material, "--out-dir", str(self.work / "capture"))
        expect(code == 0, out[-400:])
        location = before["location"]
        pose = f"{location['x']},{location['y']},{location['z'] + 100},-15,0,0"
        code, out = run_tool("capture", "viewport", f"--pose={pose}", "--out-dir", str(self.work / "capture"))
        expect(code == 0, out[-400:])
        frame = load(Path(out.strip().splitlines()[-1]))["frames"][0]
        expect(camera() == before, "posed viewport capture moved the user's viewport camera")
        return f"thumbnail + {frame['width']}x{frame['height']} frame, camera unchanged"

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

    # --- write checks (--write) ----------------------------------------------------------------

    def scratch(self, name: str) -> str:
        return f"{self.args.scratch_folder.rstrip('/')}/{name}"

    @staticmethod
    def ref(path: str) -> dict[str, str]:
        return {"refPath": f"{path}.{path.rsplit('/', 1)[-1]}"}

    def project_args(self) -> list[str]:
        return ["--project", self.args.project] if self.args.project else []

    def recipe_build(self) -> str:
        report_file = self.work / "recipe-build.json"
        code, out = run_tool("material_toolset_builder", "recipe", "dissolve_edge", "--root", str(self.work),
                             "--folder-path", self.args.scratch_folder, "--asset-name", "M_LiveSmoke", "--execute",
                             "--build-report-out", str(report_file), *self.project_args())
        report = load(report_file)
        expect(code == 0 and report["status"] == "applied", f"{report.get('status')} {report.get('problems')} {out[-300:]}")
        material = self.scratch("M_LiveSmoke")
        expect(self.exists(material) and not self.dirty(material), "material missing or left unsaved")
        return f"{len(report.get('steps', []))} steps applied and saved"

    def instance_write(self) -> str:
        material, instance = self.scratch("M_LiveSmoke"), self.scratch("MI_LiveSmoke")
        params = self.call("MaterialInstanceTools", "list_parameters", {"material": self.ref(material)}) or []
        scalar = next((row["name"] for row in params if str(row.get("type", "")).lower() == "scalar"), "")
        spec = self.work / "mi-write.json"
        values = [{"name": scalar, "type": "scalar", "value": 0.37}] if scalar else []
        spec.write_text(json.dumps({"parent_path": material, "instances": [{"path": instance, "params": values}]}), encoding="utf-8")
        out_file = self.work / "mi-write-report.json"
        code, out = run_tool("material_instance_batch", str(spec), "--execute", "--out", str(out_file), *self.project_args())
        report = load(out_file)
        expect(code == 0 and report["status"] == "applied", f"{report.get('status')} {report.get('problems')}")
        if scalar:
            value = self.call("MaterialInstanceTools", "get_scalar_parameter", {"instance": self.ref(instance), "name": scalar})
            expect(abs(float(value) - 0.37) < 1e-4, f"{scalar} reads back {value}")
        return f"MI created, {scalar or 'no scalar parameter'} read back"

    def texture_write(self) -> str:
        from PIL import Image  # provided by the material skill's requirements

        source = self.work / "T_LiveSmokeMask.png"
        Image.new("RGBA", (64, 64), (255, 128, 0, 255)).save(source)
        self.call("TextureTools", "import_file", {"folder_path": self.args.scratch_folder, "asset_name": "T_LiveSmokeMask",
                                                  "source_file": str(source)})
        texture = self.scratch("T_LiveSmokeMask")
        expect(self.exists(texture), "import_file did not create the texture")
        out_file = self.work / "texture-fix.json"
        code, out = run_tool("texture_import_fix", texture, "--role", "mask", "--apply", "--root", str(self.work),
                             "--out", str(out_file), *self.project_args())
        report = load(out_file)
        expect(code == 0 and report["status"] in ("applied", "no_changes"), f"{report.get('status')} {report.get('problems')}")
        props = self.call("ObjectTools", "get_properties", {"instance": self.ref(texture), "properties": ["sRGB"]})
        expect(props.get("sRGB") is False, f"sRGB reads back {props.get('sRGB')}")
        return f"{report['status']}, sRGB=false read back"

    def emissive_source(self, material: str) -> str:
        value = self.call("MaterialTools", "get_property_input", {"material": self.ref(material), "material_property": "MP_EmissiveColor"})
        expression = (value or {}).get("expression")
        return str(expression.get("refPath") if isinstance(expression, dict) else expression or "")

    def refactor_write(self) -> str:
        material = self.scratch("M_LiveSmoke")
        before = self.emissive_source(material)
        spec = self.work / "refactor-patch.json"
        spec.write_text(json.dumps({"target_material": material, "operations": ["add_fresnel_layer"]}), encoding="utf-8")
        out_file = self.work / "refactor.json"
        code, out = run_tool("graph_refactor_apply", "--root", str(self.work), "--patch-spec", str(spec), "--execute",
                             "--candidate-path", self.scratch("M_LiveSmoke_Candidate"),
                             "--backup-path", self.scratch("M_LiveSmoke_Backup"), "--out", str(out_file),
                             *self.project_args(), timeout=900)
        ue = load(out_file).get("ue_apply") or {}
        operations = ue.get("operations") or []
        expect(code == 0 and ue.get("saved") and operations and all(row["success"] for row in operations),
               f"{ue.get('error')} {[row.get('error') for row in operations]}")
        expect(self.emissive_source(material) == before, "the original material's emissive input changed")
        expect("Add" in self.emissive_source(self.scratch("M_LiveSmoke_Candidate")).rsplit(":", 1)[-1] or not before,
               "the candidate emissive input is not the new Fresnel chain")
        return "candidate patched and saved, original untouched"

    def niagara_write(self) -> str:
        system = self.scratch("NS_LiveSmoke")
        summary = self.call("NiagaraToolset_System", "GetSystemSummary", {"system": self.ref(self.args.niagara)})
        plan = {"tool": "niagara_asset_assistant", "effect_name": "LiveSmoke", "target_system": system, "operations": [
            {"op": "duplicate_asset", "source": self.args.niagara, "target": system},
            {"op": "set_niagara_system_props", "system_path": system, "fixed_bounds": "-25,-25,-25,25,25,75", "warmup_tick_count": 1},
            {"op": "add_ribbon_renderer", "system_path": system, "emitter_name": summary["emitters"][0]["emitterName"],
             "material_path": "/Niagara/DefaultAssets/DefaultRibbonMaterial", "facing_mode": "Screen"},
            {"op": "save_assets", "asset_paths": [system]},
        ]}
        plan_file, out_file = self.work / "niagara-plan.json", self.work / "niagara-apply.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")
        code, out = run_tool("niagara_asset_assistant", "--root", str(self.work), "apply", "--plan", str(plan_file),
                             "--execute", "--out", str(out_file))
        report = load(out_file)
        expect(code == 0 and report["status"] == "applied", f"{report['status']} {[row.get('error') for row in report['operations']]}")
        audit_file = self.work / "niagara-write-audit.json"
        code, out = run_tool("niagara_audit", system, "--out", str(audit_file))
        expect(code == 0, out[-400:])
        audit = load(audit_file)
        ribbons = [row for emitter in audit["emitters"] for row in emitter["renderers"] if "Ribbon" in row["class_name"]]
        expect(audit["system"]["fixed_bounds"] and ribbons and ribbons[-1]["material_path"], "the audit does not show the applied edits")
        return f"{len(report['operations'])} operations applied; audit shows bounds and the ribbon"

    def cleanup(self) -> str:
        expect(self.call("AssetTools", "delete", {"path": self.args.scratch_folder}), "delete returned false")
        expect(not self.exists(self.args.scratch_folder), "the scratch folder still exists")
        return f"{self.args.scratch_folder} deleted"

    def run_writes(self) -> None:
        a = self.args
        if self.exists(a.scratch_folder):
            row = {"check": "write setup", "status": "fail", "seconds": 0,
                   "detail": f"{a.scratch_folder} already exists; delete it or pass --scratch-folder"}
            self.results.append(row)
            print(f"[fail   ] write setup {row['detail']}", flush=True)
            return
        self.call("AssetTools", "create_folder", {"path": a.scratch_folder})
        self.check("material_toolset_builder recipe --execute", [], self.recipe_build)
        self.check("material_instance_batch --execute", [a.material], self.instance_write)
        self.check("texture import + texture_import_fix --apply", [], self.texture_write)
        self.check("graph_refactor_apply --execute", [], self.refactor_write)
        self.check("niagara_asset_assistant apply --execute", [a.niagara], self.niagara_write)
        self.check("scratch cleanup", [], self.cleanup)

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
        self.check("material_domain_audit", [a.material], self.domain)
        self.check("texture_import_audit", [a.texture], self.texture)
        self.check("shader_permutation_report", [a.material], self.permutations)
        self.check("live_asset_verify", [a.texture, a.material, a.niagara], self.live_verify)
        self.check("capture (thumbnail + posed viewport)", [a.material], self.capture)
        self.check("material_instance_batch (plan only)", [a.material, a.instance], self.instance_plan)
        self.check("inspect_blueprint", [a.blueprint], self.blueprint)
        if a.write:
            self.run_writes()
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
    parser.add_argument("--write", action="store_true", help="Also run the write paths in --scratch-folder, then delete it")
    parser.add_argument("--scratch-folder", default="/Game/CodexTemp/LiveSmokeWrite")
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
