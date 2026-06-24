from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import smoke_resume_cache
from unreal_material_tools.core import resolve_root_context, save_json


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = smoke_resume_cache.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class SmokeResumeCacheTests(unittest.TestCase):
    def test_inspect_and_prune_cache_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx = resolve_root_context(root)
            report_path = root / "report.json"
            save_json(report_path, {"tool": "fixture"})
            step = {
                "command_text": "python tool.py",
                "report_path": str(report_path),
                "planned_report_path": str(report_path),
                "status": "pass",
                "exit_code": 0,
                "tool": "fixture",
            }
            smoke_resume_cache.cache_store(
                ctx,
                effect="WingEcho",
                name="preview_matrix:default",
                command=["python", "tool.py"],
                input_paths=[report_path],
                step=step,
            )

            code, stdout, stderr = run_tool(["inspect", "--root", str(root), "--effect", "WingEcho"])
            self.assertEqual(code, 0, stderr)
            inspect_report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertEqual(inspect_report["summary"]["entry_count"], 1)

            report_path.unlink()
            code, stdout, stderr = run_tool(["prune", "--root", str(root), "--effect", "WingEcho", "--apply"])
            self.assertEqual(code, 0, stderr)
            prune_report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertEqual(prune_report["summary"]["stale_count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
