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

from unreal_material_tools import material_delivery_smoke
from unreal_material_tools.core import save_json


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def package_payload() -> dict[str, object]:
    return {
        "tool": "delivery_packager",
        "effect": "WingEcho",
        "layer": "RibbonTrail",
        "material_path": "/Game/Materials/M_WingEcho_RibbonTrail",
        "gate": {
            "ready_for_handoff": True,
            "missing_required": [],
            "counts": {"errors": 0, "warnings": 0, "info": 0, "ok": 0},
        },
        "summaries": {"reports": {"preview": [], "audit": [], "texture": [], "other": []}},
    }


def schema_payload() -> dict[str, object]:
    return {
        "tool": "material_parameter_schema",
        "effect": "WingEcho",
        "material_path": "/Game/Materials/M_WingEcho_RibbonTrail",
        "schema": {
            "parameters": [
                {"name": "OpacityBoost", "type": "scalar", "default": 1.0, "range": {"min": 0.0, "max": 4.0}},
                {"name": "Tint", "type": "vector", "default": {"r": 0.5, "g": 0.8, "b": 1.0, "a": 1.0}},
            ]
        },
    }


def provenance_payload() -> dict[str, object]:
    return {"tool": "material_source_provenance", "gate": {"provenance_complete": True}, "summary": {"errors": 0, "warnings": 0}}


def sorting_payload() -> dict[str, object]:
    return {"tool": "translucency_sorting_probe", "gate": {"sorting_proven": True}, "summary": {"errors": 0, "warnings": 0}}


def preview_report_payload(image_path: Path) -> dict[str, object]:
    return {
        "tool": "material_preview",
        "mode": "render",
        "material_path": "/Game/Materials/MI_WingEcho_default",
        "options": {"carrier": "ribbon"},
        "outputs": {"shaded_png": str(image_path), "shaded_ok": True, "complexity_ok": True},
    }


def matrix_payload(preview_report: Path, tier: str) -> dict[str, object]:
    return {
        "tool": "preview_matrix",
        "effect": "WingEcho",
        "layer": tier,
        "axes": {"parameter_tiers": [tier]},
        "summary": {"planned_cells": 1, "executed_cells": 1, "failed_cells": 0, "passed_cells": 1},
        "gate": {"passed": True, "executed": True, "ready_for_regression_coverage": True},
        "evidence": {"preview_reports": [str(preview_report)]},
    }


def readability_payload() -> dict[str, object]:
    return {
        "tool": "preview_readability_score",
        "summary": {"errors": 0, "warnings": 0, "image_count": 1},
        "gate": {"readable": True, "passed": True},
    }


def regression_payload() -> dict[str, object]:
    return {
        "tool": "material_regression_compare",
        "comparisons": [{"role": "shaded"}],
        "gate": {"passed": True, "errors": 0, "warnings": 0},
    }


def acceptance_payload() -> dict[str, object]:
    return {
        "tool": "material_acceptance_gate_v2",
        "delivery_summary": {"approved_for_reuse": True, "errors": 0, "warnings": 0},
        "gate": {"approved_for_reuse": True},
    }


def library_payload() -> dict[str, object]:
    return {
        "tool": "library_promotion_gate",
        "delivery_summary": {"approved_for_library": True, "errors": 0, "warnings": 0},
        "gate": {"approved_for_library": True},
    }


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = material_delivery_smoke.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def subprocess_completed(report_path: str):  # type: ignore[no-untyped-def]
    class Result:
        def __init__(self, value: str) -> None:
            self.returncode = 0
            self.stdout = value + "\n"
            self.stderr = ""

    return Result(report_path)


class MaterialDeliverySmokeTests(unittest.TestCase):
    def test_preview_matrix_axis_args_defaults_to_preview_quality(self) -> None:
        args = material_delivery_smoke.argparse.Namespace(
            matrix_spec="",
            background=[],
            exposure=[],
            distance=[],
            angle=[],
            time=[],
            quality=[],
            lighting=[],
            carrier=[],
            resolution=None,
            max_cells=64,
            allow_large_matrix=False,
            with_complexity=False,
            markdown_previews=False,
            preview_quality="low",
        )

        command = material_delivery_smoke.preview_matrix_axis_args(args)

        self.assertIn("--quality", command)
        self.assertEqual(command[command.index("--quality") + 1], "low")

    def test_matrix_preview_candidates_skip_failed_environment_executor_shell_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            executor_shell = write_json(
                root,
                "executor-shell.json",
                {
                    "tool": "preview_environment_executor",
                    "preview_report_path": "",
                    "gate": {"passed": False},
                },
            )
            matrix = write_json(
                root,
                "matrix.json",
                {
                    "tool": "preview_matrix",
                    "generated_utc": "2026-05-21T00:00:00+00:00",
                    "layer": "default-switchless",
                    "axes": {
                        "parameter_tiers": ["default"],
                        "quality_profiles": ["low"],
                        "lighting": ["hdri"],
                        "carriers": ["sprite"],
                    },
                    "cells": [
                        {
                            "id": "cell-001",
                            "parameter_tier": "default",
                            "carrier": "sprite",
                            "background": "neutral",
                            "exposure": "0",
                            "lighting": "hdri",
                            "quality_profile": "low",
                            "preview_effect": "WingEcho-cell-001",
                            "execution": {
                                "status": "fail",
                                "tool": "preview_environment_executor",
                                "report_path": str(executor_shell),
                                "preview_report_path": "",
                            },
                        }
                    ],
                },
            )

            candidates = material_delivery_smoke.matrix_preview_candidates([matrix])

            self.assertEqual(candidates, [])

    def test_regression_preview_prefers_baseline_matched_cell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preview_black = write_json(root, "preview-black.json", preview_report_payload(root / "black.png"))
            preview_neutral = write_json(root, "preview-neutral.json", preview_report_payload(root / "neutral.png"))
            preview_busy = write_json(root, "preview-busy.json", preview_report_payload(root / "busy.png"))
            baseline = write_json(
                root,
                "baseline.json",
                {
                    "tool": "material_regression_baseline",
                    "effect": "WingEcho",
                    "layer": "RibbonTrail",
                    "preview": {
                        "report_path": "baseline-preview.json",
                        "options": {
                            "carrier": "sprite",
                            "lighting": "hdri",
                        },
                    },
                },
            )
            matrix = write_json(
                root,
                "matrix.json",
                {
                    "tool": "preview_matrix",
                    "generated_utc": "2026-05-21T00:00:00+00:00",
                    "layer": "default-switchless",
                    "axes": {
                        "parameter_tiers": ["default"],
                        "quality_profiles": ["low"],
                        "lighting": ["hdri"],
                        "carriers": ["sprite"],
                    },
                    "cells": [
                        {
                            "id": "cell-001",
                            "parameter_tier": "default",
                            "carrier": "sprite",
                            "background": "black",
                            "exposure": "0",
                            "lighting": "hdri",
                            "quality_profile": "low",
                            "preview_effect": "WingEcho-cell-001",
                            "execution": {"preview_report_path": str(preview_black)},
                        },
                        {
                            "id": "cell-002",
                            "parameter_tier": "default",
                            "carrier": "sprite",
                            "background": "neutral",
                            "exposure": "0",
                            "lighting": "hdri",
                            "quality_profile": "low",
                            "preview_effect": "WingEcho-cell-002",
                            "execution": {"preview_report_path": str(preview_neutral)},
                        },
                        {
                            "id": "cell-003",
                            "parameter_tier": "default",
                            "carrier": "sprite",
                            "background": "busy",
                            "exposure": "0",
                            "lighting": "hdri",
                            "quality_profile": "low",
                            "preview_effect": "WingEcho-cell-003",
                            "execution": {"preview_report_path": str(preview_busy)},
                        },
                    ],
                },
            )
            args = material_delivery_smoke.argparse.Namespace(
                regression_tier="default",
                carrier=["sprite"],
                background=[],
                exposure=[],
                lighting=[],
                quality=["low"],
            )
            resolution = {
                "selected": {
                    "context": {
                        "parameter_tier": "default",
                        "carrier": "sprite",
                        "background": "",
                        "exposure": "",
                        "lighting": "",
                        "quality_profile": "low",
                        "environment_id": "",
                    }
                }
            }

            selected_path, detail, selection = material_delivery_smoke.regression_preview_path(
                args,
                [matrix],
                baseline_path=baseline,
                baseline_resolution=resolution,
            )

            self.assertEqual(selected_path, preview_neutral)
            self.assertIn("cell-002", detail)
            self.assertEqual(selection["selected"]["cell_id"], "cell-002")
            self.assertEqual(selection["selected"]["context"]["background"], "neutral")

    def test_dry_run_executes_variant_and_plans_live_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_json(root, "package.json", package_payload())
            schema = write_json(root, "schema.json", schema_payload())
            provenance = write_json(root, "provenance.json", provenance_payload())
            sorting = write_json(root, "sorting.json", sorting_payload())

            def fake_run(command, capture_output, text, check):  # type: ignore[no-untyped-def]
                report_path = Path(command[command.index("--out") + 1])
                if "material_variant_runner.py" in command[1]:
                    spec_path = Path(command[command.index("--spec-out") + 1])
                    save_json(
                        spec_path,
                        {
                            "effect": "WingEcho",
                            "instances": [
                                {"path": "/Game/Materials/MI_WingEcho_default", "parent_path": "/Game/Materials/M_WingEcho_RibbonTrail", "params": []},
                                {"path": "/Game/Materials/MI_WingEcho_gameplay-safe", "parent_path": "/Game/Materials/M_WingEcho_RibbonTrail", "params": []},
                            ],
                        },
                    )
                    save_json(
                        report_path,
                        {
                            "tool": "material_variant_runner",
                            "variants": [
                                {"tier": "default", "path": "/Game/Materials/MI_WingEcho_default", "params": [], "skipped_parameters": []},
                                {"tier": "gameplay-safe", "path": "/Game/Materials/MI_WingEcho_gameplay-safe", "params": [], "skipped_parameters": []},
                            ],
                            "summary": {"variant_count": 2},
                            "gate": {"variants_generated": True},
                            "material_instance_batch_spec": str(spec_path),
                        },
                    )
                elif "static_switch_variant_expander.py" in command[1]:
                    spec_path = Path(command[command.index("--spec-out") + 1])
                    save_json(
                        spec_path,
                        {
                            "effect": "WingEcho",
                            "instances": [
                                {"path": "/Game/Materials/MI_WingEcho_default", "parent_path": "/Game/Materials/M_WingEcho_RibbonTrail", "params": []},
                                {"path": "/Game/Materials/MI_WingEcho_gameplay-safe", "parent_path": "/Game/Materials/M_WingEcho_RibbonTrail", "params": []},
                            ],
                        },
                    )
                    save_json(
                        report_path,
                        {
                            "tool": "static_switch_variant_expander",
                            "variants": [
                                {"tier": "default", "path": "/Game/Materials/MI_WingEcho_default", "params": [], "skipped_parameters": []},
                                {"tier": "gameplay-safe", "path": "/Game/Materials/MI_WingEcho_gameplay-safe", "params": [], "skipped_parameters": []},
                            ],
                            "summary": {"variant_count": 2, "switch_parameter_count": 0, "requested_permutation_count": 1},
                            "gate": {"variants_generated": True, "switch_space_truncated": False},
                            "material_instance_batch_spec": str(spec_path),
                        },
                    )
                elif "permutation_budget_guard.py" in command[1]:
                    save_json(report_path, {"tool": "permutation_budget_guard", "summary": {"requested_permutation_count": 1, "warnings": 0, "errors": 0}, "gate": {"passed": True}})
                return subprocess_completed(str(report_path))

            with patch("unreal_material_tools.material_delivery_smoke.subprocess.run", side_effect=fake_run):
                code, stdout, stderr = run_tool(
                    [
                        "--root",
                        str(root),
                        "--package",
                        str(package),
                        "--parameter-schema-report",
                        str(schema),
                        "--source-provenance-report",
                        str(provenance),
                        "--translucency-sorting-report",
                        str(sorting),
                        "--markdown",
                    ]
                )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "planned")
            self.assertTrue(report["gate"]["ready_for_live_smoke"])
            by_name = {step["name"]: step for step in report["steps"]}
            self.assertEqual(by_name["material_variant_runner"]["status"], "pass")
            self.assertEqual(by_name["static_switch_variant_expander"]["status"], "pass")
            self.assertEqual(by_name["permutation_budget_guard"]["status"], "pass")
            self.assertEqual(by_name["material_instance_batch"]["status"], "planned")

    def test_execute_runs_full_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_json(root, "package.json", package_payload())
            schema = write_json(root, "schema.json", schema_payload())
            provenance = write_json(root, "provenance.json", provenance_payload())
            sorting = write_json(root, "sorting.json", sorting_payload())
            baseline = write_json(root, "baseline.json", {"tool": "material_regression_baseline", "effect": "WingEcho", "layer": "RibbonTrail"})
            image_path = root / "preview.png"
            image_path.write_bytes(b"fixture")

            def fake_run(command, capture_output, text, check):  # type: ignore[no-untyped-def]
                report_path = Path(command[command.index("--out") + 1])
                name = Path(command[1]).name
                if name == "material_variant_runner.py":
                    spec_path = Path(command[command.index("--spec-out") + 1])
                    save_json(
                        spec_path,
                        {
                            "effect": "WingEcho",
                            "instances": [
                                {"path": "/Game/Materials/MI_WingEcho_default", "parent_path": "/Game/Materials/M_WingEcho_RibbonTrail", "params": []},
                                {"path": "/Game/Materials/MI_WingEcho_gameplay-safe", "parent_path": "/Game/Materials/M_WingEcho_RibbonTrail", "params": []},
                            ],
                        },
                    )
                    save_json(
                        report_path,
                        {
                            "tool": "material_variant_runner",
                            "variants": [
                                {"tier": "default", "path": "/Game/Materials/MI_WingEcho_default", "params": [], "skipped_parameters": []},
                                {"tier": "gameplay-safe", "path": "/Game/Materials/MI_WingEcho_gameplay-safe", "params": [], "skipped_parameters": []},
                            ],
                            "summary": {"variant_count": 2},
                            "gate": {"variants_generated": True},
                            "material_instance_batch_spec": str(spec_path),
                        },
                    )
                elif name == "static_switch_variant_expander.py":
                    spec_path = Path(command[command.index("--spec-out") + 1])
                    save_json(
                        spec_path,
                        {
                            "effect": "WingEcho",
                            "instances": [
                                {"path": "/Game/Materials/MI_WingEcho_default", "parent_path": "/Game/Materials/M_WingEcho_RibbonTrail", "params": []},
                                {"path": "/Game/Materials/MI_WingEcho_gameplay-safe", "parent_path": "/Game/Materials/M_WingEcho_RibbonTrail", "params": []},
                            ],
                        },
                    )
                    save_json(
                        report_path,
                        {
                            "tool": "static_switch_variant_expander",
                            "variants": [
                                {"tier": "default", "path": "/Game/Materials/MI_WingEcho_default", "params": [], "skipped_parameters": []},
                                {"tier": "gameplay-safe", "path": "/Game/Materials/MI_WingEcho_gameplay-safe", "params": [], "skipped_parameters": []},
                            ],
                            "summary": {"variant_count": 2, "switch_parameter_count": 0, "requested_permutation_count": 1},
                            "gate": {"variants_generated": True, "switch_space_truncated": False},
                            "material_instance_batch_spec": str(spec_path),
                        },
                    )
                elif name == "permutation_budget_guard.py":
                    save_json(report_path, {"tool": "permutation_budget_guard", "summary": {"requested_permutation_count": 1, "warnings": 0, "errors": 0}, "gate": {"passed": True}})
                elif name == "material_instance_batch.py":
                    save_json(
                        report_path,
                        {
                            "tool": "material_instance_batch",
                            "instances": [
                                {"path": "/Game/Materials/MI_WingEcho_default", "create": {"success": True}, "set_params": {"success": True}},
                                {"path": "/Game/Materials/MI_WingEcho_gameplay-safe", "create": {"success": True}, "set_params": {"success": True}},
                            ],
                        },
                    )
                elif name == "preview_matrix.py":
                    tier = command[command.index("--layer") + 1]
                    preview_report = root / f"preview-{tier}.json"
                    save_json(preview_report, preview_report_payload(image_path))
                    save_json(report_path, matrix_payload(preview_report, tier))
                elif name == "preview_readability_score.py":
                    save_json(report_path, readability_payload())
                elif name == "material_regression.py":
                    save_json(report_path, regression_payload())
                elif name == "material_acceptance_gate_v2.py":
                    save_json(report_path, acceptance_payload())
                elif name == "library_promotion_gate.py":
                    save_json(report_path, library_payload())
                else:  # pragma: no cover - defensive path
                    raise AssertionError(f"Unexpected command: {command}")
                return subprocess_completed(str(report_path))

            with patch("unreal_material_tools.material_delivery_smoke.subprocess.run", side_effect=fake_run):
                code, stdout, stderr = run_tool(
                    [
                        "--root",
                        str(root),
                        "--package",
                        str(package),
                        "--parameter-schema-report",
                        str(schema),
                        "--source-provenance-report",
                        str(provenance),
                        "--translucency-sorting-report",
                        str(sorting),
                        "--baseline",
                        str(baseline),
                        "--execute",
                        "--markdown",
                        "--require-ready",
                    ]
                )
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "pass")
            self.assertTrue(report["gate"]["smoke_passed"])
            self.assertEqual(report["summary"]["risk_count"], 0)
            self.assertEqual(report["steps"][-1]["status"], "pass")

    def test_resume_cache_reuses_completed_planning_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_json(root, "package.json", package_payload())
            schema = write_json(root, "schema.json", schema_payload())
            provenance = write_json(root, "provenance.json", provenance_payload())
            sorting = write_json(root, "sorting.json", sorting_payload())

            def fake_run(command, capture_output, text, check):  # type: ignore[no-untyped-def]
                report_path = Path(command[command.index("--out") + 1])
                name = Path(command[1]).name
                if name == "material_variant_runner.py":
                    spec_path = Path(command[command.index("--spec-out") + 1])
                    save_json(spec_path, {"effect": "WingEcho", "instances": [{"path": "/Game/Materials/MI_WingEcho_default", "parent_path": "/Game/Materials/M_WingEcho_RibbonTrail", "params": []}]})
                    save_json(report_path, {"tool": "material_variant_runner", "variants": [{"tier": "default", "path": "/Game/Materials/MI_WingEcho_default", "params": [], "skipped_parameters": []}], "summary": {"variant_count": 1}, "gate": {"variants_generated": True}, "material_instance_batch_spec": str(spec_path)})
                elif name == "static_switch_variant_expander.py":
                    spec_path = Path(command[command.index("--spec-out") + 1])
                    save_json(spec_path, {"effect": "WingEcho", "instances": [{"path": "/Game/Materials/MI_WingEcho_default", "parent_path": "/Game/Materials/M_WingEcho_RibbonTrail", "params": []}]})
                    save_json(report_path, {"tool": "static_switch_variant_expander", "variants": [{"tier": "default", "path": "/Game/Materials/MI_WingEcho_default", "params": [], "skipped_parameters": []}], "summary": {"variant_count": 1, "switch_parameter_count": 0, "requested_permutation_count": 1}, "gate": {"variants_generated": True, "switch_space_truncated": False}, "material_instance_batch_spec": str(spec_path)})
                elif name == "permutation_budget_guard.py":
                    save_json(report_path, {"tool": "permutation_budget_guard", "summary": {"requested_permutation_count": 1, "warnings": 0, "errors": 0}, "gate": {"passed": True}})
                else:  # pragma: no cover - defensive path
                    raise AssertionError(f"Unexpected command during cached test warmup: {command}")
                return subprocess_completed(str(report_path))

            with patch("unreal_material_tools.material_delivery_smoke.subprocess.run", side_effect=fake_run):
                code, stdout, stderr = run_tool(
                    [
                        "--root",
                        str(root),
                        "--package",
                        str(package),
                        "--parameter-schema-report",
                        str(schema),
                        "--source-provenance-report",
                        str(provenance),
                        "--translucency-sorting-report",
                        str(sorting),
                        "--resume-cache",
                    ]
                )
            self.assertEqual(code, 0, stderr)
            first_report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertEqual(first_report["summary"]["cached_count"], 0)

            with patch("unreal_material_tools.material_delivery_smoke.subprocess.run", side_effect=AssertionError("cache miss")):
                code, stdout, stderr = run_tool(
                    [
                        "--root",
                        str(root),
                        "--package",
                        str(package),
                        "--parameter-schema-report",
                        str(schema),
                        "--source-provenance-report",
                        str(provenance),
                        "--translucency-sorting-report",
                        str(sorting),
                        "--resume-cache",
                    ]
                )
            self.assertEqual(code, 0, stderr)
            second_report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertGreaterEqual(second_report["summary"]["cached_count"], 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
