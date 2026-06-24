from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ue_flipbook_readiness import build_report


class UEFlipbookReadinessTests(unittest.TestCase):
    def test_ready_rgba_power_of_two_grid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            atlas = Path(temp_name) / "T_Test_8x8_VFX.png"
            image = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
            for y in range(64):
                for x in range(64):
                    image.putpixel((x + 16, y + 16), (255, 255, 255, 255))
            image.save(atlas)

            report = build_report(
                atlas,
                columns=8,
                rows=8,
                frame_count=1,
                mode="both",
                alpha_policy="true-alpha",
                max_texture_size=4096,
            )

            self.assertEqual(report.status, "conditional")
            self.assertTrue(report.power_of_two)
            self.assertTrue(report.grid_divides_atlas)
            self.assertTrue(report.alpha_varies)
            self.assertFalse(any(f.severity == "fail" for f in report.findings))

    def test_blocks_ten_by_ten_on_1024_for_direct_subuv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            atlas = Path(temp_name) / "T_Dust_10x10_VFX.png"
            Image.new("RGB", (1024, 1024), (0, 0, 0)).save(atlas)

            report = build_report(
                atlas,
                columns=10,
                rows=10,
                frame_count=100,
                mode="both",
                alpha_policy="luma",
                max_texture_size=4096,
            )

            self.assertEqual(report.status, "blocked")
            self.assertFalse(report.grid_divides_atlas)
            self.assertTrue(any(f.code == "grid_not_divisible" for f in report.findings))

    def test_black_luma_sheet_is_conditional_without_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            atlas = Path(temp_name) / "T_Smoke_4x4_VFX.png"
            image = Image.new("RGB", (256, 256), (0, 0, 0))
            for y in range(16, 48):
                for x in range(16, 48):
                    image.putpixel((x, y), (220, 220, 220))
            image.save(atlas)

            report = build_report(
                atlas,
                columns=4,
                rows=4,
                frame_count=1,
                mode="both",
                alpha_policy="auto",
                max_texture_size=4096,
            )

            self.assertEqual(report.status, "conditional")
            self.assertTrue(report.likely_black_luma_sheet)
            self.assertTrue(any(f.code == "luma_opacity_required" for f in report.findings))


if __name__ == "__main__":
    unittest.main()
