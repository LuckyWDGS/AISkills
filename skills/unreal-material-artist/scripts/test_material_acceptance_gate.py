from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import material_acceptance_gate
from unreal_material_tools.core import save_json


MATERIAL_PATH = "/Game/Materials/M_WingEcho_RibbonTrail"


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def contract_payload() -> dict[str, object]:
    return {
        "tool": "material_contract",
        "version": 1,
        "effect": "WingEcho",
        "layer": "RibbonTrail",
        "carrier": {
            "renderer": "ribbon",
            "uv_expectations": "ribbon UV along length",
            "particle_inputs": ["ParticleColor"],
            "dynamic_parameters": ["OpacityBoost"],
            "sort_or_depth_notes": "Additive ribbon sorted back to front with low overdraw budget.",
        },
        "material": {
            "domain": "Surface",
            "blend_mode": "Additive",
            "shading_model": "Unlit",
            "two_sided": False,
            "expected_outputs": ["EmissiveColor", "Opacity"],
            "usage_flags": ["NiagaraRibbons"],
        },
        "textures": [
            {
                "name": "T_WingEcho_RibbonTrail_VFX",
                "role": "flipbook",
                "grid": "8x8",
                "srgb": True,
            }
        ],
        "parameters": [{"name": "OpacityBoost", "type": "scalar", "default": 1.0}],
        "budgets": {
            "platform": "PC",
            "instruction_budget": 120,
            "sampler_budget": 4,
            "overdraw_risk": "medium",
        },
        "acceptance": ["Preview matches accepted WingEcho ribbon trail baseline."],
    }


def preview_payload() -> dict[str, object]:
    return {
        "tool": "material_preview",
        "mode": "render",
        "material_path": MATERIAL_PATH,
        "options": {"carrier": "ribbon", "preview_route": "niagara"},
        "outputs": {
            "shaded_png": "D:/tmp/wingecho-preview.png",
            "shaded_ok": True,
            "complexity_png": "D:/tmp/wingecho-complexity.png",
            "complexity_ok": True,
        },
        "contract_scan": {"findings": []},
    }


def material_audit_payload(usage_flags: list[str] | None = None) -> dict[str, object]:
    return {
        "tool": "material_audit",
        "material_path": MATERIAL_PATH,
        "material_info": {
            "path": MATERIAL_PATH,
            "material_domain": "Surface",
            "blend_mode": "Additive",
            "shading_models": ["Unlit"],
            "two_sided": False,
            "usage_flags": usage_flags if usage_flags is not None else ["UsedWithNiagaraRibbons"],
            "scalar_parameters": [{"name": "OpacityBoost", "param_type": "scalar", "value": 1.0}],
            "vector_parameters": [],
            "texture_parameters": [],
            "static_switch_parameters": [],
        },
        "analysis": {
            "max_instructions": 88,
            "sampler_count": 3,
            "compile_errors": [],
            "findings": [],
            "shader_stats_ready": True,
        },
        "graph_summary": {"dead_nodes": []},
        "stale_overrides": [],
    }


def domain_audit_payload(usage_flags: list[str] | None = None) -> dict[str, object]:
    return {
        "tool": "material_domain_audit",
        "material_path": MATERIAL_PATH,
        "material_info": {"path": MATERIAL_PATH},
        "domain_contract": {
            "domain": "Surface",
            "blend_mode": "Additive",
            "shading_models": ["Unlit"],
            "two_sided": False,
            "usage_flags": usage_flags if usage_flags is not None else ["UsedWithNiagaraRibbons"],
            "wired_outputs": ["MP_EmissiveColor", "MP_Opacity"],
        },
        "analysis": {"max_instructions": 88, "sampler_count": 3, "shader_stats_ready": True},
        "findings": [],
        "summary": {"errors": 0, "warnings": 0, "info": 0, "ok": 1},
    }


def texture_set_payload() -> dict[str, object]:
    return {
        "tool": "texture_set_pipeline",
        "effect": "WingEcho",
        "layer": "RibbonTrail",
        "profile": "vfx-unlit",
        "slots": {
            "base_color": {"required": False, "findings": []},
            "normal": {"required": False, "findings": []},
            "rma": {"required": False, "findings": []},
            "opacity": {"required": True, "findings": []},
            "emissive": {"required": True, "findings": []},
        },
        "findings": [],
        "gate": {
            "passed": True,
            "ready_for_import": True,
            "counts": {"errors": 0, "warnings": 0, "info": 0},
        },
    }


def regression_payload() -> dict[str, object]:
    return {
        "tool": "material_regression_compare",
        "effect": "WingEcho",
        "layer": "RibbonTrail",
        "gate": {"passed": True, "errors": 0, "warnings": 0, "findings": []},
        "comparisons": [],
    }


def package_payload(paths: dict[str, Path]) -> dict[str, object]:
    return {
        "tool": "delivery_packager",
        "version": 1,
        "effect": "WingEcho",
        "layer": "RibbonTrail",
        "material_path": MATERIAL_PATH,
        "source": {"contract_path": str(paths["contract"])},
        "route": {
            "carrier": "ribbon",
            "domain": "Surface",
            "blend_mode": "Additive",
            "shading_model": "Unlit",
            "two_sided": False,
            "expected_outputs": ["EmissiveColor", "Opacity"],
            "usage_flags": ["NiagaraRibbons"],
        },
        "texture_requirements": [{"name": "T_WingEcho_RibbonTrail_VFX", "role": "flipbook"}],
        "parameters": [{"name": "OpacityBoost", "type": "scalar", "default": 1.0}],
        "budgets": {"platform": "PC", "instruction_budget": 120, "sampler_budget": 4},
        "summaries": {
            "reports": {
                "preview": [{"path": str(paths["preview"]), "tool": "material_preview"}],
                "audit": [
                    {"path": str(paths["audit"]), "tool": "material_audit"},
                    {"path": str(paths["domain"]), "tool": "material_domain_audit"},
                ],
                "texture": [{"path": str(paths["texture_set"]), "tool": "texture_set_pipeline"}],
                "other": [{"path": str(paths["regression"]), "tool": "material_regression_compare"}],
            },
            "texture_coverage": {"required_count": 1, "covered_count": 1, "missing_count": 0, "items": []},
        },
        "gate": {
            "ready_for_handoff": True,
            "missing_required": [],
            "counts": {"errors": 0, "warnings": 0, "info": 0, "ok": 0},
        },
    }


def make_fixture(root: Path, *, usage_flags: list[str] | None = None) -> Path:
    paths = {
        "contract": write_json(root, "contract.json", contract_payload()),
        "preview": write_json(root, "preview.json", preview_payload()),
        "audit": write_json(root, "audit.json", material_audit_payload(usage_flags)),
        "domain": write_json(root, "domain.json", domain_audit_payload(usage_flags)),
        "texture_set": write_json(root, "texture-set.json", texture_set_payload()),
        "regression": write_json(root, "regression.json", regression_payload()),
    }
    return write_json(root, "package.json", package_payload(paths))


def run_gate(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = material_acceptance_gate.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class MaterialAcceptanceGateTests(unittest.TestCase):
    def test_approved_delivery_report_is_niagara_consumable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = make_fixture(root)
            code, stdout, stderr = run_gate([
                "--root",
                str(root),
                "--package",
                str(package),
                "--require-ready",
                "--markdown",
            ])
            self.assertEqual(code, 0, stderr)
            report_path = Path(stdout.strip().splitlines()[-1])
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["asset"]["ue_asset_path"], MATERIAL_PATH)
            self.assertTrue(report["delivery_summary"]["approved_for_reuse"])
            self.assertEqual(report["delivery_summary"]["errors"], 0)
            self.assertEqual(report["delivery_summary"]["warnings"], 0)
            self.assertEqual(report["asset"]["role"], "niagara-ribbon-material")
            self.assertTrue(report_path.match("*/.codex/session/material-delivery/deliveries/*/delivery.json"))
            self.assertTrue(report_path.with_suffix(".md").exists())

    def test_require_ready_blocks_missing_usage_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = make_fixture(root, usage_flags=[])
            code, stdout, stderr = run_gate([
                "--root",
                str(root),
                "--package",
                str(package),
                "--require-ready",
            ])
            self.assertEqual(code, 2)
            self.assertIn("not ready", stderr)
            report_path = Path(stdout.strip().splitlines()[-1])
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(report["delivery_summary"]["approved_for_reuse"])
            self.assertIn("usage_flags", report["gate"]["failed_checks"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
