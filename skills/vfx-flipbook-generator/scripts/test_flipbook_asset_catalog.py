from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flipbook_asset_catalog import build_catalog, catalog_to_markdown, parse_readiness


class FlipbookAssetCatalogTests(unittest.TestCase):
    def write_readiness(self, path: Path, atlas: Path, status: str = "ready", *, finding: bool = False) -> None:
        lines = [
            f"# UE Flipbook Readiness: {status}",
            "",
            f"- Atlas: `{atlas}`",
            "- Mode: `random-sheet`",
            "- Size: `1024x1024`",
            "- Grid: `4x4` (16 cells)",
            "- Frames: `16`",
            "- Cell: `256x256`",
            "- Power of two: `True`",
            "- Grid divides atlas: `True`",
            "- Alpha varies: `False`",
            "- Likely black luma sheet: `True`",
            "",
            "## Findings",
        ]
        if finding:
            lines.append("- `warn` `blank_used_cells`: `1` used cells appear nearly blank.")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_parse_readiness_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            atlas = root / "atlas.png"
            Image.new("RGB", (1024, 1024), (0, 0, 0)).save(atlas)
            report = root / "atlas_readiness.md"
            self.write_readiness(report, atlas, status="conditional", finding=True)

            info = parse_readiness(report)

            self.assertEqual(info.status, "conditional")
            self.assertEqual(info.mode, "random-sheet")
            self.assertEqual(info.size, "1024x1024")
            self.assertEqual(info.frames, 16)
            self.assertFalse(info.alpha_varies)
            self.assertTrue(info.likely_black_luma_sheet)
            self.assertEqual(info.findings[0]["code"], "blank_used_cells")

    def test_catalog_pairs_manifest_outputs_and_marks_recommended(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            atlas = root / "fx_sheet_softreadable_4x4_v01_1024.png"
            alpha = root / "fx_sheet_softreadable_alpha_4x4_v01_1024.png"
            Image.new("RGB", (1024, 1024), (0, 0, 0)).save(atlas)
            Image.new("RGBA", (1024, 1024), (255, 255, 255, 128)).save(alpha)
            manifest = {
                "effect_name": "softreadable_test",
                "usage": "randomizable Niagara SubUV sheet, not a continuous flipbook",
                "outputs": {
                    "rgb_preview_atlas": str(atlas),
                    "rgba_alpha_atlas": str(alpha),
                },
                "grid": {"columns": 4, "rows": 4, "cells": 16, "cell_width": 256, "cell_height": 256},
                "atlas": {"path": str(atlas), "width": 1024, "height": 1024},
            }
            (root / "fx_sheet_softreadable_4x4_v01_1024_manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            self.write_readiness(root / "fx_sheet_softreadable_4x4_v01_1024_readiness.md", atlas)
            self.write_readiness(root / "fx_sheet_softreadable_alpha_4x4_v01_1024_readiness.md", alpha)

            catalog = build_catalog(root)
            markdown = catalog_to_markdown(catalog)

            self.assertEqual(len(catalog.entries), 1)
            entry = catalog.entries[0]
            self.assertEqual(entry.name, "softreadable_test")
            self.assertEqual(entry.grid, "4x4")
            self.assertEqual(entry.alpha_path, str(alpha.resolve()))
            self.assertEqual(entry.recommendation, "recommended")
            self.assertIn("randomize `SubImageIndex`", markdown)
            self.assertIn("softreadable_test", markdown)

    def test_catalog_sorts_recommended_high_resolution_first(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            for size in (1024, 4096):
                atlas = root / f"fx_sheet_softreadable_4x4_v01_{size}.png"
                Image.new("RGB", (size, size), (0, 0, 0)).save(atlas)
                manifest = {
                    "effect_name": f"softreadable_test_{size}",
                    "usage": "randomizable Niagara SubUV sheet, not a continuous flipbook",
                    "outputs": {"rgb_preview_atlas": str(atlas)},
                    "grid": {"columns": 4, "rows": 4, "cells": 16, "cell_width": size // 4, "cell_height": size // 4},
                    "atlas": {"path": str(atlas), "width": size, "height": size},
                }
                (root / f"fx_sheet_softreadable_4x4_v01_{size}_manifest.json").write_text(
                    json.dumps(manifest),
                    encoding="utf-8",
                )
                report = root / f"fx_sheet_softreadable_4x4_v01_{size}_readiness.md"
                lines = [
                    "# UE Flipbook Readiness: ready",
                    "",
                    f"- Atlas: `{atlas}`",
                    "- Mode: `random-sheet`",
                    f"- Size: `{size}x{size}`",
                    "- Grid: `4x4` (16 cells)",
                    "- Frames: `16`",
                    f"- Cell: `{size // 4}x{size // 4}`",
                    "- Power of two: `True`",
                    "- Grid divides atlas: `True`",
                    "- Alpha varies: `False`",
                    "- Likely black luma sheet: `True`",
                ]
                report.write_text("\n".join(lines) + "\n", encoding="utf-8")

            catalog = build_catalog(root)

            self.assertEqual(catalog.entries[0].size, "4096x4096")

    def test_niagara_hint_uses_valid_frame_count_for_padded_repack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            atlas = root / "fx_gold_8x8_2048.png"
            Image.new("RGB", (2048, 2048), (0, 0, 0)).save(atlas)
            manifest = {
                "effect_name": "gold_repack",
                "usage": "continuous flipbook repacked into a power-of-two sheet",
                "outputs": {"rgb_preview_atlas": str(atlas)},
                "grid": {"columns": 8, "rows": 8, "cells": 64, "input_frame_count": 36, "cell_width": 256, "cell_height": 256},
                "atlas": {"path": str(atlas), "width": 2048, "height": 2048},
            }
            (root / "fx_gold_8x8_2048_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            report = root / "fx_gold_8x8_2048_readiness.md"
            report.write_text(
                "\n".join(
                    [
                        "# UE Flipbook Readiness: conditional",
                        "",
                        f"- Atlas: `{atlas}`",
                        "- Mode: `both`",
                        "- Size: `2048x2048`",
                        "- Grid: `8x8` (64 cells)",
                        "- Frames: `36`",
                        "- Cell: `256x256`",
                        "- Power of two: `True`",
                        "- Grid divides atlas: `True`",
                        "- Alpha varies: `False`",
                        "- Likely black luma sheet: `True`",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            catalog = build_catalog(root)
            markdown = catalog_to_markdown(catalog)

            self.assertIn("End 35", catalog.entries[0].niagara_hint)
            self.assertIn("leave cells 36..63 unused", markdown)


if __name__ == "__main__":
    unittest.main()
