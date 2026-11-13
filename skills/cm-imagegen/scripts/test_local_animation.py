"""Offline rendered/decoded animation tests; no generation calls or credentials."""

import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cm_animate as animation


class AnimationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        yy, xx = np.mgrid[:96, :128]
        background = np.stack((70 + xx, 90 + yy, 150 + xx // 4), axis=-1).astype(np.uint8)
        Image.fromarray(background).save(self.root / "bg.png")
        subject = Image.new("RGBA", (50, 30))
        draw = ImageDraw.Draw(subject)
        draw.polygon([(5, 10), (45, 10), (38, 25), (12, 25)], fill=(180, 70, 20, 255))
        draw.rectangle((22, 2, 25, 15), fill=(230, 180, 80, 255))
        subject.save(self.root / "subject.png")
        self.config = {"background": "bg.png", "size": [128, 96], "frame_count": 20, "frame_duration_ms": 60,
                       "layers": [{"image": "subject.png", "width": 40, "position": [64, 65],
                                   "rotation": {"amplitude": 5}, "x": {"amplitude": 4}, "y": {"amplitude": 2}}]}

    def scene(self, config=None):
        return animation.Scene(config or self.config, self.root)

    def test_period_and_seam_are_continuous(self):
        scene = self.scene()
        np.testing.assert_array_equal(scene.frame(0), scene.frame(animation.TAU))
        frames = [np.asarray(scene.frame(animation.TAU * i / scene.count), dtype=np.int16) for i in range(scene.count)]
        differences = [np.abs(frames[(i + 1) % scene.count] - f).mean() for i, f in enumerate(frames)]
        self.assertGreater(float(np.median(differences)), 0)
        self.assertLess(differences[-1], np.median(differences) * 3)

    def test_pillow_output_has_motion_correct_timing_and_provenance(self):
        out = self.root / "out.gif"
        result = animation.compose(self.scene(), out, "pillow", preview=self.root / "preview.png")
        self.assertEqual(result["media"]["size"], [128, 96])
        self.assertEqual(result["media"]["duration_ms"], 1200)
        self.assertEqual(result["media"]["frame_delays_ms"], [60])
        self.assertEqual(result["media"]["loop"], 0)
        self.assertGreater(result["media"]["distinct_frames"], 10)
        self.assertFalse(result["native_gif_request"])
        self.assertFalse(result["network_call_performed"])
        provenance = json.loads(Path(result["sidecars"][0]).read_text(encoding="utf-8"))
        self.assertEqual(provenance["output_sha256"], animation.sha256(out))
        self.assertEqual(len(provenance["sources"]), 2)
        self.assertEqual(provenance["sources"][1]["sha256"], animation.sha256(self.root / "subject.png"))
        with Image.open(self.root / "preview.png") as preview:
            self.assertEqual(preview.size, (128, 96))

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is optional")
    def test_ffmpeg_decodes_with_exact_centisecond_timing(self):
        result = animation.compose(self.scene(), self.root / "ffmpeg.gif", "ffmpeg")
        self.assertEqual(result["media"]["duration_ms"], 1200)
        self.assertEqual(result["media"]["frames"], 20)
        self.assertEqual(result["media"]["frame_delays_ms"], [60])
        self.assertGreater(result["media"]["distinct_frames"], 10)

    def test_water_effects_preserve_fixed_upper_background(self):
        config = copy.deepcopy(self.config)
        config["water"] = {"top": 40, "amplitude_px": 3}
        config["layers"][0].update(reflection=True, shadow=True, ripples=True)
        scene = self.scene(config)
        a, b = (np.asarray(scene.frame(phase)) for phase in (0, 1))
        np.testing.assert_array_equal(a[:25], b[:25])
        self.assertGreater(float(np.abs(a[40:].astype(int) - b[40:].astype(int)).mean()), 0)
        np.testing.assert_array_equal(scene.frame(0), scene.frame(animation.TAU))

    def test_layers_move_independently(self):
        config = copy.deepcopy(self.config)
        config["layers"].append({"image": "subject.png", "width": 20, "position": [20, 25], "x": {"amplitude": 6, "cycles": 2}})
        scene = self.scene(config)
        a, b = [np.asarray(scene.frame(p)) for p in (0, animation.TAU / 8)]
        self.assertTrue(np.any(a[0:30, 0:40] != b[0:30, 0:40]))
        self.assertTrue(np.any(a[45:75, 40:90] != b[45:75, 40:90]))

    def test_opaque_and_empty_foregrounds_are_rejected(self):
        for color in ((1, 2, 3, 255), (0, 0, 0, 0)):
            with self.subTest(color=color):
                Image.new("RGBA", (50, 30), color).save(self.root / "subject.png")
                with self.assertRaisesRegex(ValueError, "real transparency"):
                    self.scene()

    def test_invalid_timing_cycles_and_unknown_fields_fail(self):
        variants = []
        for key, value in (("frame_duration_ms", 33), ("frame_count", 1), ("frame_count", True), ("typo", 1)):
            config = copy.deepcopy(self.config)
            config[key] = value
            variants.append(config)
        for key, value in (("cycles", 1.5), ("cycles", 0), ("amplitude", float("nan"))):
            config = copy.deepcopy(self.config)
            config["layers"][0]["x"][key] = value
            variants.append(config)
        for config in variants:
            with self.subTest(config=config), self.assertRaises(ValueError):
                self.scene(config)

    def test_static_animation_does_not_replace_existing_output(self):
        config = copy.deepcopy(self.config)
        config["layers"][0] = {"image": "subject.png", "width": 40, "position": [64, 65]}
        output = self.root / "existing.gif"
        output.write_bytes(b"previous deliverable")
        with self.assertRaisesRegex(ValueError, "no visible animation"):
            animation.compose(self.scene(config), output, "pillow")
        self.assertEqual(output.read_bytes(), b"previous deliverable")

    def test_invalid_preview_is_rejected_before_output_is_written(self):
        output = self.root / "out.gif"
        with self.assertRaisesRegex(ValueError, "Preview"):
            animation.compose(self.scene(), output, "pillow", preview=output)
        self.assertFalse(output.exists())

    def test_cli_resolves_images_relative_to_scene_and_auto_uses_pillow(self):
        scene_file = self.root / "scene.json"
        scene_file.write_text(json.dumps(self.config), encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), mock.patch.object(animation.shutil, "which", return_value=None):
            code = animation.main(["--scene", str(scene_file), "--out", str(self.root / "cli.gif")])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["encoder"], "pillow")


if __name__ == "__main__":
    unittest.main()
