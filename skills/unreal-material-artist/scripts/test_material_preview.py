from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import material_preview
from unreal_material_tools.core import save_json


class FakeBridgeClient:
    responses: list[object] = []
    scripts: list[str] = []

    def __init__(self, skill_root: Path, project: str | None = None, endpoint: str | None = None, timeout_seconds: int = 120) -> None:
        self.skill_root = skill_root
        self.project = project
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def ping(self) -> dict[str, object]:
        return {"ready": True}

    def exec_json(self, script_text: str, *, no_preflight: bool = False) -> object:
        FakeBridgeClient.scripts.append(script_text)
        if not FakeBridgeClient.responses:
            raise AssertionError("FakeBridgeClient had no queued response.")
        return FakeBridgeClient.responses.pop(0)


def write_registry(root: Path, payload: dict[str, object]) -> Path:
    path = root / ".codex" / "session" / "transient-preview-registry.json"
    save_json(path, payload)
    return path


def run_main(args: list[str], responses: list[object] | None = None) -> tuple[int, str, str]:
    FakeBridgeClient.responses = list(responses or [])
    FakeBridgeClient.scripts = []
    stdout = StringIO()
    stderr = StringIO()
    with patch.object(material_preview, "BridgeClient", FakeBridgeClient):
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = material_preview.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class MaterialPreviewTransientCliTests(unittest.TestCase):
    def test_transient_list_writes_live_probe_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(
                root,
                {
                    "version": 1,
                    "updated_at": "2026-05-20T00:00:00+00:00",
                    "entries": [
                        {
                            "key": "sprite|/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "carrier": "sprite",
                            "template_system": "/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "transient_name": "NS_CodexPreview_Transient_sprite_NS_Toolset_ModuleSmoke",
                            "transient_system_path": "/Engine/Transient.NS_CodexPreview_Transient_sprite_NS_Toolset_ModuleSmoke",
                            "created_at": "2026-05-20T00:00:00+00:00",
                            "preview_count": 2,
                            "last_material_path": "/Game/VFX/M_Test",
                            "last_report_path": "D:/preview.json",
                            "last_preview_png": "D:/preview.png",
                            "last_source_tool": "flipbook_ue_pipeline.preview",
                            "last_used_at": "2026-05-20T00:00:00+00:00",
                            "last_live_exists": True,
                        }
                    ],
                },
            )
            code, stdout, stderr = run_main(
                [
                    "transient",
                    "list",
                    "--root",
                    str(root),
                    "--project",
                    "DummyProject",
                    "--markdown",
                ],
                responses=[
                    [
                        {
                            "key": "sprite|/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "transient_system_path": "/Engine/Transient.NS_CodexPreview_Transient_sprite_NS_Toolset_ModuleSmoke",
                            "exists": True,
                            "class": "/Script/Niagara.NiagaraSystem",
                            "renderer_count": 3,
                        }
                    ]
                ],
            )
            self.assertEqual(code, 0, stderr)
            report_path = Path(stdout.strip().splitlines()[-1])
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["entry_count"], 1)
            self.assertTrue(report["entries"][0]["live_probe"]["exists"])
            self.assertIn("renderer_count", report["entries"][0]["live_probe"])
            self.assertTrue(any("renderer_count" in script for script in FakeBridgeClient.scripts))

    def test_transient_recycle_preserves_last_preview_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = write_registry(
                root,
                {
                    "version": 1,
                    "updated_at": "2026-05-20T00:00:00+00:00",
                    "entries": [
                        {
                            "key": "sprite|/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "carrier": "sprite",
                            "template_system": "/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "transient_name": "NS_CodexPreview_Transient_sprite_NS_Toolset_ModuleSmoke",
                            "transient_system_path": "/Engine/Transient.NS_CodexPreview_Transient_sprite_NS_Toolset_ModuleSmoke",
                            "created_at": "2026-05-20T00:00:00+00:00",
                            "preview_count": 2,
                            "last_material_path": "/Game/VFX/M_Test",
                            "last_report_path": "D:/preview.json",
                            "last_preview_png": "D:/preview.png",
                            "last_source_tool": "flipbook_ue_pipeline.preview",
                            "last_used_at": "2026-05-20T00:00:00+00:00",
                            "last_live_exists": True,
                        }
                    ],
                },
            )
            code, stdout, stderr = run_main(
                [
                    "transient",
                    "recycle",
                    "--root",
                    str(root),
                    "--project",
                    "DummyProject",
                ],
                responses=[
                    [
                        {
                            "key": "sprite|/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "carrier": "sprite",
                            "template_system": "/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "transient_name": "NS_CodexPreview_Transient_sprite_NS_Toolset_ModuleSmoke",
                            "transient_system_path": "/Engine/Transient.NS_CodexPreview_Transient_sprite_NS_Toolset_ModuleSmoke",
                            "success": True,
                            "reused_existing": True,
                            "error": "",
                        }
                    ]
                ],
            )
            self.assertEqual(code, 0, stderr)
            report_path = Path(stdout.strip().splitlines()[-1])
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["results"][0]["success"])
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            entry = registry["entries"][0]
            self.assertEqual(entry["preview_count"], 2)
            self.assertEqual(entry["last_material_path"], "/Game/VFX/M_Test")
            self.assertEqual(entry["last_report_path"], "D:/preview.json")
            self.assertEqual(entry["last_preview_png"], "D:/preview.png")
            self.assertIn("last_recycled_at", entry)

    def test_transient_recycle_all_handles_every_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(
                root,
                {
                    "version": 1,
                    "updated_at": "2026-05-20T00:00:00+00:00",
                    "entries": [
                        {
                            "key": "sprite|/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "carrier": "sprite",
                            "template_system": "/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "transient_name": "NS_CodexPreview_Transient_sprite_NS_Toolset_ModuleSmoke",
                            "transient_system_path": "/Engine/Transient.NS_CodexPreview_Transient_sprite_NS_Toolset_ModuleSmoke",
                            "created_at": "2026-05-20T00:00:00+00:00",
                            "preview_count": 1,
                        },
                        {
                            "key": "ribbon|/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "carrier": "ribbon",
                            "template_system": "/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "transient_name": "NS_CodexPreview_Transient_ribbon_NS_Toolset_ModuleSmoke",
                            "transient_system_path": "/Engine/Transient.NS_CodexPreview_Transient_ribbon_NS_Toolset_ModuleSmoke",
                            "created_at": "2026-05-20T00:00:00+00:00",
                            "preview_count": 1,
                        },
                    ],
                },
            )
            code, stdout, stderr = run_main(
                [
                    "transient",
                    "recycle-all",
                    "--root",
                    str(root),
                    "--project",
                    "DummyProject",
                ],
                responses=[
                    [
                        {
                            "key": "sprite|/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "carrier": "sprite",
                            "template_system": "/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "transient_name": "NS_CodexPreview_Transient_sprite_NS_Toolset_ModuleSmoke",
                            "transient_system_path": "/Engine/Transient.NS_CodexPreview_Transient_sprite_NS_Toolset_ModuleSmoke",
                            "success": True,
                            "reused_existing": True,
                            "error": "",
                        },
                        {
                            "key": "ribbon|/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "carrier": "ribbon",
                            "template_system": "/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "transient_name": "NS_CodexPreview_Transient_ribbon_NS_Toolset_ModuleSmoke",
                            "transient_system_path": "/Engine/Transient.NS_CodexPreview_Transient_ribbon_NS_Toolset_ModuleSmoke",
                            "success": True,
                            "reused_existing": True,
                            "error": "",
                        },
                    ]
                ],
            )
            self.assertEqual(code, 0, stderr)
            report_path = Path(stdout.strip().splitlines()[-1])
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(len(report["results"]), 2)
            self.assertTrue(all(item["success"] for item in report["results"]))

    def test_transient_prune_dry_run_and_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = write_registry(
                root,
                {
                    "version": 1,
                    "updated_at": "2026-05-20T00:00:00+00:00",
                    "entries": [
                        {
                            "key": "active|probe",
                            "carrier": "sprite",
                            "template_system": "/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "transient_name": "NS_CodexPreview_Transient_ActiveProbe",
                            "transient_system_path": "/Engine/Transient.NS_CodexPreview_Transient_ActiveProbe",
                            "created_at": "2026-05-20T00:00:00+00:00",
                            "preview_count": 1,
                        },
                        {
                            "key": "stale|probe",
                            "carrier": "sprite",
                            "template_system": "/Game/CodexTemp/ToolsetRegistrySmoke/NS_Toolset_ModuleSmoke",
                            "transient_name": "NS_CodexPreview_Transient_StaleProbe",
                            "transient_system_path": "/Engine/Transient.NS_CodexPreview_Transient_StaleProbe",
                            "created_at": "2026-05-20T00:00:00+00:00",
                            "preview_count": 0,
                        },
                    ],
                },
            )
            probe_payload = [
                {
                    "key": "active|probe",
                    "transient_system_path": "/Engine/Transient.NS_CodexPreview_Transient_ActiveProbe",
                    "exists": True,
                    "class": "/Script/Niagara.NiagaraSystem",
                    "renderer_count": 3,
                },
                {
                    "key": "stale|probe",
                    "transient_system_path": "/Engine/Transient.NS_CodexPreview_Transient_StaleProbe",
                    "exists": False,
                    "class": "",
                    "renderer_count": 0,
                },
            ]

            code, stdout, stderr = run_main(
                [
                    "transient",
                    "prune",
                    "--root",
                    str(root),
                    "--project",
                    "DummyProject",
                    "--markdown",
                ],
                responses=[probe_payload],
            )
            self.assertEqual(code, 0, stderr)
            dry_run_report = json.loads(Path(stdout.strip().splitlines()[-1]).read_text(encoding="utf-8"))
            self.assertTrue(dry_run_report["dry_run"])
            self.assertEqual(dry_run_report["pruned_count"], 1)
            registry_after_dry_run = json.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(len(registry_after_dry_run["entries"]), 2)

            code, stdout, stderr = run_main(
                [
                    "transient",
                    "prune",
                    "--root",
                    str(root),
                    "--project",
                    "DummyProject",
                    "--apply",
                ],
                responses=[probe_payload],
            )
            self.assertEqual(code, 0, stderr)
            apply_report = json.loads(Path(stdout.strip().splitlines()[-1]).read_text(encoding="utf-8"))
            self.assertFalse(apply_report["dry_run"])
            self.assertEqual(apply_report["pruned_count"], 1)
            registry_after_apply = json.loads(registry_path.read_text(encoding="utf-8"))
            keys = [item["key"] for item in registry_after_apply["entries"]]
            self.assertEqual(keys, ["active|probe"])


class MaterialPreviewScriptTests(unittest.TestCase):
    def test_niagara_preview_script_pins_seed_and_reinitializes(self) -> None:
        script = material_preview.build_niagara_preview_script(
            material_path="/Game/Materials/M_Test",
            carrier="sprite",
            width=256,
            height=256,
            fov=35.0,
            out_png="D:/preview.png",
            sim_time=1.0,
            template_system="/Niagara/DefaultAssets/DefaultSystem.DefaultSystem",
            emitter_name_hint=None,
            subuv_grid=None,
            background_preset="neutral",
            exposure_bias=0.0,
            light_rig="studio",
        )

        self.assertIn("set_random_seed_offset(0)", script)
        self.assertIn("set_editor_property('determinism', True)", script)
        self.assertIn("set_editor_property('random_seed', 0)", script)
        self.assertIn("NiagaraToolsets.NiagaraToolset_System.SetEmitterData", script)
        self.assertIn("\"bDeterminism\": True", script)
        self.assertIn("reset_system()", script)
        self.assertIn("reinitialize_system()", script)
        self.assertIn("advance_simulation_by_time(SIM_TIME, 1.0 / 60.0)", script)
        self.assertIn("set_paused(True)", script)
        self.assertIn("set_component_tick_enabled(False)", script)


if __name__ == "__main__":
    unittest.main(verbosity=2)
