#!/usr/bin/env python3
"""Re-record the report-contract fixtures from a running UE 5.8+ editor (read-only).

The material and Niagara contract tests replay real collector output stored in
``<skill>/scripts/fixtures``. After an engine upgrade, re-record them, rerun the
contract tests, and update any expectation the new engine legitimately changed.

    python scripts/record_fixtures.py --project MyGame
    python scripts/record_fixtures.py --project MyGame --check    # record to a temp dir and diff only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve().parent
SKILLS = _HERE.parents[1]
for path in (_HERE, SKILLS / "unreal-material-artist" / "scripts", SKILLS / "niagara-vfx-artist" / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ue_mcp.skill_api import builtin_mcp, connect  # noqa: E402
from unreal_material_tools import material_audit  # noqa: E402
from vfx_delivery import niagara_audit  # noqa: E402

# The contract tests assert facts about these UE template assets; keep them in sync.
MATERIALS = ["/Game/LevelPrototyping/Materials/M_PrototypeGrid", "/Game/LevelPrototyping/Materials/MI_PrototypeGrid_Gray"]
NIAGARA = "/Game/LevelPrototyping/Interactable/JumpPad/Assets/NS_JumpPad"
MATERIAL_DIR = SKILLS / "unreal-material-artist" / "scripts" / "fixtures"
NIAGARA_DIR = SKILLS / "niagara-vfx-artist" / "scripts" / "fixtures"


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def strip_module_inputs(raw: dict) -> None:
    """Per-module input lists are unused by the Niagara report and make the fixture several times larger."""
    for emitter in raw["emitters"]:
        for stack in emitter["topology"].values():
            for item in stack if isinstance(stack, list) else [stack]:
                if isinstance(item, dict):
                    for module in item.get("modules", []):
                        module.pop("inputs", None)


def record(project: str | None, material_dir: Path, niagara_dir: Path) -> list[Path]:
    skill_root = SKILLS / "unreal-material-artist"
    module = builtin_mcp()
    client = connect(project=project)
    written: list[Path] = []
    try:
        owner = client.editor_owner()
        source = {"engine": owner.get("engine_version", "unknown"), "project": owner.get("project", project or "unknown"),
                  "captured": date.today().isoformat()}
        for asset in MATERIALS:
            raw = client.run_tool_script(material_audit.build_collect_script(material_audit.object_path(asset)))
            outputs = material_audit.collect_output_connections(module, client, raw["base"])
            stats = material_audit.collect_shader_stats(skill_root, asset, project or owner.get("project"))
            stats.pop("node", None)
            path = material_dir / f"mcp-material-{asset.rsplit('/', 1)[-1]}.json"
            write(path, {"source": source, "asset_path": asset, "raw": raw, "outputs": outputs, "stats": stats})
            written.append(path)
        raw = client.run_tool_script(niagara_audit.build_collect_script(niagara_audit.object_path(NIAGARA)))
        strip_module_inputs(raw)
        path = niagara_dir / f"mcp-niagara-{NIAGARA.rsplit('/', 1)[-1]}.json"
        write(path, {"source": source, "system_path": NIAGARA, "raw": raw})
        written.append(path)
    finally:
        client.close()
    return written


def changed_sections(old: dict, new: dict) -> list[str]:
    """Top-level keys whose content differs, ignoring the capture date."""
    keys = sorted((set(old) | set(new)) - {"source"})
    diffs = [key for key in keys if old.get(key) != new.get(key)]
    if {k: v for k, v in old.get("source", {}).items() if k != "captured"} != \
            {k: v for k, v in new.get("source", {}).items() if k != "captured"}:
        diffs.insert(0, "source")
    return diffs


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=os.environ.get("UE_MCP_PROJECT"), help="Expected project name")
    parser.add_argument("--check", action="store_true", help="Record to a temporary folder and report differences only")
    args = parser.parse_args()
    if not args.check:
        for path in record(args.project, MATERIAL_DIR, NIAGARA_DIR):
            print(f"recorded {path.relative_to(SKILLS)} ({path.stat().st_size // 1024} KB)")
        print("Now run the contract tests: test_material_audit_contract.py, test_niagara_audit_contract.py")
        return 0
    with tempfile.TemporaryDirectory(prefix="ue-fixtures-") as folder:
        fresh = record(args.project, Path(folder) / "material", Path(folder) / "niagara")
        drift = 0
        for path in fresh:
            current = (MATERIAL_DIR if path.parent.name == "material" else NIAGARA_DIR) / path.name
            old = json.loads(current.read_text(encoding="utf-8")) if current.exists() else {}
            sections = changed_sections(old, json.loads(path.read_text(encoding="utf-8")))
            drift += bool(sections)
            print(f"{current.name}: {'unchanged' if not sections else 'differs in ' + ', '.join(sections)}")
        return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
