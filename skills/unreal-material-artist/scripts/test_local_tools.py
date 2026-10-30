"""Offline CLI checks for the local (editor-free) material tools that had no coverage."""

import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from unreal_material_tools import (
    channel_packer, flipbook_normalizer, graph_refactor_apply, material_asset_library, project_material_health,
    reference_to_material_plan, texture_asset_report,
)



def run(module, argv: list[str]) -> tuple[int, str]:
    with redirect_stdout(StringIO()) as stdout:
        code = module.main(argv)
    return code, stdout.getvalue().strip()


def solid(path: Path, size: tuple[int, int], color: tuple[int, int, int, int]) -> Path:
    Image.new("RGBA", size, color).save(path)
    return path


class ChannelPackerTests(unittest.TestCase):
    def test_packs_named_channels_and_constants(self):
        with tempfile.TemporaryDirectory() as folder:
            red = solid(Path(folder, "red.png"), (8, 8), (200, 10, 20, 255))
            green = solid(Path(folder, "green.png"), (4, 4), (0, 90, 0, 255))
            out = Path(folder, "packed.png")
            code, printed = run(channel_packer, ["--root", folder, "--r", f"{red}@R", "--g", f"{green}@G",
                                                 "--invert-g", "--fill-b", "7", "--out", str(out)])
            self.assertEqual(code, 0)
            report = json.loads(Path(printed).read_text(encoding="utf-8"))
            self.assertEqual((report["width"], report["height"]), (8, 8))
            with Image.open(out) as packed:
                # The smaller green source is resized to the first source; G is inverted, A keeps its default fill.
                self.assertEqual(packed.getpixel((3, 3)), (200, 255 - 90, 7, 255))

    def test_requires_a_source(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(SystemExit, "at least one channel source"):
                run(channel_packer, ["--root", folder])


class FlipbookNormalizerTests(unittest.TestCase):
    def test_splits_and_repacks_an_atlas(self):
        with tempfile.TemporaryDirectory() as folder:
            atlas = Image.new("RGBA", (64, 32), (0, 0, 0, 0))
            atlas.paste((255, 255, 255, 255), (4, 4, 20, 20))
            atlas.paste((255, 128, 0, 255), (40, 8, 56, 24))
            source = Path(folder, "atlas.png")
            atlas.save(source)
            out = Path(folder, "normalized.png")
            code, printed = run(flipbook_normalizer, [str(source), "--root", folder, "--source-grid", "2x1",
                                                      "--grid", "2x1", "--cell-size", "32", "--padding", "2",
                                                      "--pow2-atlas", "--out", str(out)])
            self.assertEqual(code, 0)
            report = json.loads(Path(printed).read_text(encoding="utf-8"))
            self.assertEqual((report["frame_count"], report["output_grid"]), (2, "2x1"))
            self.assertEqual((report["atlas_width"], report["atlas_height"]), (64, 32))
            self.assertTrue(report["atlas_power_of_two"])

    def test_auto_grid_reports_non_power_of_two(self):
        with tempfile.TemporaryDirectory() as folder:
            frames = [solid(Path(folder, f"f{index}.png"), (16, 16), (255, 255, 255, 255)) for index in range(3)]
            code, printed = run(flipbook_normalizer, [*map(str, frames), "--root", folder, "--cell-size", "24",
                                                      "--out", str(Path(folder, "auto.png"))])
            self.assertEqual(code, 0)
            report = json.loads(Path(printed).read_text(encoding="utf-8"))
            self.assertEqual(report["output_grid"], "2x2")
            self.assertFalse(report["atlas_power_of_two"])
            self.assertEqual(report["recommended_atlas_power_of_two"], {"width": 64, "height": 64})


class TextureAssetReportTests(unittest.TestCase):
    def test_flags_grid_and_data_texture_issues(self):
        with tempfile.TemporaryDirectory() as folder:
            atlas = solid(Path(folder, "atlas.png"), (96, 64), (255, 255, 255, 255))
            mask = solid(Path(folder, "mask.png"), (64, 64), (255, 0, 0, 255))
            out = Path(folder, "report.json")
            self.assertEqual(run(texture_asset_report, [str(atlas), "--root", folder, "--role", "flipbook",
                                                        "--grid", "4x4", "--out", str(out)])[0], 0)
            texture = json.loads(out.read_text(encoding="utf-8"))["textures"][0]
            self.assertFalse(texture["power_of_two"])
            self.assertEqual(texture["grid"]["cell_width"], 24)
            self.assertTrue(any("not square" in warning for warning in texture["warnings"]))

            self.assertEqual(run(texture_asset_report, [str(mask), "--root", folder, "--role", "mask",
                                                        "--out", str(out)])[0], 0)
            texture = json.loads(out.read_text(encoding="utf-8"))["textures"][0]
            self.assertTrue(texture["power_of_two"])
            self.assertTrue(any("sRGB disabled" in warning for warning in texture["warnings"]))


class ReferenceToMaterialPlanTests(unittest.TestCase):
    def test_new_plan_validates_and_seeds_a_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder, "plan.json")
            code, _ = run(reference_to_material_plan, ["new", "--root", folder, "--effect", "Fireball",
                                                       "--target", "additive fire ribbon trail", "--emit-contract",
                                                       "--out", str(out)])
            self.assertEqual(code, 0)
            plan = json.loads(out.read_text(encoding="utf-8"))
            for key in ("material_route", "texture_requirements", "parameters", "preview_plan", "audit_plan"):
                self.assertIn(key, plan)
            self.assertTrue(Path(plan["material_contract_path"]).is_file())
            self.assertEqual(run(reference_to_material_plan, ["validate", str(out)])[0], 0)

            del plan["material_route"]
            out.write_text(json.dumps(plan), encoding="utf-8")
            code, printed = run(reference_to_material_plan, ["validate", str(out)])
            self.assertEqual(code, 1)
            self.assertIn("missing_key", printed)


class ProjectMaterialHealthTests(unittest.TestCase):
    def test_scan_ranks_over_budget_materials(self):
        with tempfile.TemporaryDirectory() as folder:
            reports = Path(folder, "reports")
            reports.mkdir()
            light = {
                "tool": "material_audit",
                "material_path": "/Game/VFX/M_Light",
                "material_info": {"path": "/Game/VFX/M_Light"},
                "analysis": {"max_instructions": 90, "sampler_count": 2, "compile_errors": []},
            }
            (reports / "light.json").write_text(json.dumps(light), encoding="utf-8")
            heavy = {
                "tool": "material_audit",
                "material_path": "/Game/VFX/M_Heavy",
                "material_info": {"path": "/Game/VFX/M_Heavy", "static_switch_parameters": [{"name": "UseNoise"}]},
                "analysis": {"max_instructions": 600, "sampler_count": 20, "compile_errors": []},
                "graph_summary": {"dead_nodes": ["A", "B"]},
            }
            (reports / "heavy.json").write_text(json.dumps(heavy), encoding="utf-8")
            (reports / "broken.json").write_text("{not json", encoding="utf-8")
            out = Path(folder, "health.json")
            code, _ = run(project_material_health, ["scan", "--root", folder, "--report-root", str(reports),
                                                    "--out", str(out), "--strict"])
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertEqual(report["summary"]["invalid_report_count"], 1)
        self.assertEqual(report["summary"]["tool_counts"]["material_audit"], 2)
        top = report["hotlists"]["materials_by_score"][0]
        self.assertEqual(top["material_path"], "/Game/VFX/M_Heavy")
        self.assertFalse(report["gate"]["passed"])


class GraphRefactorApplyTests(unittest.TestCase):
    def test_patch_spec_becomes_a_plan_only_route(self):
        with tempfile.TemporaryDirectory() as folder:
            spec = Path(folder, "patch.json")
            spec.write_text(json.dumps({"target_material": "/Game/VFX/M_Fire", "operations": ["add_depth_fade"]}),
                            encoding="utf-8")
            out = Path(folder, "apply.json")
            code, _ = run(graph_refactor_apply, ["--root", folder, "--patch-spec", str(spec), "--out", str(out),
                                                 "--strict"])
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(code, 1)  # --strict: a plan is never ready for acceptance
        self.assertFalse(report["execute"])
        self.assertEqual(report["gate"], {"ready_for_acceptance": False, "reason": "plan_only"})
        self.assertEqual(report["apply_payload"]["operations"][0]["operation"], "add_depth_fade")
        self.assertIn("AssetTools.duplicate /Game/VFX/M_Fire", report["mcp_route"][0])
        self.assertTrue(report["review"]["review_required"])

    def test_needs_a_target(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(SystemExit) as raised, redirect_stderr(StringIO()) as stderr:
                run(graph_refactor_apply, ["--root", folder])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--patch-spec", stderr.getvalue())


class MaterialAssetLibraryTests(unittest.TestCase):
    def test_register_search_promote_round_trip(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(material_asset_library, "skill_root", return_value=Path(folder)):
            noise = solid(Path(folder, "noise.png"), (64, 64), (128, 128, 128, 255))
            code, printed = run(material_asset_library, ["register", str(noise), "--category", "noise",
                                                         "--role", "breakup", "--tags", "fire,smoke"])
            self.assertEqual(code, 0)
            record = json.loads(printed)
            self.assertEqual((record["stage"], record["category"]), ("candidates", "noise"))
            self.assertTrue(noise.exists())  # register copies unless --move

            _, printed = run(material_asset_library, ["search", "--stage", "candidates", "--tag", "fire"])
            self.assertEqual([item["id"] for item in json.loads(printed)["results"]], [record["id"]])
            _, printed = run(material_asset_library, ["search", "--tag", "fire"])
            self.assertEqual(json.loads(printed)["results"], [])  # search defaults to approved assets

            _, printed = run(material_asset_library, ["promote", record["id"], "--stage", "approved",
                                                      "--root", folder])
            promoted = json.loads(printed)["record"]
            self.assertEqual(promoted["stage"], "approved")
            _, printed = run(material_asset_library, ["status"])
            self.assertEqual(json.loads(printed)["by_stage"]["approved"], 1)

    def test_auto_promote_rejects_without_self_review(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(material_asset_library, "skill_root", return_value=Path(folder)):
            mask = solid(Path(folder, "mask.png"), (32, 32), (255, 255, 255, 255))
            _, printed = run(material_asset_library, ["register", str(mask), "--category", "mask", "--role", "edge"])
            asset_id = json.loads(printed)["id"]
            code, printed = run(material_asset_library, ["auto-promote", asset_id, "--self-review", "rejected"])
            self.assertEqual((code, json.loads(printed)["decision"]), (1, "rejected"))


if __name__ == "__main__":
    unittest.main()
