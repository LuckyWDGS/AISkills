"""The generated-flipbook job chain: route advice -> job scaffold -> batch plan -> runner -> atlas packer."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from vfx_flipbook import flipbook_batch_plan, flipbook_batch_runner, flipbook_job_scaffold, frame_atlas_packer
from vfx_flipbook.flipbook_builder import compose_atlas
from vfx_flipbook.flipbook_route_advisor import build_advice, parse_grid


def run_main(module, *argv: str) -> str:
    with patch("sys.argv", [module.__name__, *argv]), redirect_stdout(StringIO()) as stdout:
        code = module.main()
    if code not in (0, None):
        raise AssertionError(f"{module.__name__} exited {code}: {stdout.getvalue()}")
    return stdout.getvalue().strip()


class RouteAdvisorTests(unittest.TestCase):
    def test_route_follows_source_sample_pressure(self) -> None:
        rich = build_advice("smoke", parse_grid("4x4"), clip_duration=2.0, source_fps=30.0)
        self.assertEqual((rich.route, rich.duplicate_pressure), ("direct-extract", "low"))
        sparse = build_advice("smoke", parse_grid("12x12"), clip_duration=1.0, source_fps=12.0)
        self.assertNotEqual(sparse.route, "direct-extract")
        self.assertLess(sparse.source_to_target_ratio, 1.0)
        with self.assertRaises(Exception):
            parse_grid("12")


class JobPipelineTests(unittest.TestCase):
    def test_default_job_rejects_incompatible_grid_before_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            flipbook_job_scaffold.build_job_spec('smoke 12x12 6s', (12, 12), 6, None, Path(tmp))

    def test_scaffold_plan_and_runner_track_anchor_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec_info = json.loads(run_main(flipbook_job_scaffold, "smoke 4x4 2s", "--out-root", tmp, "--json"))
            self.assertEqual((spec_info["grid"], spec_info["target_cells"]), ("4x4", 16))
            spec_path = next(Path(tmp).rglob("job-spec.json"))
            self.assertTrue((spec_path.parent / "prompts.md").is_file())

            plan_path = Path(run_main(flipbook_batch_plan, str(spec_path)).splitlines()[-1])
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(len(plan["frames"]), 16)
            self.assertEqual(sum(1 for frame in plan["frames"] if frame["is_anchor"]), len(plan["phases"]))
            self.assertIn("tools", Path(plan["runner"]["script_path"]).parts)

            status = json.loads(run_main(flipbook_batch_runner, "status", str(plan_path), "--json"))
            self.assertEqual(status["next_action"], "run anchor for phase 1")

            frame = Path(tmp, "frame_001.png")
            Image.new("RGBA", (64, 64), (200, 200, 200, 255)).save(frame)
            run_main(flipbook_batch_runner, "import-frame", str(plan_path), "--frame", "1", "--path", str(frame),
                     "--approve-anchor", "--json")
            status = json.loads(run_main(flipbook_batch_runner, "status", str(plan_path), "--json"))
            first = status["phases"][0]
            self.assertEqual((first["anchor_status"], first["completed_frame_count"]), ("approved", 1))
            self.assertNotEqual(status["next_action"], "run anchor for phase 1")


class FrameAtlasPackerTests(unittest.TestCase):
    def test_builder_cell_padding_preserves_uv_grid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frames = [Path(tmp, f'{i}.png') for i in range(4)]
            colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
            for path, color in zip(frames, colors):
                Image.new('RGBA', (48, 48), color).save(path)
            atlas = Path(tmp, 'atlas.png')
            compose_atlas(frames, atlas, columns=2, rows=2, cell_size=(48, 48), background=(0, 0, 0, 0),
                          atlas_size=(128, 128), pad_cells=True)
            with Image.open(atlas) as packed:
                self.assertEqual([packed.getpixel(p) for p in [(32, 32), (96, 32), (32, 96), (96, 96)]], colors)

    def test_144_frames_fit_16x16_without_playing_unused_cells(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frames, out = Path(tmp, 'frames'), Path(tmp, 'out')
            frames.mkdir()
            for index in range(144):
                Image.new('RGBA', (8, 8), (index, 0, 0, 255)).save(frames / f'{index:03}.png')
            run_main(frame_atlas_packer, str(frames), '--grid', '16x16', '--cell-size', '8x8', '--out-dir', str(out))
            manifest = json.loads((out / 'flipbook-manifest.json').read_text(encoding='utf-8'))
            self.assertEqual((manifest['input_frame_count'], manifest['grid']['cells']), (144, 256))
            self.assertEqual((manifest['ue_notes']['first_frame'], manifest['ue_notes']['recommended_end_frame']), (0, 143))
            self.assertEqual(manifest['ue_notes']['blank_cells'], 112)
            self.assertTrue(manifest['ue_notes']['sub_uv_direct_ready'])
            with Image.open(out / 'flipbook_atlas.png') as packed:
                self.assertEqual(packed.getpixel((124, 68)), (143, 0, 0, 255))
                self.assertEqual(packed.getpixel((4, 76))[3], 0)

    def test_non_power_of_two_grid_is_rejected_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frames, out = Path(tmp, 'frames'), Path(tmp, 'out')
            frames.mkdir()
            Image.new('RGBA', (8, 8)).save(frames / 'frame.png')
            with self.assertRaises(SystemExit):
                run_main(frame_atlas_packer, str(frames), '--grid', '12x12', '--cell-size', '8x8', '--out-dir', str(out))
            self.assertFalse(out.exists())

    def test_padding_preserves_each_uv_cells_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frames, out = Path(tmp, 'frames'), Path(tmp, 'out')
            frames.mkdir()
            colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
            for index, color in enumerate(colors):
                Image.new('RGBA', (48, 48), color).save(frames / f'{index}.png')
            run_main(frame_atlas_packer, str(frames), '--grid', '2x2', '--cell-size', '48x48',
                     '--atlas-size-mode', 'pad-to-power-of-two', '--out-dir', str(out))
            with Image.open(out / 'flipbook_atlas.png') as atlas:
                self.assertEqual([atlas.getpixel(p) for p in [(32, 32), (96, 32), (32, 96), (96, 96)]], colors)
            manifest = json.loads((out / 'flipbook-manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['grid']['cell_width'], 64)

    def test_excess_frames_are_not_silently_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(5):
                Image.new('RGBA', (8, 8)).save(Path(tmp, f'{i}.png'))
            with self.assertRaises(SystemExit):
                run_main(frame_atlas_packer, tmp, '--grid', '2x2', '--cell-size', '8x8', '--out-dir', str(Path(tmp, 'out')))

    def test_packs_frames_into_a_power_of_two_atlas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            frames = Path(tmp, "frames")
            frames.mkdir()
            for index in range(3):
                Image.new("RGBA", (40, 20), (255, 60 * index, 0, 255)).save(frames / f"frame_{index:03d}.png")
            out = Path(tmp, "out")
            run_main(frame_atlas_packer, str(frames), "--grid", "2x2", "--cell-size", "48x48",
                     "--atlas-size-mode", "pad-to-power-of-two", "--out-dir", str(out), "--atlas-name", "atlas.png")
            with Image.open(out / "atlas.png") as atlas:
                self.assertEqual(atlas.size, (128, 128))
                self.assertEqual(atlas.getpixel((24, 24))[:3], (255, 0, 0))  # first frame, contain-fit into its cell
                self.assertEqual(atlas.getpixel((70, 70))[3], 0)  # the fourth cell has no frame
            manifest = json.loads(next(out.glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual((manifest["input_frame_count"], manifest["grid"]["cells"]), (3, 4))


if __name__ == "__main__":
    unittest.main()
