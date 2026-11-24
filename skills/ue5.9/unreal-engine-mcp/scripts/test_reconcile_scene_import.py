import copy
import json
import tempfile
import unittest
from pathlib import Path

from reconcile_scene_import import Editor, GLTF_PARENT, apply_selected, capture, object_path, plan, source_manifest


LEVEL = "/Game/Test/L_Test"
ROOT = "/Game/Test/Import"
ASSET = ROOT + "/MI_Shelf.MI_Shelf"
FIELD = "Scalar:RoughnessFactor"
KEY = f"materials|{ASSET}|{FIELD}"


def manifest(value):
    return {"level": LEVEL, "projectFile": "/work/Scene.uproject", "actors": {},
            "materials": {ASSET: {"parent": GLTF_PARENT, FIELD: value}}}


class MemoryEditor:
    level = LEVEL
    project = "/work/Scene.uproject"

    def __init__(self, value=.1):
        self.mat = manifest(value)["materials"][ASSET]
        self.modified = False
        self.writes = []
        self.saves = []

    def check_world(self):
        pass

    def dirty(self, asset):
        return self.modified

    def read_material(self, asset, fields):
        return self.mat.copy()

    def check_material_path(self, asset):
        if asset != ASSET:
            raise ValueError("Unexpected material")

    def effective_value(self, asset, field):
        return self.mat[field]

    def set_parameter(self, asset, field, value):
        self.writes.append((asset, field, value))
        self.mat[field] = value
        self.modified = True

    def save(self, asset):
        self.saves.append(asset)
        self.modified = False


class SceneImportTests(unittest.TestCase):
    def setUp(self):
        self.candidate = plan(manifest(.1), manifest(.5), manifest(.1))

    def test_three_way_and_float_tolerance(self):
        for a, b, c, status in [(.1, .1, .9, "keep_editor"), (.1, .5, .9, "conflict"),
                                (.1, .5, .100001, "source_update"), (.1, .5, .500001, "equal")]:
            with self.subTest(status=status):
                out = plan(manifest(a), manifest(b), manifest(c))
                self.assertEqual(out["counts"][status], 1 if status != "equal" else 2)
                if status != "equal":
                    self.assertEqual(out["differences"][KEY]["selectable"], status == "source_update")

    def test_parent_or_missing_asset_is_review_only(self):
        live = manifest(.1)
        live["materials"][ASSET]["parent"] = "/Game/Manual/Parent.Parent"
        self.assertFalse(plan(manifest(.1), manifest(.5), live)["differences"][KEY]["selectable"])
        del live["materials"][ASSET]
        self.assertEqual(plan(manifest(.1), manifest(.5), live)["differences"][KEY]["status"], "review_structure")

    def test_apply_rechecks_and_repeated_run_has_zero_writes(self):
        editor = MemoryEditor()
        self.assertEqual(apply_selected(editor, self.candidate, ROOT, [KEY])["items"][0]["status"], "saved_verified")
        self.assertEqual(apply_selected(editor, self.candidate, ROOT, [KEY])["items"][0]["status"], "already_current")
        self.assertEqual((len(editor.writes), len(editor.saves)), (1, 1))

    def test_scope_dirty_stale_and_reparented_refuse_before_write(self):
        for case in ("scope", "dirty", "stale", "parent"):
            with self.subTest(case=case):
                editor = MemoryEditor(.2 if case == "stale" else .1)
                editor.modified = case == "dirty"
                if case == "parent":
                    editor.mat["parent"] = "/Game/P.P"
                root = "/Game/Test/Im" if case == "scope" else ROOT
                self.assertFalse(apply_selected(editor, self.candidate, root, [KEY])["ok"])
                self.assertFalse(editor.writes)

    def test_partial_and_unknown_write_are_never_replayed(self):
        class FailedSave(MemoryEditor):
            def save(self, asset):
                raise TimeoutError("save response interrupted")
        editor = FailedSave()
        report = apply_selected(editor, self.candidate, ROOT, [KEY])
        self.assertFalse(report["ok"])
        self.assertEqual(report["items"][0]["status"], "save_attempted_inspect_before_retry")
        self.assertFalse(apply_selected(editor, self.candidate, ROOT, [KEY])["ok"])
        self.assertEqual(len(editor.writes), 1)

    def test_other_project_unbound_capture_and_noncanonical_path_cannot_write(self):
        editor = MemoryEditor()
        for project in (None, "/another/Scene.uproject"):
            self.assertFalse(apply_selected(editor, {**self.candidate, "projectFile": project}, ROOT, [KEY])["ok"])
        self.assertFalse(editor.writes)
        self.assertFalse(object_path(ROOT + "/../Outside.Outside"))
        self.assertFalse(object_path(ROOT + "/Wrong.Subobject"))
        self.assertFalse(object_path(ROOT + "/Folder\\Outside.Outside"))

    def test_save_failure_journals_successful_writes_separately(self):
        class BadGetter(MemoryEditor):
            def effective_value(self, asset, field):
                return .33 if self.writes else self.mat[field]
        editor = BadGetter()
        states = []
        out = apply_selected(editor, self.candidate, ROOT, [KEY], lambda s: states.append(copy.deepcopy(s)))
        self.assertFalse(out["ok"])
        self.assertFalse(editor.saves)
        self.assertEqual(states[0]["items"][0]["status"], "write_attempted_inspect_before_retry")

    def test_duplicate_labels_preserve_both_and_missing_actor_is_reported(self):
        class Scene(MemoryEditor):
            def actor_index(self):
                return {"a": ("Shelf", "Furniture"), "b": ("Shelf", "Furniture")}
        src = manifest(.1)
        src["actors"] = {"first": {"actor": "a", "label": "Shelf"}, "second": {"actor": "missing", "label": "Chair"}}
        snap = capture(Scene(), src, src)
        self.assertIn("Duplicate", snap["issues"]["actors|first"])
        self.assertIn("missing", snap["issues"]["actors|second"])
        self.assertFalse(snap["actors"])

    def test_named_slot_and_instance_override_are_independent(self):
        base = manifest(.1)
        base["actors"]["door"] = {"slot:Oak": "/Game/Oak.Oak", "overrides": {}}
        source, current = copy.deepcopy(base), copy.deepcopy(base)
        source["actors"]["door"]["slot:Oak"] = "/Game/Birch.Birch"
        current["actors"]["door"]["overrides"] = {"Oak": "/Game/Art.Art"}
        changes = plan(base, source, current)["differences"]
        self.assertEqual(changes["actors|door|overrides"]["status"], "keep_editor")
        self.assertEqual(changes["actors|door|slot:Oak"]["status"], "source_update")
        self.assertFalse(changes["actors|door|slot:Oak"]["selectable"])

    def test_layered_override_and_inherited_value(self):
        class Materials:
            def call(self, group, tool, **args):
                if tool == "GetProperties":
                    return {"parent": {"refPath": GLTF_PARENT}, "textureParameterValues": [], "vectorParameterValues": [],
                            "scalarParameterValues": [{"parameterInfo": {"name": "X", "association": "LayerParameter",
                                                                          "index": 0}, "parameterValue": 2.0}]}
                if tool == "ListParameters":
                    return [{"name": "X", "type": "Scalar"}, {"name": "Y", "type": "Scalar"}]
                assert tool == "GetScalarParameter" and args["name"] == "Y"
                return .33
        live = Editor.read_material(Materials(), ASSET, ["Scalar:X", "Scalar:Y"])
        self.assertEqual(live, {"parent": GLTF_PARENT, "Scalar:Y": .33})

    def test_gltf_texture_mapping_and_shared_mesh_instances(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp, "room.gltf")
            file.write_text(json.dumps({"materials": [{"name": "M", "pbrMetallicRoughness": {"baseColorTexture": {"index": 1}}}],
                                        "textures": [{"source": 1}, {"source": 0}], "images": [{"name": "T1"}, {"name": "T2"}]}))
            assets = {"mesh": "/Game/S.S", "M": "/Game/M.M", "T1": "/Game/T1.T1"}
            group = {"name": "a", "meshName": "mesh", "folder": "F", "pivotUE": [1, 2, 3], "slots": ["M"]}
            placement = {"groups": [group, {**group, "name": "b"}]}
            def make(a, b):
                return source_manifest(file, placement, assets, {"a": a, "b": b}, LEVEL, GLTF_PARENT, "", "", "")
            spec = make("A", "B")
            self.assertEqual(spec["materials"]["/Game/M.M"]["Texture:BaseColorTexture"], "/Game/T1.T1")
            self.assertEqual(len(spec["actors"]), 2)
            with self.assertRaisesRegex(ValueError, "Repeated placement"):
                make("A", "A")

    def test_source_name_and_prefixed_ue_slot_resolve_to_the_same_material(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp, "room.gltf")
            file.write_text(json.dumps({"materials": [{"name": "Oak"}]}))
            group = {"name": "Shelf", "meshName": "SM_Shelf", "folder": "", "pivotUE": [0, 0, 0],
                     "slots": ["Oak"]}
            mesh, oak = "/Game/SM_Shelf.SM_Shelf", "/Game/MI_Oak.MI_Oak"

            def generate(mapping):
                return source_manifest(file, {"groups": [group]}, mapping, {}, LEVEL, GLTF_PARENT, "", "", "MI_")

            expected = generate({"SM_Shelf": mesh, "Oak": oak})
            self.assertEqual(expected["actors"]["Shelf"]["slot:MI_Oak"], oak)
            self.assertIn(oak, expected["materials"])
            self.assertEqual(generate([{"refPath": mesh}, {"refPath": oak}]), expected)
            group["slots"] = ["MI_Oak"]
            self.assertEqual(generate({"SM_Shelf": mesh, "Oak": oak}), expected)
            with self.assertRaisesRegex(ValueError, "unambiguous"):
                generate({"SM_Shelf": mesh, "Oak": oak, "MI_Oak": "/Game/Alt.Alt"})

    def test_unnamed_gltf_material_and_base_color_image_use_separate_indices(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp, "room.gltf")
            file.write_text(json.dumps({"materials": [{"pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}],
                                        "textures": [{"source": 1}], "images": [{"name": "Other"}, {}]}))
            material, texture = "/Game/MI_Oak.MI_Oak", "/Game/T_Oak.T_Oak"
            def generate(mapping):
                return source_manifest(file, {"groups": []}, mapping, {}, LEVEL, GLTF_PARENT, "", "", "")
            mapped = generate({"material:0": material, "image:1": texture})
            self.assertEqual(mapped["materials"][material]["Texture:BaseColorTexture"], texture)
            with self.assertRaisesRegex(ValueError, "image:1"):
                generate({"material:0": material, "image:0": texture})


if __name__ == "__main__":
    unittest.main()
