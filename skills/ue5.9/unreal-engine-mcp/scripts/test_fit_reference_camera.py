"""Regression checks for the depth/FOV ambiguity and independent photo landmarks."""

import math
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path

HAS_NUMPY = find_spec("numpy") is not None
HAS_SCIPY = find_spec("scipy") is not None
HAS_PILLOW = find_spec("PIL") is not None
if HAS_NUMPY:
    from fit_reference_camera import analyze, save_overlay


def photographed_point(name, x, y, z, weight=1):
    # Independently known camera: origin, zero rotation, 800 x 600, horizontal FOV 90.
    return {"name": name, "ueCm": [x, y, z], "weight": weight,
            "photoPx": [399.5 + 400*y/x, 299.5 - 400*z/x]}


@unittest.skipUnless(HAS_NUMPY and HAS_SCIPY, "Optional reference-camera fitting needs NumPy and SciPy")
class ReferenceCameraFitTests(unittest.TestCase):
    def setUp(self):
        self.points = [photographed_point(str(i), 400, y, z)
                       for i, (y, z) in enumerate([(-80, 100), (70, 90), (-90, -40), (100, -60)])]
        self.camera = {"location": {"x": 12, "y": 3, "z": -4},
                       "rotation": {"yaw": 1, "pitch": 1, "roll": 0}, "fOV": 93}
        self.data = {"imageSize": [800, 600], "camera": self.camera, "points": self.points}

    def test_frontal_wall_cannot_determine_forward_distance_and_fov(self):
        self.points.append(photographed_point("held out", 200, 50, 30, weight=0))
        # A different distance and focal length reproduce every point on the wall exactly.
        self.camera.update(location={"x": 100, "y": 0, "z": 0}, rotation={"yaw": 0, "pitch": 0},
                           fOV=math.degrees(2 * math.atan(400 / 300)))
        self.assertLess(analyze(self.data, evaluate_only=True)["weightedRmsPx"], 1e-8)
        with self.assertRaises(ValueError):
            analyze(self.data, evaluate_only=False)

    def test_nearby_anchor_resolves_depth_and_preserves_holdout_error(self):
        self.points.append(photographed_point("near", 200, 50, 30))
        held_out = photographed_point("held out", 250, -35, 40, weight=0)
        held_out["photoPx"][0] += 8
        held_out["photoPx"][1] -= 6
        self.points.append(held_out)
        result = analyze(self.data, evaluate_only=False)
        self.assertLess(result["weightedRmsPx"], 1e-6)
        self.assertAlmostEqual(result["heldOutRmsPx"], 10, places=5)
        self.assertAlmostEqual(result["camera"]["fOV"], 90, places=5)
        for coordinate in result["camera"]["location"].values():
            self.assertAlmostEqual(coordinate, 0, places=5)


def level_camera(x=0, y=0):
    return {"location": {"x": x, "y": y, "z": 0}, "rotation": {"yaw": 0, "pitch": 0}, "fOV": 90}


@unittest.skipUnless(HAS_NUMPY, "Camera evaluation needs NumPy")
class SavedCameraComparisonTests(unittest.TestCase):
    def setUp(self):
        self.points = [photographed_point("distance", 400, 0, 0, weight=3)]
        self.data = {"imageSize": [800, 600], "camera": level_camera(y=30), "points": self.points}

    def test_saved_baseline_separate_from_seed_and_holdout_can_regress(self):
        near = photographed_point("near", 200, 20, 0, weight=0)
        near["photoPx"][0] -= 20
        self.points.append(near)
        result = analyze(self.data, False, baseline_camera=level_camera(y=10), candidate_camera=level_camera())
        self.assertAlmostEqual(result["initialWeightedRmsPx"], 30)
        self.assertAlmostEqual(result["baselineWeightedRmsPx"], 10)
        self.assertAlmostEqual(result["weightedRmsChangePx"], -10)
        self.assertAlmostEqual(result["baselineHeldOutRmsPx"], 0)
        self.assertAlmostEqual(result["heldOutRmsChangePx"], 20)
        self.assertEqual((result["fitPointCount"], result["heldOutPointCount"]), (1, 1))
        point = result["points"][1]
        self.assertEqual(point["role"], "held-out")
        self.assertEqual(point["weight"], 0)
        self.assertEqual(point["photoPx"], [419.5, 299.5])
        self.assertEqual(point["baselineProjectedPx"], point["photoPx"])
        self.assertEqual(point["projectedPx"], [439.5, 299.5])
        self.assertEqual(point["offsetPx"], [20, 0])

    def test_no_holdout_is_not_reported_as_zero(self):
        result = analyze(self.data, True)
        self.assertEqual(result["weightedRmsChangePx"], 0)
        self.assertIsNone(result["baselineHeldOutRmsPx"])
        self.assertIsNone(result["heldOutRmsPx"])
        self.assertIsNone(result["heldOutRmsChangePx"])
        self.assertEqual(result["heldOutPointCount"], 0)

    def test_two_saved_cameras_can_be_compared_with_an_unusable_search_seed(self):
        self.data["camera"] = level_camera(x=500)
        result = analyze(self.data, False, baseline_camera=level_camera(y=10), candidate_camera=level_camera())
        self.assertIsNone(result["initialWeightedRmsPx"])
        self.assertAlmostEqual(result["weightedRmsChangePx"], -10)

    def test_holdout_behind_baseline_is_unscorable_there(self):
        self.points.append({"name": "behind seed", "ueCm": [-50, 10, 10], "photoPx": [400, 300], "weight": 0})
        result = analyze(self.data, False, candidate_camera=level_camera(x=-100))
        self.assertIsNone(result["points"][1]["baselineProjectedPx"])
        self.assertIsNone(result["baselineHeldOutRmsPx"])
        self.assertIsNotNone(result["heldOutRmsPx"])
        self.assertIsNone(result["heldOutRmsChangePx"])

    @unittest.skipUnless(HAS_PILLOW, "The optional photo overlay needs Pillow")
    def test_photo_overlay_preserves_pixel_grid_and_source(self):
        from PIL import Image
        result = analyze(self.data, True, candidate_camera=level_camera())
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            photo, overlay = p / "photo.png", p / "overlay.png"
            Image.new("RGB", (800, 600), (81, 76, 75)).save(photo)
            original = photo.read_bytes()
            save_overlay(result, photo, overlay)
            self.assertEqual(photo.read_bytes(), original)
            with Image.open(overlay) as view:
                self.assertGreater(view.width, 800)
                self.assertEqual(view.getpixel((0, 0)), (81, 76, 75))
                self.assertEqual(view.getpixel((400, 300)), (255, 237, 98))
                self.assertEqual(view.getpixel((370 - 6, 300)), (255, 129, 52))
                self.assertEqual(view.getpixel((400 + 4, 300)), (0, 225, 239))
            with self.assertRaisesRegex(ValueError, "overwrite"):
                save_overlay(result, photo, photo)
            self.assertEqual(photo.read_bytes(), original)

    @unittest.skipUnless(HAS_PILLOW, "The optional photo overlay needs Pillow")
    def test_resized_or_reframed_photo_cannot_silently_change_markers(self):
        from PIL import Image
        result = analyze(self.data, True)
        with tempfile.TemporaryDirectory() as tmp:
            photo, overlay = Path(tmp) / "photo.png", Path(tmp) / "overlay.png"
            for size in ((400, 300), (800, 450)):
                with self.subTest(size=size):
                    Image.new("RGB", size).save(photo)
                    with self.assertRaisesRegex(ValueError, "Photo size"):
                        save_overlay(result, photo, overlay)
                    self.assertFalse(overlay.exists())


if __name__ == "__main__":
    unittest.main()
