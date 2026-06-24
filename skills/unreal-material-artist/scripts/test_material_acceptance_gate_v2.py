from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import material_acceptance_gate_v2
from unreal_material_tools.core import save_json


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def acceptance_payload() -> dict[str, object]:
    return {
        "tool": "material_acceptance_gate",
        "effect": "WingEcho",
        "layer": "RibbonTrail",
        "asset": {"ue_asset_path": "/Game/Materials/M_WingEcho", "category": "other", "role": "niagara-ribbon-material"},
        "route": {"blend_mode": "Additive", "carrier": "ribbon", "material_domain": "Surface"},
        "delivery_summary": {"approved_for_reuse": True, "errors": 0, "warnings": 0},
    }


def gate_payload(tool: str, gate_key: str, value: bool = True) -> dict[str, object]:
    return {"tool": tool, "gate": {gate_key: value}, "summary": {"errors": 0 if value else 1, "warnings": 0}}


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = material_acceptance_gate_v2.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class MaterialAcceptanceGateV2Tests(unittest.TestCase):
    def test_v2_passes_with_all_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            acceptance = write_json(root, "acceptance.json", acceptance_payload())
            schema = write_json(root, "schema.json", gate_payload("material_parameter_schema", "schema_complete"))
            provenance = write_json(root, "provenance.json", gate_payload("material_source_provenance", "provenance_complete"))
            sorting = write_json(root, "sorting.json", gate_payload("translucency_sorting_probe", "sorting_proven"))
            matrix = write_json(root, "matrix.json", gate_payload("preview_matrix", "ready_for_regression_coverage"))
            readability = write_json(root, "readability.json", gate_payload("preview_readability_score", "readable"))
            code, stdout, stderr = run_tool(
                [
                    "--root",
                    str(root),
                    "--acceptance-report",
                    str(acceptance),
                    "--parameter-schema-report",
                    str(schema),
                    "--source-provenance-report",
                    str(provenance),
                    "--translucency-sorting-report",
                    str(sorting),
                    "--preview-matrix-report",
                    str(matrix),
                    "--preview-readability-report",
                    str(readability),
                    "--require-ready",
                ]
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertTrue(report["delivery_summary"]["approved_for_reuse"])

    def test_v2_blocks_missing_readability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            acceptance = write_json(root, "acceptance.json", acceptance_payload())
            schema = write_json(root, "schema.json", gate_payload("material_parameter_schema", "schema_complete"))
            provenance = write_json(root, "provenance.json", gate_payload("material_source_provenance", "provenance_complete"))
            sorting = write_json(root, "sorting.json", gate_payload("translucency_sorting_probe", "sorting_proven"))
            matrix = write_json(root, "matrix.json", gate_payload("preview_matrix", "ready_for_regression_coverage"))
            code, stdout, stderr = run_tool(
                [
                    "--root",
                    str(root),
                    "--acceptance-report",
                    str(acceptance),
                    "--parameter-schema-report",
                    str(schema),
                    "--source-provenance-report",
                    str(provenance),
                    "--translucency-sorting-report",
                    str(sorting),
                    "--preview-matrix-report",
                    str(matrix),
                    "--require-ready",
                ]
            )
            self.assertEqual(code, 2)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertIn("preview_readability", report["gate"]["failed_checks"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
