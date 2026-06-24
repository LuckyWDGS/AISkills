from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import material_toolset_builder


def recipe_args(root: Path, recipe: str = "fire-ribbon") -> argparse.Namespace:
    return argparse.Namespace(
        root=str(root),
        recipe=recipe,
        recipe_key="",
        effect="WingEcho",
        layer="RibbonTrail",
        intent=None,
        carrier=None,
        folder_path="/Game/Materials/VFX",
        asset_name=None,
        out=None,
        build_spec_out=None,
        build_report_out=None,
        inline_build_spec=True,
        execute=False,
        project=None,
        endpoint=None,
        timeout=180,
        markdown=False,
    )


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = material_toolset_builder.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class MaterialToolsetBuilderTests(unittest.TestCase):
    def test_fire_ribbon_alias_resolves(self) -> None:
        self.assertEqual(material_toolset_builder.recipe_key("fire-ribbon"), "fire_ribbon_additive")
        self.assertEqual(material_toolset_builder.recipe_key("flame-trail"), "fire_ribbon_additive")
        self.assertEqual(material_toolset_builder.recipe_key("fire-ribbon-android"), "fire_ribbon_additive_android")
        self.assertEqual(material_toolset_builder.recipe_key("flame-trail-android"), "fire_ribbon_additive_android")

    def test_fire_ribbon_recipe_report_and_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = recipe_args(root)
            report, out, spec_path = material_toolset_builder.build_recipe_report(args)
            spec = report["builder_spec"]
            route = report["route"]

            self.assertEqual(report["recipe"], "fire_ribbon_additive")
            self.assertEqual(report["carrier"], "ribbon")
            self.assertEqual(route["domain"], "Surface")
            self.assertEqual(route["blend_mode"], "Additive")
            self.assertEqual(route["shading_model"], "Unlit")
            self.assertTrue(route["two_sided"])
            self.assertEqual(route["usage_flags"], ["NiagaraRibbons"])
            self.assertEqual(out.name, "material-toolset-recipe.json")
            self.assertEqual(spec_path.name, "material-builder-spec.json")

            texture = report["texture_requirements"][0]
            self.assertEqual(texture["name"], "T_FireRibbonMask_VFX")
            self.assertFalse(texture["sRGB"])
            self.assertEqual(texture["compression"], "Masks")
            self.assertTrue(texture["required"])

            parameter_names = {item["name"] for item in report["parameters"]}
            self.assertEqual(
                parameter_names,
                {
                    "Texture_Mask",
                    "Color_Main",
                    "Color_Core",
                    "Intensity",
                    "Core_Boost",
                    "OpacityScale",
                    "Width_Power",
                    "Distortion_Intensity",
                    "Speed_Main",
                    "Speed_Noise",
                    "Tiling_Length",
                    "Use_Flow_UV_Remap",
                    "S_DynamicEmissiveBoost",
                    "S_DynamicOpacityBoost",
                },
            )

            expression_classes = {item["expression_class"] for item in spec["expressions"]}
            self.assertTrue(
                {
                    "/Script/Engine.MaterialExpressionTextureSampleParameter2D",
                    "/Script/Engine.MaterialExpressionParticleColor",
                    "/Script/Engine.MaterialExpressionDynamicParameter",
                    "/Script/Engine.MaterialExpressionTime",
                    "/Script/Engine.MaterialExpressionPanner",
                    "/Script/Engine.MaterialExpressionAppendVector",
                    "/Script/Engine.MaterialExpressionSubtract",
                    "/Script/Engine.MaterialExpressionAbs",
                    "/Script/Engine.MaterialExpressionOneMinus",
                    "/Script/Engine.MaterialExpressionClamp",
                    "/Script/Engine.MaterialExpressionPower",
                    "/Script/Engine.MaterialExpressionLinearInterpolate",
                }.issubset(expression_classes)
            )
            expression_locations = [
                (item["expression_class"], item["x"], item["y"])
                for item in spec["expressions"]
            ]
            self.assertEqual(len(expression_locations), len(set(expression_locations)))

            texture_sample_aliases = [
                item["alias"]
                for item in spec["expressions"]
                if item["expression_class"] == "/Script/Engine.MaterialExpressionTextureSampleParameter2D"
            ]
            self.assertEqual(texture_sample_aliases, ["mask_texture_noise", "mask_texture"])
            expected_mask_properties = [
                {"name": "ParameterName", "value": "Texture_Mask"},
                {"name": "Texture", "value": "/Game/Materials/VFX/T_FireRibbonMask_VFX.T_FireRibbonMask_VFX"},
            ]
            for alias in texture_sample_aliases:
                mask_props = next(item for item in spec["expression_properties"] if item["expression"] == alias)
                self.assertEqual(mask_props["properties"], expected_mask_properties)

            connections = {
                (
                    item["from_expression"],
                    item["from_output_name"],
                    item["to_expression"],
                    item["to_input_name"],
                )
                for item in spec["connections"]
            }
            self.assertIn(("flow_uv_raw", "", "main_panner_raw", "Coordinate"), connections)
            self.assertIn(("time_main", "", "main_panner_raw", "Time"), connections)
            self.assertIn(("flow_uv_remap", "", "main_panner_remap", "Coordinate"), connections)
            self.assertIn(("time_main", "", "main_panner_remap", "Time"), connections)
            self.assertIn(("noise_uv", "", "mask_texture_noise", "Coordinates"), connections)
            self.assertIn(("main_uv", "", "mask_texture", "Coordinates"), connections)
            self.assertIn(("width_center_fade", "", "width_clamped", "Input"), connections)
            self.assertIn(("width_clamped", "", "width_falloff", "Base"), connections)
            self.assertIn(("width_power", "", "width_falloff", "Exponent"), connections)

            output_props = {item["material_property"] for item in spec["output_connections"]}
            self.assertEqual(output_props, {"MP_EmissiveColor", "MP_Opacity"})
            self.assertIn("--carrier ribbon --with-complexity", report["preview_plan"]["command"])
            self.assertTrue(any("packed-mask" in warning for warning in report["warnings"]))
            self.assertTrue(any("first-pass" in warning for warning in report["warnings"]))
            self.assertTrue(any("same folder" in warning for warning in report["warnings"]))

    def test_fire_ribbon_android_recipe_is_one_sample_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = recipe_args(root, recipe="fire-ribbon-android")
            report, _out, _spec_path = material_toolset_builder.build_recipe_report(args)
            spec = report["builder_spec"]

            self.assertEqual(report["recipe"], "fire_ribbon_additive_android")
            self.assertEqual(report["carrier"], "ribbon")
            self.assertEqual(report["route"]["usage_flags"], ["NiagaraRibbons"])

            parameter_names = {item["name"] for item in report["parameters"]}
            self.assertEqual(
                parameter_names,
                {
                    "Texture_Mask",
                    "Color_Main",
                    "Color_Core",
                    "Intensity",
                    "Core_Boost",
                    "OpacityScale",
                    "Width_Power",
                    "Speed_Main",
                    "Tiling_Length",
                    "Use_Flow_UV_Remap",
                    "S_DynamicEmissiveBoost",
                    "S_DynamicOpacityBoost",
                },
            )
            self.assertNotIn("Distortion_Intensity", parameter_names)
            self.assertNotIn("Speed_Noise", parameter_names)

            expression_classes = {item["expression_class"] for item in spec["expressions"]}
            self.assertTrue(
                {
                    "/Script/Engine.MaterialExpressionTextureSampleParameter2D",
                    "/Script/Engine.MaterialExpressionTime",
                    "/Script/Engine.MaterialExpressionPanner",
                    "/Script/Engine.MaterialExpressionClamp",
                    "/Script/Engine.MaterialExpressionPower",
                    "/Script/Engine.MaterialExpressionLinearInterpolate",
                    "/Script/Engine.MaterialExpressionParticleColor",
                    "/Script/Engine.MaterialExpressionDynamicParameter",
                }.issubset(expression_classes)
            )
            expression_locations = [
                (item["expression_class"], item["x"], item["y"])
                for item in spec["expressions"]
            ]
            self.assertEqual(len(expression_locations), len(set(expression_locations)))

            texture_sample_aliases = [
                item["alias"]
                for item in spec["expressions"]
                if item["expression_class"] == "/Script/Engine.MaterialExpressionTextureSampleParameter2D"
            ]
            self.assertEqual(texture_sample_aliases, ["mask_texture"])
            self.assertNotIn("mask_texture_noise", {item["alias"] for item in spec["expressions"]})

            connections = {
                (
                    item["from_expression"],
                    item["from_output_name"],
                    item["to_expression"],
                    item["to_input_name"],
                )
                for item in spec["connections"]
            }
            self.assertIn(("main_uv", "", "mask_texture", "Coordinates"), connections)
            self.assertIn(("flow_uv_raw", "", "main_panner_raw", "Coordinate"), connections)
            self.assertIn(("time_main", "", "main_panner_raw", "Time"), connections)
            self.assertIn(("flow_uv_remap", "", "main_panner_remap", "Coordinate"), connections)
            self.assertIn(("width_center_fade", "", "width_clamped", "Input"), connections)
            self.assertIn(("width_clamped", "", "width_falloff", "Base"), connections)

            output_props = {item["material_property"] for item in spec["output_connections"]}
            self.assertEqual(output_props, {"MP_EmissiveColor", "MP_Opacity"})
            self.assertTrue(any("one Texture_Mask sample" in warning for warning in report["warnings"]))

    def test_list_recipes_includes_fire_ribbon(self) -> None:
        code, stdout, stderr = run_tool(["list-recipes", "--json"])

        self.assertEqual(code, 0, stderr)
        rows = json.loads(stdout)
        self.assertIn("fire_ribbon_additive", rows)
        self.assertEqual(rows["fire_ribbon_additive"]["carrier"], "ribbon")
        self.assertIn("fire_ribbon_additive_android", rows)
        self.assertEqual(rows["fire_ribbon_additive_android"]["carrier"], "ribbon")


if __name__ == "__main__":
    unittest.main(verbosity=2)
