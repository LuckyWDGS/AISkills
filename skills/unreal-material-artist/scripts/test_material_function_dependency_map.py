from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import material_function_dependency_map
from unreal_material_tools.core import save_json


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def linter_payload() -> dict[str, object]:
    return {
        "tool": "material_function_linter",
        "functions": [
            {
                "name": "MF_NoiseWarp",
                "path": "/Game/Functions/MF_NoiseWarp",
                "description": "noise warp",
                "library_category": "VFX",
                "expose_to_library": True,
                "num_expressions": 90,
                "inputs": [{"name": "UV"}],
                "outputs": [{"name": "Out"}],
                "findings": [],
            }
        ],
    }


def audit_payload(material_path: str) -> dict[str, object]:
    return {
        "tool": "material_audit",
        "material_path": material_path,
        "raw_graph": {
            "nodes": [
                {
                    "class_name": "MaterialExpressionMaterialFunctionCall",
                    "caption": "MF_NoiseWarp",
                    "key_properties": {"Function": "/Game/Functions/MF_NoiseWarp"},
                }
            ]
        },
    }


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = material_function_dependency_map.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class MaterialFunctionDependencyMapTests(unittest.TestCase):
    def test_dependency_hotspot_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            linter = write_json(root, "linter.json", linter_payload())
            audit_a = write_json(root, "audit-a.json", audit_payload("/Game/Materials/M_A"))
            audit_b = write_json(root, "audit-b.json", audit_payload("/Game/Materials/M_B"))
            code, stdout, stderr = run_tool(
                ["--root", str(root), "--function-linter-report", str(linter), "--audit-report", str(audit_a), "--audit-report", str(audit_b)]
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["hotspot_count"], 1)
            self.assertEqual(report["hotspots"][0]["reuse_count"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
