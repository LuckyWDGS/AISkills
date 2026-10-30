"""Offline CLI checks for the Niagara workflow tools that had no coverage.

The reference -> anchor -> layer map -> evidence -> diff -> diagnosis chain runs end to end in one
project root; the editor-facing smokes run against a refused or fake MCP connection.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from vfx_delivery.niagara_plan_apply import apply_plan
from vfx_delivery import (
    asset_plan, delivery_chain_smoke, design_compare, gap_diagnosis, integration_plan, layer_evidence, learning_loop,
    niagara_asset_assistant, niagara_audit, reference_acceptance, reference_cache, tuning_log, ue_smoke, visual_diff_qa,
    visual_layer_map,
)


def run_tool(module, args: list[str]) -> tuple[int, str]:
    with redirect_stdout(StringIO()) as stdout, redirect_stderr(StringIO()):
        code = module.main(args)
    return code, stdout.getvalue().strip()


def flame_image(path: Path, offset: int = 0) -> Path:
    image = Image.new("RGBA", (160, 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((40 + offset, 20, 110 + offset, 100), fill=(255, 140, 20, 255))
    draw.ellipse((60 + offset, 40, 90 + offset, 80), fill=(255, 240, 200, 255))
    image.save(path)
    return path


class ReferenceChainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def tool(self, module, *args: str) -> tuple[int, str]:
        return run_tool(module, ["--root", str(self.root), *args])

    def register_anchor(self) -> dict:
        source = flame_image(self.root / "design.png")
        code, printed = self.tool(reference_cache, "register", str(source), "--effect", "Fireball", "--label", "design")
        self.assertEqual(code, 0)
        return json.loads(printed)

    def lock_anchor(self, entry_id: str) -> None:
        code, _ = self.tool(reference_acceptance, "review", entry_id, "--effect", "Fireball", "--status", "approved",
                            "--implementation-scope", "full effect", "--scope-confirmed", "--lock-anchor")
        self.assertEqual(code, 0)

    def test_reference_cache_derives_and_moves_entries(self) -> None:
        entry = self.register_anchor()
        self.assertEqual(entry["size"], {"width": 160, "height": 120})
        self.assertTrue((self.root / entry["cached_path"]).is_file())

        _, printed = self.tool(reference_cache, "crop", entry["id"], "--left", "40", "--top", "20",
                               "--right", "120", "--bottom", "100")
        crop = json.loads(printed)
        self.assertEqual((crop["kind"], crop["derived_from"], crop["size"]), ("crop", entry["id"], {"width": 80, "height": 80}))
        _, printed = self.tool(reference_cache, "hq", crop["id"], "--scale", "2")
        self.assertEqual(json.loads(printed)["size"], {"width": 160, "height": 160})

        _, printed = self.tool(reference_cache, "set-status", crop["id"], "--status", "rejected")
        moved = json.loads(printed)
        self.assertIn("rejected", Path(moved["cached_path"]).parts)
        with self.assertRaisesRegex(SystemExit, "Unknown reference entry id"):
            self.tool(reference_cache, "crop", "missing", "--left", "0", "--top", "0", "--right", "1", "--bottom", "1")

    def test_layer_map_requires_a_locked_anchor(self) -> None:
        entry = self.register_anchor()
        self.tool(visual_layer_map, "init", "--effect", "Fireball", "--anchor-reference-id", entry["id"])
        with self.assertRaisesRegex(SystemExit, "no locked anchor"):
            self.tool(visual_layer_map, "add-layer", "--effect", "Fireball", "--name", "Core")
        self.lock_anchor(entry["id"])
        self.assertEqual(self.tool(visual_layer_map, "add-layer", "--effect", "Fireball", "--name", "Core",
                                   "--self-test", "core stays brightest")[0], 0)
        with self.assertRaisesRegex(SystemExit, "Layer already exists"):
            self.tool(visual_layer_map, "add-layer", "--effect", "Fireball", "--name", "Core")

    def test_evidence_diff_and_diagnosis_chain(self) -> None:
        entry = self.register_anchor()
        self.lock_anchor(entry["id"])
        self.tool(visual_layer_map, "init", "--effect", "Fireball", "--anchor-reference-id", entry["id"])
        self.tool(visual_layer_map, "add-layer", "--effect", "Fireball", "--name", "Core")

        code, printed = self.tool(layer_evidence, "suggest", entry["id"], "--count", "3")
        self.assertEqual(code, 0)
        suggestions = json.loads(Path(printed).read_text(encoding="utf-8"))["suggestions"]
        self.assertTrue(1 <= len(suggestions) <= 3)
        code, printed = self.tool(layer_evidence, "attach", entry["id"], "--layer", "Core", "--suggestion-index", "0",
                                  "--silhouette", "round head")
        self.assertTrue(Path(printed).is_file())
        _, printed = self.tool(visual_layer_map, "show", "--effect", "Fireball")
        core = json.loads(printed)["layers"][0]
        self.assertEqual((core["evidence"]["reference_id"], core["evidence"]["silhouette"]), (entry["id"], "round head"))

        same = self.root / entry["cached_path"]
        _, printed = self.tool(visual_diff_qa, "--reference-id", entry["id"], "--preview-path", str(same),
                               "--effect", "Fireball", "--layer", "Core")
        self.assertEqual(json.loads(Path(printed).read_text(encoding="utf-8"))["metrics"]["mean_diff"], 0)
        shifted = flame_image(self.root / "preview.png", offset=30)
        _, printed = self.tool(visual_diff_qa, "--reference-id", entry["id"], "--preview-path", str(shifted),
                               "--effect", "Fireball", "--layer", "Core")
        report = json.loads(Path(printed).read_text(encoding="utf-8"))
        self.assertGreater(report["metrics"]["mask_delta"], 0)
        self.assertGreater(report["metrics"]["preview_centroid"][0], report["metrics"]["reference_centroid"][0])
        self.assertTrue(Path(report["outputs"]["composite_path"]).is_file())

        self.tool(gap_diagnosis, "add", "--id", "d1", "--effect", "Fireball", "--layer", "Core", "--symptom", "silhouette",
                  "--suspect-layer", "material", "--observation", "core drifts right", "--next-action", "recenter UVs")
        self.tool(gap_diagnosis, "set-status", "--effect", "Fireball", "--id", "d1", "--status", "fixed")
        _, printed = self.tool(gap_diagnosis, "list", "--effect", "Fireball", "--layer", "Core")
        rows = [json.loads(line) for line in printed.splitlines()]
        self.assertEqual([(row["id"], row["status"]) for row in rows], [("d1", "fixed")])
        _, printed = self.tool(gap_diagnosis, "export-md", "--effect", "Fireball")
        self.assertIn("core drifts right", Path(printed).read_text(encoding="utf-8"))

        code, printed = self.tool(design_compare, "generate", "--effect", "Fireball", "--layer", "Core")
        criteria = json.loads(Path(printed).read_text(encoding="utf-8"))["criteria"]
        self.tool(design_compare, "update", "--effect", "Fireball", "--layer", "Core", "--criterion", criteria[0]["name"],
                  "--status", "pass", "--observation", "matches")
        updated = json.loads(Path(printed).read_text(encoding="utf-8"))["criteria"][0]
        self.assertEqual((updated["status"], updated["observation"]), ("pass", "matches"))

    def test_asset_plan_feeds_the_niagara_template_plan(self) -> None:
        entry = self.register_anchor()
        self.lock_anchor(entry["id"])
        self.tool(visual_layer_map, "init", "--effect", "Fireball", "--anchor-reference-id", entry["id"])
        self.tool(visual_layer_map, "add-layer", "--effect", "Fireball", "--name", "Core")
        self.assertEqual(self.tool(asset_plan, "generate", "--effect", "Fireball", "--platform", "Android")[0], 0)
        _, printed = self.tool(asset_plan, "show", "--effect", "Fireball")
        plan = json.loads(printed)
        self.assertEqual(plan["naming"]["system_name"], "NS_Fireball")
        self.assertTrue(plan["assets"]["low_end_variant_required"])

        _, printed = self.tool(niagara_asset_assistant, "plan-template", "--effect", "Fireball",
                               "--template-system", "/Game/Templates/NS_Fire", "--fixed-bounds=-50,-50,-50,50,50,50")
        mutation = json.loads(Path(printed).read_text(encoding="utf-8"))
        self.assertEqual(mutation["target_system"], "/Game/VFX/Fireball/NS_Fireball")
        ops = [op["op"] for op in mutation["operations"]]
        self.assertEqual(ops[:2], ["duplicate_asset", "set_niagara_system_props"])

    def test_logs_and_plans_round_trip(self) -> None:
        self.lock_anchor(self.register_anchor()["id"])
        self.tool(tuning_log, "add", "--effect", "Fireball", "--asset-type", "MaterialInstance",
                  "--asset-path", "/Game/VFX/MI_Fire", "--parameter", "EmissiveIntensity", "--old-value", "4",
                  "--new-value", "6", "--reason", "core too dim", "--visual-gap", "brightness")
        _, printed = self.tool(tuning_log, "list", "--effect", "Fireball")
        self.assertEqual(json.loads(printed)["new_value"], "6")
        _, printed = self.tool(tuning_log, "export-md", "--effect", "Fireball")
        self.assertIn("EmissiveIntensity", Path(printed).read_text(encoding="utf-8"))

        self.tool(integration_plan, "generate", "--effect", "Fireball", "--socket", "hand_r", "--notify", "Cast")
        _, printed = self.tool(integration_plan, "show", "--effect", "Fireball")
        self.assertIn("hand_r", json.dumps(json.loads(printed)))

        self.tool(learning_loop, "add-lesson", "--effect", "Fireball", "--kind", "failure", "--text", "bounds too small")
        self.assertEqual(self.tool(learning_loop, "summarize", "--effect", "Fireball")[0], 0)
        _, printed = self.tool(learning_loop, "show", "--effect", "Fireball")
        self.assertEqual(json.loads(printed)["manual_lessons"], [{"kind": "failure", "text": "bounds too small"}])


class RepairPlanTests(unittest.TestCase):
    def test_repair_plan_reads_the_structured_audit(self) -> None:
        sprite = {"renderer_index": 0, "class_name": "NiagaraSpriteRendererProperties", "material_paths": []}
        bound = {"renderer_index": 1, "class_name": "NiagaraMeshRendererProperties", "material_paths": ["/Game/M_Mesh.M_Mesh"]}
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp, "audit.json")
            audit.write_text(json.dumps({
                "schema_version": "niagara_audit/3",
                "system_path": "/Game/VFX/NS_Fire",
                "system": {"fixed_bounds": None},
                "emitters": [
                    {"name": "Sparks", "role": "generic", "renderers": [sprite, bound]},
                    {"name": "Trail", "role": "trail-receiver", "roles": ["trail-receiver"], "renderers": []},
                    {"name": "Unused", "role": "generic", "renderers": []},
                ],
            }), encoding="utf-8")
            code, printed = run_tool(niagara_asset_assistant, ["--root", tmp, "repair-plan", "--audit", str(audit),
                                                                "--default-material", "/Game/VFX/MI_Fix",
                                                                "--fixed-bounds=-1,-1,-1,1,1,1"])
            plan = json.loads(Path(printed).read_text(encoding="utf-8"))
            dry = apply_plan(plan, execute=False)
        self.assertEqual(code, 0)
        self.assertEqual([op["op"] for op in plan["operations"]],
                         ["set_niagara_system_props", "patch_renderer_material", "add_ribbon_renderer", "save_assets"])
        patch_op = plan["operations"][1]
        self.assertEqual((patch_op["emitter_name"], patch_op["renderer_index"], patch_op["material_path"]),
                         ("Sparks", 0, "/Game/VFX/MI_Fix"))
        self.assertTrue(any("Unused" in warning for warning in plan["warnings"]))
        self.assertEqual(dry["status"], "planned")  # every repair has an MCP route


class FakeClient:
    def editor_owner(self):
        return {"project": "Demo"}

    def close(self):
        pass


class EditorSmokeTests(unittest.TestCase):
    def test_ue_smoke_records_a_refused_connection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(ue_smoke, "connect", side_effect=OSError("refused")):
            out = Path(tmp, "smoke.json")
            self.assertEqual(run_tool(ue_smoke, ["--root", tmp, "--out", str(out)])[0], 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual((report["status"], report["blocked_reason"]), ("blocked", "refused"))
            self.assertEqual(run_tool(ue_smoke, ["--root", tmp, "--out", str(out), "--require-ue"])[0], 2)

    def test_ue_smoke_passes_on_a_live_editor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.object(ue_smoke, "connect", return_value=FakeClient()):
            out = Path(tmp, "smoke.json")
            self.assertEqual(run_tool(ue_smoke, ["--root", tmp, "--out", str(out)])[0], 0)
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual((report["status"], report["ping"]), ("pass", {"project": "Demo"}))

    def test_delivery_chain_smoke_reports_a_blocked_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(niagara_audit, "command", side_effect=OSError("editor offline")):
            out = Path(tmp, "chain.json")
            args = ["--root", tmp, "--effect", "Fireball", "--final-system", "/Game/VFX/NS_Fire", "--out", str(out)]
            self.assertEqual(run_tool(delivery_chain_smoke, [*args, "--allow-blocked-ue"])[0], 0)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "blocked")
            steps = {step["name"]: step for step in report["steps"]}
            self.assertEqual(steps["audit:/Game/VFX/NS_Fire"]["error"], "editor offline")
            self.assertIn("delivery-package", steps)
            self.assertIn("delivery-dashboard", steps)
            self.assertTrue(report["delivery_index"])
            with self.assertRaises(OSError):  # without --allow-blocked-ue the editor failure propagates
                run_tool(delivery_chain_smoke, args)

    def test_delivery_chain_smoke_skip_audit_needs_no_editor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp, "chain.json")
            code, _ = run_tool(delivery_chain_smoke, ["--root", tmp, "--effect", "Fireball", "--final-system",
                                                      "/Game/VFX/NS_Fire", "--skip-audit", "--out", str(out),
                                                      "--require-ready"])
            report = json.loads(out.read_text(encoding="utf-8"))
        self.assertFalse(any(step["name"].startswith("audit:") for step in report["steps"]))
        self.assertNotEqual(report["delivery_overall"], "ready")  # no evidence was supplied
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
