"""Offline tests: shot-plan normalization/validation, camera math, sequence lint, sample checks."""

import unittest

from sequence_sample import active_camera, angle_delta, check_keys
from sequencer_tools import inspect as seq_inspect
from sequencer_tools.plan import look_at_rotation, normalize, ray_box_entry, resolve_camera_keys, unwrap_yaws, validate

PLAN = {
    "sequence": {"path": "/Game/Cine/LS_Test", "fps": 30, "seconds": 6},
    "cameras": [
        {"id": "Wide", "keys": [{"time": 0, "location": [-600, 0, 300], "look_at": "Hero", "focal": 24, "focus": "auto"},
                                {"time": 3, "location": [-300, 0, 300], "look_at": "Hero"}]},
        {"id": "Close", "keys": [{"frame": 60, "location": [100, 100, 150], "rotation": [-10, 200, 0]}]},
    ],
    "shots": [{"camera": "Wide", "start": 0, "end": 2}, {"camera": "Close", "start": 2, "end": 6}],
    "actors": [{"actor": "Hero", "keys": [{"time": 0, "offset": [0, 0, 0]}, {"time": 6, "offset": [0, 0, 100]}]}],
}


def rules(findings):
    return {f["rule"] for f in findings}


class PlanTests(unittest.TestCase):
    def test_times_become_display_rate_frames(self):
        plan = normalize(PLAN)
        self.assertEqual((plan["sequence"]["start_frame"], plan["sequence"]["end_frame"]), (0, 180))
        self.assertEqual([k["frame"] for k in plan["cameras"][0]["keys"]], [0, 90])
        self.assertEqual([(s["start_frame"], s["end_frame"]) for s in plan["shots"]], [(0, 60), (60, 180)])
        self.assertEqual(plan["cameras"][1]["keys"][0]["frame"], 60)

    def test_valid_plan_has_no_errors(self):
        self.assertEqual([f for f in validate(normalize(PLAN)) if f["severity"] == "error"], [])

    def test_cut_problems_and_bad_keys_are_found(self):
        plan = normalize({**PLAN, "shots": [{"camera": "Wide", "start": 0, "end": 3}, {"camera": "Nope", "start": 2, "end": 5}],
                          "cameras": PLAN["cameras"] + [{"id": "Spare", "aim": "middle", "keys": [{"time": 1, "location": [0, 0, 0],
                                                                                                 "rotation": [0, 0, 0], "look_at": "Hero"}]}]})
        found = rules(validate(plan))
        self.assertTrue({"shot_camera", "cut_overlap", "cut_gap", "unused_camera", "aim", "rotation"} <= found, found)

    def test_sequence_path_and_range_are_required(self):
        found = rules(validate(normalize({"sequence": {"path": "Cine/LS"}, "cameras": [], "shots": []})))
        self.assertTrue({"sequence_path", "sequence_range"} <= found)

    def test_look_at_rotation(self):
        self.assertEqual(look_at_rotation([0, 0, 0], [100, 0, 0]), [0.0, 0.0, 0.0])
        pitch, yaw, _ = look_at_rotation([0, 0, 100], [0, 100, 0])
        self.assertAlmostEqual(yaw, 90.0)
        self.assertAlmostEqual(pitch, -45.0)

    def test_yaw_unwrap_avoids_long_spins(self):
        self.assertEqual(unwrap_yaws([170, -170, 175]), [170, 190, 175])

    def test_ray_box_entry(self):
        self.assertAlmostEqual(ray_box_entry([0, 0, 0], [100, 0, 0], [40, -5, -5], [60, 5, 5]), 40)
        self.assertEqual(ray_box_entry([50, 0, 0], [100, 0, 0], [40, -5, -5], [60, 5, 5]), 0)
        self.assertIsNone(ray_box_entry([0, 0, 0], [100, 0, 0], [40, 10, -5], [60, 20, 5]))

    def test_resolve_keys_fills_rotation_and_auto_focus(self):
        keys = resolve_camera_keys(normalize(PLAN)["cameras"][0], {"Hero": [0, 0, 300]})
        self.assertEqual(keys[0]["rotation"], [0.0, 0.0, 0.0])
        self.assertEqual(keys[0]["focus"], 600.0)
        self.assertEqual(keys[0]["aim_point"], [0, 0, 300])
        with self.assertRaises(KeyError):
            resolve_camera_keys(normalize(PLAN)["cameras"][0], {})


def dump(cuts, cameras=("CAMA", "CAMB"), playback=(0, 100), extra_tracks=()):
    bindings = []
    for cam in cameras:
        child = cam + "C"
        bindings.append({"id": cam, "name": cam, "display": cam, "parent": None, "children": [child], "tracks": [
            {"name": "T", "class": "MovieScene3DTransformTrack", "display": "Transform", "sections": [
                {"name": "S", "class": "MovieScene3DTransformSection", "start": None, "end": None,
                 "channels": [{"name": "Location.X", "keys": [[0, 0.0], [150, 10.0]]}]}]}]})
        bindings.append({"id": child, "name": "CameraComponent", "display": "CameraComponent", "parent": cam, "children": [], "tracks": []})
    sections = [{"name": f"Cut{i}", "class": "MovieSceneCameraCutSection", "start": s, "end": e, "camera": c, "channels": []}
                for i, (s, e, c) in enumerate(cuts or [])]
    tracks = ([{"name": "Cuts", "class": "MovieSceneCameraCutTrack", "display": "", "sections": sections}] if cuts is not None else [])
    return {"sequence": "/Game/T/LS.LS", "display_rate": [30, 1], "tick_resolution": [24000, 1], "playback": list(playback),
            "tracks": tracks + list(extra_tracks), "bindings": bindings}


class LintTests(unittest.TestCase):
    def test_clean_cuts(self):
        found = rules(seq_inspect.lint(dump([(0, 50, "CAMA"), (50, 100, "CAMB")])))
        self.assertEqual(found, {"key_outside_range"})

    def test_cut_problems(self):
        found = rules(seq_inspect.lint(dump([(0, 40, "CAMA"), (30, 80, "0" * 32)])))
        self.assertTrue({"cut_overlap", "cut_without_camera", "cut_gap", "unused_camera"} <= found, found)

    def test_cameras_without_cut_track(self):
        self.assertIn("no_camera_cuts", rules(seq_inspect.lint(dump(None))))

    def test_empty_and_animation_sections(self):
        extra = [{"name": "A", "class": "MovieSceneSkeletalAnimationTrack", "display": "Anim", "sections": [
                     {"name": "AS", "class": "MovieSceneSkeletalAnimationSection", "start": 10, "end": 10, "animation": None, "channels": []}]},
                 {"name": "F", "class": "MovieSceneFadeTrack", "display": "Fade", "sections": []}]
        found = rules(seq_inspect.lint(dump([(0, 100, "CAMA"), ], cameras=("CAMA",), extra_tracks=extra)))
        self.assertTrue({"empty_section", "animation_missing", "empty_track"} <= found, found)

    def test_summary_names_cameras(self):
        summary = seq_inspect.summarize(dump([(0, 50, "CAMA"), (50, 100, "CAMB")]))
        self.assertEqual(summary["cameras"], ["CAMA", "CAMB"])
        self.assertEqual(summary["seconds"], 3.333)


class SampleTests(unittest.TestCase):
    def test_active_camera_and_angles(self):
        cuts = [{"start": 0, "end": 60, "camera": "A"}, {"start": 60, "end": 120, "camera": "B"}]
        self.assertEqual([active_camera(cuts, f) for f in (0, 59, 60, 120)], ["A", "A", "B", None])
        self.assertAlmostEqual(angle_delta(179, -179), 2)

    def test_check_keys(self):
        planned = {"Wide": {"binding": "AB-CD", "keys": [{"frame": 0, "location": [0, 0, 0], "rotation": [-10, 90, 0], "focal": 24}]}}
        good = {0: {"bindings": {"ABCD": {"transform": {"location": {"x": 0.4, "y": 0, "z": 0},
                                                         "rotation": {"pitch": -10.2, "yaw": -270, "roll": 0}},
                                           "camera": {"CurrentFocalLength": 24.05}}}}}
        self.assertTrue(check_keys(good, planned)[0]["ok"])
        bad = {0: {"bindings": {"ABCD": {"transform": {"location": {"x": 5, "y": 0, "z": 0},
                                                        "rotation": {"pitch": -10, "yaw": 90, "roll": 0}}}}}}
        self.assertFalse(check_keys(bad, planned)[0]["ok"])


if __name__ == "__main__":
    unittest.main()
