from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import preview_environment_executor


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = preview_environment_executor.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class PreviewEnvironmentExecutorTests(unittest.TestCase):
    def test_execute_is_refused_and_the_plan_captures(self) -> None:
        args = ["--material-path", "/Game/Materials/MI_WingEcho_Default", "--carrier", "ribbon",
                "--background", "busy", "--exposure", "high"]
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stderr(StringIO()) as stderr, self.assertRaises(SystemExit):
                preview_environment_executor.main(["--root", tmp, *args, "--execute"])
            self.assertIn("material_preview.py capture", stderr.getvalue())
            code, stdout, stderr_text = run_tool(["--root", tmp, *args])
            self.assertEqual(code, 0, stderr_text)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(report["environment"]["light_rig"], "contrast")  # recorded as plan intent
        command = " ".join(report["preview_command"]) if isinstance(report.get("preview_command"), list) else str(report.get("preview_command"))
        self.assertIn("capture", command)
        self.assertIn("--route viewport", command)


if __name__ == "__main__":
    unittest.main(verbosity=2)
