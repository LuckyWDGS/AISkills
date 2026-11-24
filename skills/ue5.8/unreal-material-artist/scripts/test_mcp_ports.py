"""Offline checks for the tools ported from UnrealBridge to Epic MCP: their pure planning and report code."""

import json
from pathlib import Path
import unittest

from unreal_material_tools import material_audit, material_function_linter, material_toolset_builder as builder
from unreal_material_tools import runtime_param_trace, shader_permutation_report, texture_import_audit, texture_import_fix


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def texture_row(**tags):
    base = {"Format": "BC5", "CompressionSettings": "TC_Normalmap", "LODGroup": "TEXTUREGROUP_World",
            "SRGB": "False", "NeverStream": "False", "MipGenSettings": "TMGS_FromTextureGroup", "HasAlphaChannel": "False"}
    return texture_import_audit.texture_info({"asset_path": "/Game/T/T_X", "found": True,
                                              "size": {"x": 1024, "y": 512}, "tags": {**base, **tags}})


class TextureTests(unittest.TestCase):
    def test_tags_become_report_fields(self):
        info = texture_row(MipGenSettings="TMGS_NoMipmaps", SRGB="True")
        self.assertEqual((info["width"], info["height"], info["srgb"], info["num_mips"]), (1024, 512, True, 1))
        self.assertIsNone(texture_row()["num_mips"])  # mips generated, count unknown over MCP
        self.assertEqual(texture_import_audit.texture_info({"asset_path": "/Game/T/Missing", "found": False}),
                         {"asset_path": "/Game/T/Missing", "found": False})

    def test_role_findings(self):
        report = texture_import_audit.build_report([texture_row(SRGB="True")], role="mask", grid_text=None,
                                                   max_dimension=2048, max_resource_bytes=None)
        rules = {row["rule"] for row in report["textures"][0]["findings"]}
        self.assertEqual(rules, {"srgb_enabled"})
        self.assertTrue(report["coverage_gaps"])
        ui = texture_import_audit.build_report([texture_row()], role="ui", grid_text=None, max_dimension=2048,
                                               max_resource_bytes=None)
        self.assertIn("ui_mips", {row["rule"] for row in ui["textures"][0]["findings"]})

    def test_fix_plan_writes_only_changes_and_saves(self):
        changes = texture_import_fix.diff_profile(texture_row(), texture_import_fix.role_profile("mask", "color"))
        self.assertEqual(changes, {"compression_settings": "TC_Masks", "lod_group": "TEXTUREGROUP_Effects"})
        # Python-style enum spellings from older specs still compare equal.
        self.assertEqual(texture_import_fix.diff_profile({"compression_settings": "TC_Masks", "lod_group": "TEXTUREGROUP_EFFECTS",
                                                          "srgb": False, "never_stream": False},
                                                         {"compression_settings": "TC_MASKS", "lod_group": "TEXTUREGROUP_Effects",
                                                          "srgb": False, "never_stream": False}), {})
        steps = texture_import_fix.build_plan([{"texture_path": "/Game/T/T_X.T_X", "planned_changes": changes},
                                               {"texture_path": "/Game/T/T_Y", "planned_changes": {}}])
        self.assertEqual([step["kind"] for step in steps], ["set", "save"])
        self.assertEqual(json.loads(steps[0]["args"]["values"]), {"compressionSettings": "TC_Masks", "lODGroup": "TEXTUREGROUP_Effects"})
        self.assertEqual(steps[0]["expect"], json.loads(steps[0]["args"]["values"]))
        self.assertEqual(steps[1]["args"], {"asset_paths": ["/Game/T/T_X"]})


class AuditPortTests(unittest.TestCase):
    def test_permutation_groups(self):
        raw = {"total": 3, "instances": [
            {"path": "/Game/M/MI_A", "parents": ["/Script/Engine.Material'/Game/M/M_Base.M_Base'"],
             "switches": {"Grid": True}, "has_static_permutation": True},
            {"path": "/Game/M/MI_B", "parents": ["/Script/Engine.MaterialInstanceConstant'/Game/M/MI_A.MI_A'",
                                                  "/Script/Engine.Material'/Game/M/M_Base.M_Base'"],
             "switches": {"Grid": True}, "has_static_permutation": False},
            {"path": "/Game/M/MI_C", "parents": ["/Script/Engine.Material'/Game/M/M_Base.M_Base'"],
             "switches": {"Grid": False}, "has_static_permutation": False},
        ]}
        report = shader_permutation_report.build_report(raw, "/Game/M")
        first = report["groups"][0]
        self.assertEqual((first["base_path"], first["switch_signature"], first["max_chain_depth"]),
                         ("/Game/M/M_Base.M_Base", ["Grid=true"], 2))
        self.assertEqual(report["summary"], {"groups": 2, "bases": 1, "own_permutation_instances": 1})

    def test_function_lint(self):
        raw = {"total": 1, "functions": [{
            "path": "/Game/F/MF_X", "name": "MF_X", "num_expressions": 5,
            "info": {"description": "", "bExposeToLibrary": True, "libraryCategoriesText": ["Misc"]},
            "inputs": [{"inputName": "UV", "description": ""}, {"inputName": "UV", "description": "dup"}],
            "outputs": [], "static_switch_nodes": 3}]}
        report = material_function_linter.build_report(raw, "/Game/F")
        item = report["functions"][0]
        self.assertEqual(item["library_category"], "Misc")
        self.assertEqual({row["rule"] for row in item["findings"]},
                         {"undocumented_input", "duplicate_input", "no_outputs", "switch_sprawl"})

    def test_runtime_trace_links_material_and_niagara(self):
        data = json.loads((FIXTURES / "mcp-material-M_PrototypeGrid.json").read_text(encoding="utf-8"))
        audit = material_audit.build_report(data["asset_path"], data["raw"], data["outputs"], data["stats"])
        audit["material_info"]["vector_parameters"].append({"name": "Color", "param_type": "Vector"})
        niagara = {"tool": "niagara_audit", "system_path": "/Game/FX/NS_X",
                   "user_variables": [{"name": "User.Color", "defaultValue": {"value": {"r": 1}}}],
                   "emitters": [{"name": "Trail", "parsed": {"renderers": [{
                       "class_name": "NiagaraRibbonRendererProperties",
                       "renderer_data": {"MaterialUserParamBinding": {"parameter": {"name": "User.TrailMaterial"}}}}]}}]}
        report = runtime_param_trace.build_report(audit, niagara, [])
        sources = {(row["kind"], row["name"]) for row in report["niagara_parameter_sources"]}
        self.assertEqual(sources, {("user_variable", "User.Color"), ("renderer_binding", "User.TrailMaterial")})
        self.assertIn("Color", {row["material_param"] for row in report["runtime_links"]})
        self.assertIsNone(report["mi_parameters"])


class BuilderTests(unittest.TestCase):
    def test_values_and_route(self):
        self.assertEqual(builder.ue_property_value("True"), True)
        self.assertEqual(builder.ue_property_value("2.5"), 2.5)
        self.assertEqual(builder.ue_property_value("(R=1.0,G=0.5,B=0.25,A=1.0)"), {"r": 1.0, "g": 0.5, "b": 0.25, "a": 1.0})
        self.assertEqual(builder.ue_property_value("/Game/T/T_X"), {"refPath": "/Game/T/T_X.T_X"})
        self.assertEqual(builder.ue_property_name("ParameterName"), "parameterName")
        self.assertEqual(builder.route_properties({"domain": "Surface", "blend_mode": "Additive", "shading_model": "Unlit",
                                                   "two_sided": True})["blendMode"], "BLEND_Additive")

    def test_create_script_payload_is_python_safe(self):
        spec = {"folder_path": "/Game/X", "asset_name": "M_X", "route": {"two_sided": True, "usage_flags": ["NiagaraRibbons"]},
                "expressions": [{"alias": "a", "expression_class": "/Script/Engine.MaterialExpressionConstant"}]}
        script = builder.build_create_script(spec)
        compile(script, "create", "exec")  # JSON true/false must not leak into Python source
        self.assertIn("niagararibbons", script)

    def test_wiring_maps_legacy_pin_names(self):
        spec = {"expression_properties": [{"expression": "tex", "properties": [{"name": "Texture", "value": "/Game/T/T_Missing"},
                                                                               {"name": "ParameterName", "value": "Mask"}]}],
                "connections": [{"from_expression": "uv", "to_expression": "mask", "to_input_name": "Input"},
                                {"from_expression": "uv", "to_expression": "tex", "to_input_name": "Coordinates"},
                                {"from_expression": "uv", "to_expression": "tex", "to_input_name": "Nope"}],
                "output_connections": [{"expression": "tex", "material_property": "EmissiveColor", "output_name": "RGB"}]}
        aliases = {"uv": "/Game/X/M.M:UV", "mask": "/Game/X/M.M:Mask", "tex": "/Game/X/M.M:Tex"}
        pins = {"mask": {"in": ["None"], "out": [""]}, "tex": {"in": ["UVs", "Apply View MipBias"], "out": ["RGB"]}}
        steps, problems = builder.build_wiring_steps(spec, "/Game/X/M.M", aliases, pins, {"/Game/T/T_Missing.T_Missing"})
        connects = [step["args"]["to_input_name"] for step in steps if step["kind"] == "connect"]
        self.assertEqual(connects, ["", "UVs"])
        self.assertEqual(json.loads(steps[0]["args"]["values"]), {"parameterName": "Mask"})
        output = next(step for step in steps if step["kind"] == "output")
        self.assertEqual(output["args"]["material_property"], "MP_EmissiveColor")
        self.assertEqual(steps[-1]["kind"], "recompile")
        self.assertTrue(any("left at its default" in item for item in problems))
        self.assertTrue(any("'Nope'" in item for item in problems))

    def test_every_recipe_yields_a_valid_create_script(self):
        import argparse
        for key, definition in builder.RECIPE_DEFINITIONS.items():
            args = argparse.Namespace(recipe=key, recipe_key=key, root="auto", effect="E", layer="L", intent=None, carrier=None,
                                      folder_path="/Game/X", asset_name=f"M_{key}", execute=False, inline_build_spec=False)
            spec = builder.make_recipe_builder_spec(args, definition)
            compile(builder.build_create_script(spec), key, "exec")
            self.assertTrue(spec["expressions"], key)


if __name__ == "__main__":
    unittest.main()
