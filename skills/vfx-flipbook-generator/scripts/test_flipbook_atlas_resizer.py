from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flipbook_atlas_resizer import parse_grid, parse_target_size, resize_atlas_pair


class FlipbookAtlasResizerTests(unittest.TestCase):
    def test_parse_grid_and_power_of_two_target(self) -> None:
        self.assertEqual(parse_grid("4x4"), (4, 4))
        self.assertEqual(parse_target_size("2048"), (2048, 2048))
        self.assertEqual(parse_target_size("4096x2048"), (4096, 2048))
        with self.assertRaises(Exception):
            parse_target_size("3000")

    def test_resize_pair_writes_scaled_images_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            atlas = root / "fx_sheet_demo_4x4_v01_1024.png"
            alpha = root / "fx_sheet_demo_alpha_4x4_v01_1024.png"
            Image.new("RGB", (1024, 1024), (0, 16, 24)).save(atlas)
            Image.new("RGBA", (1024, 1024), (255, 255, 255, 128)).save(alpha)
            manifest = {
                "effect_name": "demo_softreadable",
                "usage": "randomizable Niagara SubUV sheet, not a continuous flipbook",
                "outputs": {
                    "rgb_preview_atlas": str(atlas),
                    "rgba_alpha_atlas": str(alpha),
                },
                "grid": {"columns": 4, "rows": 4, "cells": 16, "cell_width": 256, "cell_height": 256},
                "ue_notes": {"playback_mode": "random SubImageIndex"},
            }
            manifest_path = root / "fx_sheet_demo_4x4_v01_1024_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            [result] = resize_atlas_pair(
                atlas,
                alpha=alpha,
                source_manifest=manifest_path,
                grid=(4, 4),
                targets=[(2048, 2048)],
                out_dir=root,
            )

            primary_out = Path(result.primary_path)
            alpha_out = Path(result.alpha_path or "")
            self.assertTrue(primary_out.exists())
            self.assertTrue(alpha_out.exists())
            with Image.open(primary_out) as image:
                self.assertEqual(image.size, (2048, 2048))
            with Image.open(alpha_out) as image:
                self.assertEqual(image.size, (2048, 2048))

            resized_manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(resized_manifest["effect_name"], "demo_softreadable_2k")
            self.assertEqual(resized_manifest["grid"]["cell_width"], 512)
            self.assertEqual(resized_manifest["atlas"]["grid_divides_atlas"], True)
            self.assertEqual(resized_manifest["outputs"]["rgba_alpha_atlas"], str(alpha_out.resolve()))


if __name__ == "__main__":
    unittest.main()
