from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import regression_baseline_set
from unreal_material_tools.core import save_json


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def baseline_payload() -> dict[str, object]:
    return {
        "tool": "material_regression_baseline",
        "effect": "WingEcho",
        "layer": "RibbonTrail",
        "created_utc": "2026-05-21T00:00:00+00:00",
        "label": "accepted",
        "status": "accepted",
        "preview": {"report_path": "D:/preview.json"},
    }


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = regression_baseline_set.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class RegressionBaselineSetTests(unittest.TestCase):
    def test_register_then_resolve_by_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = write_json(root, "baseline.json", baseline_payload())
            code, stdout, stderr = run_tool(
                [
                    "register",
                    "--root",
                    str(root),
                    "--baseline",
                    str(baseline),
                    "--parameter-tier",
                    "gameplay-safe",
                    "--carrier",
                    "ribbon",
                    "--background",
                    "busy",
                    "--exposure",
                    "high",
                ]
            )
            self.assertEqual(code, 0, stderr)
            register_report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            index_path = Path(register_report["baseline_index"])
            self.assertTrue(index_path.exists())

            code, stdout, stderr = run_tool(
                [
                    "resolve",
                    "--root",
                    str(root),
                    "--effect",
                    "WingEcho",
                    "--layer",
                    "RibbonTrail",
                    "--parameter-tier",
                    "gameplay-safe",
                    "--carrier",
                    "ribbon",
                    "--background",
                    "busy",
                    "--exposure",
                    "high",
                    "--require-match",
                ]
            )
            self.assertEqual(code, 0, stderr)
            resolve_report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertTrue(resolve_report["gate"]["has_match"])
            self.assertEqual(resolve_report["selected"]["baseline_path"], str(baseline))


if __name__ == "__main__":
    unittest.main(verbosity=2)
