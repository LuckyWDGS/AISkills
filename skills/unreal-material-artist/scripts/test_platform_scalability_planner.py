from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import platform_scalability_planner
from unreal_material_tools.core import save_json


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def package_payload() -> dict[str, object]:
    return {"tool": "delivery_packager", "effect": "WingEcho", "route": {"blend_mode": "Additive", "carrier": "ribbon"}, "summaries": {"reports": {}}}


def audit_payload() -> dict[str, object]:
    return {"tool": "material_audit", "analysis": {"max_instructions": 120, "sampler_count": 5, "shader_stats_ready": True}}


def texture_set_payload() -> dict[str, object]:
    return {
        "tool": "texture_set_pipeline",
        "slots": {"opacity": {"slot": "opacity", "file": {"width": 2048, "height": 2048}}},
    }


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = platform_scalability_planner.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class PlatformScalabilityPlannerTests(unittest.TestCase):
    def test_android_and_low_end_show_pressure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_json(root, "package.json", package_payload())
            audit = write_json(root, "audit.json", audit_payload())
            texture_set = write_json(root, "texture-set.json", texture_set_payload())
            code, stdout, stderr = run_tool(
                ["--root", str(root), "--package", str(package), "--audit-report", str(audit), "--texture-set-report", str(texture_set)]
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["platform_count"], 3)
            self.assertGreater(report["summary"]["warnings"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
