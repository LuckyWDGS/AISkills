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

from unreal_material_tools import preview_environment_executor
from unreal_material_tools.core import save_json


def subprocess_completed(report_path: str):  # type: ignore[no-untyped-def]
    class Result:
        def __init__(self, value: str) -> None:
            self.returncode = 0
            self.stdout = value + "\n"
            self.stderr = ""

    return Result(report_path)


def preview_payload() -> dict[str, object]:
    return {
        "tool": "material_preview",
        "mode": "render",
        "material_path": "/Game/Materials/MI_WingEcho_Default",
        "outputs": {"shaded_png": "D:/preview.png", "shaded_ok": True, "complexity_ok": True},
    }


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = preview_environment_executor.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class PreviewEnvironmentExecutorTests(unittest.TestCase):
    def test_execute_wraps_material_preview_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview_report = root / "preview.json"

            def fake_run(command, capture_output, text, check):  # type: ignore[no-untyped-def]
                save_json(preview_report, preview_payload())
                return subprocess_completed(str(preview_report))

            with patch("unreal_material_tools.preview_environment_executor.subprocess.run", side_effect=fake_run):
                code, stdout, stderr = run_tool(
                    [
                        "--root",
                        str(root),
                        "--material-path",
                        "/Game/Materials/MI_WingEcho_Default",
                        "--carrier",
                        "ribbon",
                        "--background",
                        "busy",
                        "--exposure",
                        "high",
                        "--execute",
                    ]
                )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertTrue(report["gate"]["passed"])
            self.assertEqual(report["preview_report_path"], str(preview_report))
            self.assertEqual(report["environment"]["background_preset"], "busy")
            self.assertEqual(report["environment"]["light_rig"], "contrast")


if __name__ == "__main__":
    unittest.main(verbosity=2)
