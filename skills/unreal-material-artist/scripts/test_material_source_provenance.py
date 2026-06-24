from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import material_source_provenance
from unreal_material_tools.core import save_json


ASSET_PATH = "/Game/Textures/T_WingEcho_RibbonTrail_VFX"


def file_path(root: Path) -> str:
    path = root / "T_WingEcho_RibbonTrail_VFX.png"
    path.write_bytes(b"placeholder")
    return str(path)


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def texture_set_payload(texture_file: str) -> dict[str, object]:
    return {
        "tool": "texture_set_pipeline",
        "effect": "WingEcho",
        "layer": "RibbonTrail",
        "slots": {
            "opacity": {
                "slot": "opacity",
                "role": "mask",
                "file_path": texture_file,
                "asset_path": ASSET_PATH,
                "expected_import": {"srgb": False, "compression_settings": "TC_MASKS"},
            }
        },
        "fix_plan": {"pack_rma": {}},
    }


def import_audit_payload() -> dict[str, object]:
    return {
        "tool": "texture_import_audit",
        "textures": [
            {
                "asset_path": ASSET_PATH,
                "found": True,
                "width": 1024,
                "height": 1024,
                "compression_settings": "TC_MASKS",
                "lod_group": "TEXTUREGROUP_EFFECTS",
                "srgb": False,
                "num_mips": 11,
                "pixel_format": "PF_B8G8R8A8",
                "resource_size_bytes": 1024,
            }
        ],
    }


def source_manifest_payload(texture_file: str, with_prompt: bool = True) -> dict[str, object]:
    texture: dict[str, object] = {
        "slot": "opacity",
        "role": "mask",
        "file_path": texture_file,
        "asset_path": ASSET_PATH,
        "source_kind": "cm-imagegen",
        "original_file": "D:/Refs/wingecho-reference.png",
        "license": "project-owned",
    }
    if with_prompt:
        texture["source_prompt"] = "cyan ribbon opacity mask with broken energetic edge"
    return {"textures": [texture]}


def run_provenance(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = material_source_provenance.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class MaterialSourceProvenanceTests(unittest.TestCase):
    def test_complete_manifest_import_and_texture_set_pass_require_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            texture_file = file_path(root)
            texture_set = write_json(root, "texture-set.json", texture_set_payload(texture_file))
            import_audit = write_json(root, "import-audit.json", import_audit_payload())
            manifest = write_json(root, "source-manifest.json", source_manifest_payload(texture_file))
            code, stdout, stderr = run_provenance(
                [
                    "--root",
                    str(root),
                    "--source-manifest",
                    str(manifest),
                    "--texture-set-report",
                    str(texture_set),
                    "--import-audit-report",
                    str(import_audit),
                    "--require-complete",
                ]
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertTrue(report["gate"]["provenance_complete"])
            self.assertEqual(report["summary"]["texture_count"], 1)
            self.assertTrue(report["textures"][0]["reuse_eligibility"]["ready"])

    def test_generated_texture_without_prompt_is_blocked_when_complete_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            texture_file = file_path(root)
            manifest = write_json(root, "source-manifest.json", source_manifest_payload(texture_file, with_prompt=False))
            code, stdout, stderr = run_provenance(["--root", str(root), "--source-manifest", str(manifest), "--require-complete"])
            self.assertEqual(code, 2)
            self.assertIn("incomplete", stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertIn("generated_prompt_missing", {item["rule"] for item in report["findings"]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
