from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from unreal_material_tools import preview_environment_executor


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = preview_environment_executor.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class PreviewEnvironmentExecutorTests(unittest.TestCase):
    def test_plan_records_the_environment_to_stage(self) -> None:
        args = ["--material-path", "/Game/Materials/MI_WingEcho_Default", "--carrier", "ribbon",
                "--background", "busy", "--exposure", "high"]
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, stderr_text = run_tool(["--root", tmp, *args])
            self.assertEqual(code, 0, stderr_text)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual(report["environment"]["light_rig"], "contrast")
        self.assertEqual(report["status"], "planned")
        self.assertIn("capture", report["preview_command"])
        self.assertIn("--route viewport", report["preview_command_text"])

    def test_execute_passes_only_for_a_staged_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            preview = Path(tmp, "preview.json")
            preview.write_text(json.dumps({"tool": "material_preview", "outputs": {"shaded_ok": True}}), encoding="utf-8")
            completed = subprocess.CompletedProcess([], 0, stdout=str(preview) + chr(10), stderr="")
            base = ["--root", tmp, "--material-path", "/Game/M", "--carrier", "ribbon", "--execute",
                    "--pose", "0,0,100,-10,0,0", "--strict"]
            with patch.object(preview_environment_executor.subprocess, "run", return_value=completed) as run:
                code, stdout, _ = run_tool(base)
                unstaged = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
                self.assertIn("--pose", run.call_args.args[0])
                staged_code, stdout, _ = run_tool([*base, "--staged"])
                staged = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
        self.assertEqual((code, unstaged["status"], unstaged["gate"]["passed"]), (1, "captured_unstaged", False))
        self.assertEqual((staged_code, staged["status"], staged["environment"]["applied_by"]), (0, "pass", "user staging"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
