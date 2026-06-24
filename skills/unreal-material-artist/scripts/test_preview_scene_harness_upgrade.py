from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import preview_scene_harness_upgrade
from unreal_material_tools.core import save_json


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def matrix_payload() -> dict[str, object]:
    return {
        "tool": "preview_matrix",
        "material_path": "/Game/Materials/MI_WingEcho_Default",
        "axes": {
            "backgrounds": ["black", "busy"],
            "exposures": ["0", "high"],
            "parameter_tiers": ["default", "high"],
            "quality_profiles": ["low"],
            "lighting": ["hdri"],
            "carriers": ["ribbon"],
            "distances": [0.0],
            "angles": [{"yaw": 0.0, "pitch": 0.0}],
            "times": [1.0],
        },
    }


def variant_payload() -> dict[str, object]:
    return {
        "tool": "material_variant_runner",
        "variants": [
            {"tier": "default", "path": "/Game/Materials/MI_WingEcho_Default"},
            {"tier": "high", "path": "/Game/Materials/MI_WingEcho_High"},
        ],
    }


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = preview_scene_harness_upgrade.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class PreviewSceneHarnessUpgradeTests(unittest.TestCase):
    def test_missing_background_and_exposure_maps_block_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            matrix = write_json(root, "matrix.json", matrix_payload())
            variant = write_json(root, "variant.json", variant_payload())
            code, stdout, stderr = run_tool(["--root", str(root), "--preview-matrix-report", str(matrix), "--variant-report", str(variant), "--require-ready"])
            self.assertEqual(code, 2)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertIn("background", report["gate"]["blocked_axes"])
            self.assertIn("exposure", report["gate"]["blocked_axes"])

    def test_full_maps_make_harness_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            matrix = write_json(root, "matrix.json", matrix_payload())
            variant = write_json(root, "variant.json", variant_payload())
            code, stdout, stderr = run_tool(
                [
                    "--root",
                    str(root),
                    "--preview-matrix-report",
                    str(matrix),
                    "--variant-report",
                    str(variant),
                    "--background-map",
                    "black=/Game/Preview/BG_Black",
                    "--background-map",
                    "busy=D:/Refs/busy.png",
                    "--exposure-map",
                    "0=0",
                    "--exposure-map",
                    "high=1",
                    "--require-ready",
                ]
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertTrue(report["gate"]["ready_for_live_matrix"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
