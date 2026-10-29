from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import material_instance_batch as mib


PARENT = "/Game/Materials/M_Master"
FACTS = {
    "parents": {PARENT: {"exists": True, "parameters": [
        {"name": "Roughness", "type": "Scalar"}, {"name": "Tint", "type": "Vector"},
        {"name": "UseNoise", "type": "StaticSwitch"}, {"name": "Mask", "type": "Texture"},
    ]}},
    "instances": {"/Game/Materials/MI_New": {"exists": False, "parent": ""},
                  "/Game/Materials/MI_Old": {"exists": True, "parent": "/Game/Materials/M_Master.M_Master"},
                  "/Game/Materials/MI_Other": {"exists": True, "parent": "/Game/Materials/M_Else.M_Else"}},
}


def spec(*instances):
    return {"parent_path": PARENT, "instances": list(instances)}


class PlanTests(unittest.TestCase):
    def test_new_instance_gets_create_params_and_save_with_readbacks(self):
        steps, problems = mib.build_plan(spec({"path": "/Game/Materials/MI_New", "params": [
            {"name": "Roughness", "type": "scalar", "value": "0.4"},
            {"name": "Tint", "type": "vector", "value": '{"r": 1, "g": 0.5}'},
            {"name": "UseNoise", "type": "static_switch", "value": "on"},
            {"name": "Mask", "type": "texture", "value": "/Game/T/T_Mask"},
        ]}), FACTS, reuse_existing=False)
        self.assertEqual(problems, [])
        self.assertEqual([s["kind"] for s in steps], ["create", "param", "param", "param", "param", "save"])
        create = steps[0]
        self.assertEqual(create["args"], {"folder_path": "/Game/Materials", "asset_name": "MI_New",
                                          "parent": {"refPath": "/Game/Materials/M_Master.M_Master"}})
        self.assertEqual(create["expect"], {"parent": {"refPath": "/Game/Materials/M_Master.M_Master"}})
        self.assertEqual(steps[1]["expect"], 0.4)
        self.assertEqual(steps[2]["args"]["value"], {"r": 1.0, "g": 0.5, "b": 0.0, "a": 1.0})
        self.assertIs(steps[3]["expect"], True)
        self.assertEqual(steps[4]["expect"], {"refPath": "/Game/T/T_Mask.T_Mask"})
        self.assertEqual(steps[1]["args"]["instance"], {"refPath": "/Game/Materials/MI_New.MI_New"})
        self.assertEqual(steps[-1]["args"], {"asset_paths": ["/Game/Materials/MI_New"]})
        self.assertIs(steps[-1]["expect"], False)

    def test_problems_block_instead_of_skipping(self):
        steps, problems = mib.build_plan(spec(
            {"path": "/Game/Materials/MI_New", "params": [{"name": "Rougness", "type": "scalar", "value": 1},
                                                          {"name": "Tint", "type": "scalar", "value": 1},
                                                          {"name": "X", "type": "font", "value": 1}]},
            {"path": "/Game/Materials/MI_Old"},
        ), FACTS, reuse_existing=False)
        joined = "\n".join(problems)
        self.assertIn("no Scalar parameter 'Rougness'", joined)
        self.assertIn("no Scalar parameter 'Tint'", joined)
        self.assertIn("unsupported type 'font'", joined)
        self.assertIn("MI_Old: already exists", joined)

    def test_reuse_requires_same_parent(self):
        steps, problems = mib.build_plan(spec({"path": "/Game/Materials/MI_Old"}, {"path": "/Game/Materials/MI_Other"}),
                                         FACTS, reuse_existing=True)
        self.assertEqual([s["kind"] for s in steps], ["save"])
        self.assertIn("refusing to reparent", problems[0])

    def test_missing_parent(self):
        _, problems = mib.build_plan({"parent_path": "/Game/Nope", "instances": [{"path": "/Game/M/MI"}]},
                                     {"parents": {"/Game/Nope": {"exists": False, "parameters": []}}, "instances": {}},
                                     reuse_existing=False)
        self.assertIn("does not exist", problems[0])


class ReportTests(unittest.TestCase):
    def test_rows_keep_legacy_shape(self):
        steps, _ = mib.build_plan(spec(
            {"path": "/Game/Materials/MI_New", "params": [{"name": "Roughness", "type": "scalar", "value": 1},
                                                          {"name": "Tint", "type": "vector", "value": {"r": 1}}]},
            {"path": "/Game/Materials/MI_Old", "params": [{"name": "Roughness", "type": "scalar", "value": 1}]},
        ), FACTS, reuse_existing=True)
        entries = [{**step, "_line": index + 2} for index, step in enumerate(steps)]
        statuses = ["ok", "ok", "mismatch", "skipped", "skipped", "skipped"]
        batch = {"results": [{"line": e["_line"], "status": s, "error": "x" if s != "ok" else ""} for e, s in zip(entries, statuses)]}
        rows = {row["path"]: row for row in mib.instance_rows(entries, batch, spec(*[{"path": e["instance"]} for e in entries]))}
        new, old = rows["/Game/Materials/MI_New"], rows["/Game/Materials/MI_Old"]
        self.assertTrue(new["create"]["success"])
        self.assertEqual((new["set_params"]["applied"], new["set_params"]["skipped"]), (1, ["Tint"]))
        self.assertFalse(new["set_params"]["success"])
        self.assertTrue(old["create"]["reused_existing"])
        self.assertTrue(old["create"]["success"])
        self.assertFalse(old["save"]["success"])

    def test_values(self):
        self.assertEqual(mib.normalize_value("vector", "(R=1,G=0.6,B=0.2,A=0.5)"), {"r": 1.0, "g": 0.6, "b": 0.2, "a": 0.5})
        self.assertEqual(mib.normalize_value("texture", {"refPath": "/Game/T/T_A.T_A"}), {"refPath": "/Game/T/T_A.T_A"})
        self.assertEqual(mib.asset_path("/Game/M/MI_X.MI_X"), "/Game/M/MI_X")
        with self.assertRaises(ValueError):
            mib.normalize_value("static_switch", "maybe")


if __name__ == "__main__":
    unittest.main(verbosity=2)
