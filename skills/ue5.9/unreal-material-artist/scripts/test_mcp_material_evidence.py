"""The MCP-era domain audit and preview capture feed the acceptance gate and regression offline."""

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from unreal_material_tools import material_acceptance_gate, material_preview, material_regression
from unreal_material_tools import material_audit as audit
from unreal_material_tools import material_domain_audit as domain


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def audit_report(name: str) -> dict:
    data = json.loads((FIXTURES / f"mcp-material-{name}.json").read_text(encoding="utf-8"))
    return audit.build_report(data["asset_path"], data["raw"], data["outputs"], data["stats"])


def fake_capture(folder: Path, ok: bool = True) -> dict:
    png = folder / "frame.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    return {"tool": "mcp_capture", "transport": "epic-mcp EditorAppToolset", "ok": ok, "error": "" if ok else "boom",
            "pose": None, "frames": [{"path": str(png), "sha256": "x"}] if ok else []}


class DomainAuditTests(unittest.TestCase):
    def test_fixture_report(self):
        report = domain.audit_payload(domain.raw_from_audit(audit_report("M_PrototypeGrid")))
        self.assertEqual(report["schema_version"], domain.SCHEMA_VERSION)
        contract = report["domain_contract"]
        self.assertEqual((contract["domain"], contract["blend_mode"], contract["shading_models"]),
                         ("Surface", "Opaque", ["DefaultLit"]))
        self.assertEqual([row["rule_id"] for row in report["findings"]], ["lit_missing_core_outputs"])  # no Normal wired
        self.assertTrue(report["coverage_gaps"])  # compile errors are an MCP gap and must stay visible

    def test_mcp_names_are_normalized(self):
        raw = domain.raw_from_audit(audit_report("M_PrototypeGrid"))
        raw["material_info"].update(usage_flags=["NiagaraSprites"], shading_models=domain.shading_model_names(
            {"shading_models": ["Two Sided Foliage"], "shading_model": "MSM_FromMaterialExpression"}))
        raw["graph"]["nodes"].append({"class_name": "Custom", "caption": ""})
        report = domain.audit_payload(raw)
        self.assertEqual(report["domain_contract"]["shading_models"], ["TwoSidedFoliage", "FromMaterialExpression"])
        self.assertEqual(report["node_evidence"]["custom_nodes"], 1)
        rules = {row["rule_id"] for row in report["findings"]}
        self.assertTrue({"foliage_not_twosided", "advanced_shading_route", "vfx_usage_flag_material_side"} <= rules)

    def test_report_without_raw_graph_is_refused(self):
        report = audit_report("M_PrototypeGrid")
        report.pop("raw_graph")
        with self.assertRaisesRegex(SystemExit, "include-raw-graph"):
            domain.raw_from_audit(report)

    def test_cli_from_audit_feeds_the_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            source, out = Path(folder) / "audit.json", Path(folder) / "domain.json"
            source.write_text(json.dumps(audit_report("M_PrototypeGrid")), encoding="utf-8")
            with redirect_stdout(StringIO()):
                self.assertEqual(domain.main(["--from-audit", str(source), "--root", folder, "--out", str(out)]), 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
        errors, warnings, _ = material_acceptance_gate._domain_audit_counts(
            {"payload": payload, "path": str(out)}, "/Game/LevelPrototyping/Materials/M_PrototypeGrid")
        self.assertEqual((errors, warnings), (0, 1))


class CapturePreviewTests(unittest.TestCase):
    def test_capture_report_passes_the_preview_gate_and_locks_a_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            report = material_preview.build_capture_report("/Game/M/M_Fire", "thumbnail", "mesh", fake_capture(Path(folder)))
            self.assertEqual((report["tool"], report["mode"], report["options"]["carrier"]),
                             ("material_preview", "capture", "thumbnail"))
            check = material_acceptance_gate.evaluate_preview(
                [{"tool": "material_preview", "path": "p.json", "payload": report, "load_error": ""}], "/Game/M/M_Fire")
            self.assertTrue(check["passed"], check)
            self.assertEqual(check["warnings"], 0)  # no complexity view over MCP is not a failure
            summary = material_regression.preview_report_summary(Path("p.json"), report)
            self.assertEqual(summary["image_paths"]["shaded"], report["outputs"]["shaded_png"])

    def test_failed_capture_fails_the_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            report = material_preview.build_capture_report("/Game/M/M_Fire", "viewport", "ribbon",
                                                           fake_capture(Path(folder), ok=False))
        self.assertEqual(report["options"]["carrier"], "ribbon")
        check = material_acceptance_gate.evaluate_preview(
            [{"tool": "material_preview", "path": "p.json", "payload": report, "load_error": ""}], "/Game/M/M_Fire")
        self.assertFalse(check["passed"])

    def test_capture_command_writes_the_report(self):
        class Client:
            def close(self):
                pass

        with tempfile.TemporaryDirectory() as folder:
            calls = []

            def capture(client, mode, out_dir, stem, **kwargs):
                calls.append((mode, kwargs["asset_path"], kwargs["frames"]))
                return fake_capture(Path(folder))

            with patch("unreal_material_tools.mcp.connect", return_value=Client()), \
                    patch("unreal_material_tools.mcp.capture_report", side_effect=capture), \
                    redirect_stdout(StringIO()) as stdout:
                code = material_preview.main(["capture", "/Game/M/M_Fire", "--root", folder])
            self.assertEqual(code, 0)
            self.assertEqual(calls, [("asset", "/Game/M/M_Fire", 1)])
            written = json.loads(Path(stdout.getvalue().strip()).read_text(encoding="utf-8"))
            self.assertEqual(written["schema_version"], material_preview.CAPTURE_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
