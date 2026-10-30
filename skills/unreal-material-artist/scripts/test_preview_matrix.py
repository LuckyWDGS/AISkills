from __future__ import annotations

import json
import math
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

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

    def test_only_mcp_drivable_axes_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview = write_json(root, "staged.json", {"tool": "material_preview", "outputs": {"shaded_ok": True}})
            calls = []

            def fake_execute(cell):
                calls.append(cell["preview_command"])
                return preview_matrix.execution_from_report(str(preview), source="mcp-capture")

            args = ["--root", str(root), "--material-path", MATERIAL_PATH, "--carrier", "ribbon",
                    "--background", "black,busy", "--angle", "0,0;90,30", "--focus", "100,0,50", "--execute"]
            with patch.object(preview_matrix, "execute_cell", side_effect=fake_execute):
                code, stdout, stderr = run_matrix(args)
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            cells = {(cell["background"], cell["yaw"]): cell for cell in report["cells"]}
            # Angles orbit the focus point; the second background needs manual staging.
            self.assertEqual(len(calls), 2)
            self.assertIn("--pose", cells[("black", 90.0)]["preview_command"])
            pose = cells[("black", 90.0)]["capture"]["pose"].split(",")
            self.assertAlmostEqual(float(pose[1]), 300 * math.cos(math.radians(30)), places=1)  # y offset at yaw 90
            self.assertEqual(pose[3], "-30.00")  # looks down at the focus
            self.assertEqual(cells[("busy", 0.0)]["execution"]["status"], "pending_staging")
            self.assertIn("background", cells[("busy", 0.0)]["capture"]["intent_only_axes"])
            self.assertEqual(report["summary"]["pending_staging_cells"], 2)
            self.assertTrue(report["gate"]["passed"])
            self.assertFalse(report["gate"]["ready_for_regression_coverage"])

            staged = [f"{cell['id']}={preview}" for cell in report["cells"] if cell["background"] == "busy"]
            with patch.object(preview_matrix, "execute_cell", side_effect=fake_execute):
                code, stdout, _ = run_matrix([*args, *sum((["--cell-report", item] for item in staged), [])])
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["executed_cells"], 4)
            self.assertTrue(report["gate"]["ready_for_regression_coverage"])

    def test_parameter_tiers_capture_their_instances_as_thumbnails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, stderr = run_matrix(["--root", tmp, "--material-path", MATERIAL_PATH, "--carrier", "mesh",
                                               "--parameter-tier", "default,high,low",
                                               "--tier-material", "high=/Game/Materials/MI_High"])
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
        by_tier = {cell["parameter_tier"]: cell["capture"] for cell in report["cells"]}
        self.assertEqual(by_tier["default"]["material_path"], MATERIAL_PATH)
        self.assertEqual((by_tier["high"]["material_path"], by_tier["high"]["route"]), ("/Game/Materials/MI_High", "thumbnail"))
        self.assertIn("parameter_tier", by_tier["low"]["intent_only_axes"])
        self.assertEqual(report["summary"]["mcp_executable_cells"], 2)
        self.assertIn("--execute", report["next_actions"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
