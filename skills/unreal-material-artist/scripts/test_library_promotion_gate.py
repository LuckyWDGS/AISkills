from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import library_promotion_gate
from unreal_material_tools.core import save_json


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def report_payload(tool: str, gate_key: str | None = None, approved: bool | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"tool": tool}
    if approved is not None:
        payload["delivery_summary"] = {"approved_for_reuse": approved}
        payload["asset"] = {"ue_asset_path": "/Game/Materials/M_WingEcho"}
    if gate_key:
        payload["gate"] = {gate_key: True}
    return payload


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = library_promotion_gate.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class LibraryPromotionGateTests(unittest.TestCase):
    def test_full_bundle_is_approved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = [
                write_json(root, "acceptance.json", report_payload("material_acceptance_gate_v2", approved=True)),
                write_json(root, "schema.json", report_payload("material_parameter_schema", "schema_complete")),
                write_json(root, "provenance.json", report_payload("material_source_provenance", "provenance_complete")),
                write_json(root, "matrix.json", report_payload("preview_matrix", "ready_for_regression_coverage")),
                write_json(root, "readability.json", report_payload("preview_readability_score", "readable")),
            ]
            args = ["--root", str(root), "--require-ready"]
            for report in reports:
                args.extend(["--report-path", str(report)])
            code, stdout, stderr = run_tool(args)
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertTrue(report["delivery_summary"]["approved_for_library"])

    def test_missing_provenance_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = [
                write_json(root, "acceptance.json", report_payload("material_acceptance_gate_v2", approved=True)),
                write_json(root, "schema.json", report_payload("material_parameter_schema", "schema_complete")),
                write_json(root, "matrix.json", report_payload("preview_matrix", "ready_for_regression_coverage")),
                write_json(root, "readability.json", report_payload("preview_readability_score", "readable")),
            ]
            args = ["--root", str(root), "--require-ready"]
            for report in reports:
                args.extend(["--report-path", str(report)])
            code, stdout, stderr = run_tool(args)
            self.assertEqual(code, 2)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            rules = {item["rule"] for item in report["findings"]}
            self.assertIn("missing_required_report", rules)


if __name__ == "__main__":
    unittest.main(verbosity=2)
