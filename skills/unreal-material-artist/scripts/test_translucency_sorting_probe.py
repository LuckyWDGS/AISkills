from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import translucency_sorting_probe
from unreal_material_tools.core import save_json


MATERIAL_PATH = "/Game/Materials/M_WingEcho_RibbonTrail"


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def contract_payload() -> dict[str, object]:
    return {
        "tool": "material_contract",
        "effect": "WingEcho",
        "layer": "RibbonTrail",
        "carrier": {
            "renderer": "ribbon",
            "sort_or_depth_notes": "Ribbon sorts back to front; FixedBounds required in Niagara.",
        },
        "material": {
            "domain": "Surface",
            "blend_mode": "Additive",
            "shading_model": "Unlit",
            "expected_outputs": ["EmissiveColor", "Opacity"],
            "usage_flags": ["NiagaraRibbons"],
        },
        "budgets": {"overdraw_risk": "medium"},
    }


def audit_payload() -> dict[str, object]:
    return {
        "tool": "material_audit",
        "material_path": MATERIAL_PATH,
        "graph": {
            "nodes": [
                {"class_name": "MaterialExpressionDepthFade", "caption": "DepthFade", "desc": "", "key_properties": ""}
            ]
        },
        "analysis": {"findings": [], "compile_errors": [], "max_instructions": 70, "sampler_count": 2},
    }


def package_payload(contract: Path, audit: Path) -> dict[str, object]:
    return {
        "tool": "delivery_packager",
        "effect": "WingEcho",
        "layer": "RibbonTrail",
        "material_path": MATERIAL_PATH,
        "source": {"contract_path": str(contract)},
        "route": {"carrier": "ribbon", "domain": "Surface", "blend_mode": "Additive", "shading_model": "Unlit"},
        "summaries": {"reports": {"audit": [{"path": str(audit), "tool": "material_audit"}]}},
    }


def niagara_probe_payload() -> dict[str, object]:
    return {
        "tool": "niagara_material_integration_probe",
        "system_path": "/Game/VFX/NS_WingEcho",
        "renderer": {
            "SortMode": "ViewDepth",
            "CustomSortingBinding": "Particles.SortKey",
            "FixedBounds": "present",
        },
        "findings": [{"severity": "ok", "rule": "sorting", "message": "sorting is proven"}],
    }


def make_fixture(root: Path) -> dict[str, Path]:
    contract = write_json(root, "contract.json", contract_payload())
    audit = write_json(root, "audit.json", audit_payload())
    package = write_json(root, "package.json", package_payload(contract, audit))
    probe = write_json(root, "niagara-probe.json", niagara_probe_payload())
    return {"contract": contract, "audit": audit, "package": package, "probe": probe}


def run_probe(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = translucency_sorting_probe.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class TranslucencySortingProbeTests(unittest.TestCase):
    def test_require_proven_blocks_missing_system_sorting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = make_fixture(root)
            code, stdout, stderr = run_probe(["--root", str(root), "--package", str(paths["package"]), "--require-proven"])
            self.assertEqual(code, 2)
            self.assertIn("unproven", stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertFalse(report["gate"]["sorting_proven"])
            self.assertIn("sorting_unproven", {item["rule"] for item in report["findings"]})

    def test_niagara_probe_evidence_proves_sorting_and_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = make_fixture(root)
            code, stdout, stderr = run_probe(
                [
                    "--root",
                    str(root),
                    "--package",
                    str(paths["package"]),
                    "--material-integration-probe",
                    str(paths["probe"]),
                    "--require-proven",
                ]
            )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertTrue(report["gate"]["sorting_proven"])
            self.assertFalse(report["gate"]["material_preview_is_system_proof"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
