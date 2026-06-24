from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import preview_matrix
from unreal_material_tools.core import save_json


MATERIAL_PATH = "/Game/Materials/M_WingEcho_RibbonTrail"


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def run_matrix(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = preview_matrix.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class PreviewMatrixTests(unittest.TestCase):
    def test_dry_run_matrix_writes_cells_and_preview_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, stdout, stderr = run_matrix(
                [
                    "--root",
                    str(root),
                    "--material-path",
                    MATERIAL_PATH,
                    "--background",
                    "black,busy",
                    "--angle",
                    "0,0;45,10",
                    "--quality",
                    "low",
                    "--carrier",
                    "ribbon",
                    "--markdown",
                ]
            )
            self.assertEqual(code, 0, stderr)
            report_path = Path(stdout.strip())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(report["gate"]["executed"])
            self.assertEqual(report["summary"]["planned_cells"], 4)
            self.assertIn("material_preview.py", report["cells"][0]["preview_command_text"])
            self.assertNotEqual(report["cells"][0]["preview_effect"], report["cells"][1]["preview_effect"])
            self.assertIn("--effect", report["cells"][0]["preview_command"])
            self.assertTrue(report_path.with_suffix(".md").exists())

    def test_large_matrix_is_blocked_without_explicit_allowance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(SystemExit):
                run_matrix(
                    [
                        "--root",
                        str(root),
                        "--material-path",
                        MATERIAL_PATH,
                        "--background",
                        "a,b,c",
                        "--distance",
                        "0,1,2",
                        "--angle",
                        "0,0;45,10;90,15",
                        "--quality",
                        "low,medium,high",
                        "--max-cells",
                        "10",
                    ]
                )

    def test_package_can_provide_material_path_and_carrier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_json(
                root,
                "package.json",
                {
                    "tool": "delivery_packager",
                    "effect": "WingEcho",
                    "layer": "RibbonTrail",
                    "material_path": MATERIAL_PATH,
                    "route": {"carrier": "ribbon", "domain": "Surface", "blend_mode": "Additive"},
                },
            )
            code, stdout, stderr = run_matrix(["--root", str(root), "--package", str(package), "--quality", "low"])
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertEqual(report["material_path"], MATERIAL_PATH)
            self.assertEqual(report["cells"][0]["carrier"], "ribbon")

    def test_prefer_environment_executor_switches_preview_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, stdout, stderr = run_matrix(
                [
                    "--root",
                    str(root),
                    "--material-path",
                    MATERIAL_PATH,
                    "--carrier",
                    "ribbon",
                    "--background",
                    "black,busy",
                    "--prefer-environment-executor",
                ]
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertIn("preview_environment_executor.py", report["cells"][0]["preview_command_text"])
            self.assertTrue(report["cells"][0]["environment_executor"]["background_executable"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
