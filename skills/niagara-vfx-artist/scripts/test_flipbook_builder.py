from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vfx_delivery.flipbook_builder import (
    VideoMetadata,
    atlas_size_for_mode,
    build_recommendation,
    clip_range_from_args,
    compose_atlas,
    format_subprocess_error,
    frame_times,
    is_power_of_two,
    local_ffmpeg_state,
    metadata_for_clip,
    nearest_power_of_two,
    normalize_frame,
    parse_grid,
    parse_time,
    resolve_executable,
)


class FlipbookBuilderTests(unittest.TestCase):
    def test_parse_grid_accepts_x_star_and_multiplication_sign(self) -> None:
        self.assertEqual(parse_grid("8x8"), (8, 8))
        self.assertEqual(parse_grid("8*4"), (8, 4))
        self.assertEqual(parse_grid("4×4"), (4, 4))

    def test_parse_time_accepts_seconds_and_timecodes(self) -> None:
        self.assertEqual(parse_time("1.5"), 1.5)
        self.assertEqual(parse_time("00:01.500"), 1.5)
        self.assertEqual(parse_time("01:02"), 62.0)
        self.assertEqual(parse_time("00:01:02.250"), 62.25)

    def test_recommendation_prefers_common_grid(self) -> None:
        metadata = VideoMetadata(
            path="D:/tmp/fire.mp4",
            width=1024,
            height=1024,
            duration_seconds=2.0,
            fps=30.0,
            frame_count=60,
            source="manual",
        )
        recommendation = build_recommendation(
            metadata,
            target_fps=12.0,
            min_frames=16,
            max_frames=64,
            max_texture_size=4096,
            allow_upscale=False,
        )
        self.assertEqual(recommendation["recommended_grid"]["label"], "8x4")
        self.assertEqual(recommendation["recommended_sampling_frames"], 32)
        self.assertEqual(recommendation["estimated_atlas_size"], {"width": 4096, "height": 2048})

    def test_recommendation_caps_long_clip_to_8x8(self) -> None:
        metadata = VideoMetadata(
            path="D:/tmp/smoke.mp4",
            width=512,
            height=512,
            duration_seconds=8.0,
            fps=30.0,
            frame_count=240,
            source="manual",
        )
        recommendation = build_recommendation(
            metadata,
            target_fps=12.0,
            min_frames=16,
            max_frames=64,
            max_texture_size=4096,
            allow_upscale=False,
        )
        self.assertEqual(recommendation["recommended_grid"]["label"], "8x8")
        self.assertEqual(recommendation["desired_frames_clamped"], 64)

    def test_nearest_power_of_two_snaps_each_axis(self) -> None:
        self.assertEqual(nearest_power_of_two(2160), 2048)
        self.assertEqual(nearest_power_of_two(4090), 4096)
        self.assertEqual(atlas_size_for_mode((2160, 4090), "nearest-power-of-two"), (2048, 4096))
        self.assertTrue(is_power_of_two(2048))
        self.assertTrue(is_power_of_two(4096))
        self.assertFalse(is_power_of_two(2160))

    def test_recommendation_reports_power_of_two_atlas_size(self) -> None:
        metadata = VideoMetadata(
            path="D:/tmp/dust.mov",
            width=270,
            height=512,
            duration_seconds=2.0,
            fps=30.0,
            frame_count=60,
            source="manual",
        )
        recommendation = build_recommendation(
            metadata,
            target_fps=12.0,
            min_frames=16,
            max_frames=64,
            max_texture_size=4096,
            allow_upscale=False,
        )
        self.assertEqual(recommendation["recommended_grid"]["label"], "8x4")
        self.assertEqual(recommendation["raw_estimated_atlas_size"], {"width": 2160, "height": 2048})
        self.assertEqual(recommendation["estimated_atlas_size"], {"width": 2048, "height": 2048})
        self.assertTrue(recommendation["estimated_atlas_power_of_two"])

    def test_clip_range_defaults_to_full_video(self) -> None:
        metadata = VideoMetadata("D:/tmp/smoke.mp4", 512, 512, 8.0, 30.0, 240, "manual")
        args = type("Args", (), {"start": 0.0, "end": None})()
        clip = clip_range_from_args(metadata, args)
        self.assertTrue(clip.uses_full_video)
        self.assertEqual(clip.start_seconds, 0.0)
        self.assertEqual(clip.end_seconds, 8.0)
        self.assertEqual(clip.duration_seconds, 8.0)

    def test_clip_range_changes_auto_recommendation_duration(self) -> None:
        metadata = VideoMetadata("D:/tmp/smoke.mp4", 512, 512, 8.0, 30.0, 240, "manual")
        args = type("Args", (), {"start": 2.0, "end": 3.0})()
        clip = clip_range_from_args(metadata, args)
        clipped = metadata_for_clip(metadata, clip)
        recommendation = build_recommendation(
            clipped,
            target_fps=12.0,
            min_frames=16,
            max_frames=64,
            max_texture_size=4096,
            allow_upscale=False,
        )
        self.assertFalse(clip.uses_full_video)
        self.assertEqual(clipped.duration_seconds, 1.0)
        self.assertEqual(recommendation["recommended_grid"]["label"], "4x4")

    def test_frame_times_evenly_uses_midpoints(self) -> None:
        self.assertEqual(frame_times(0.0, 1.0, 4, mode="evenly", fps=12.0), [0.125, 0.375, 0.625, 0.875])

    def test_normalize_and_compose_atlas(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
            normalized: list[Path] = []
            for index, color in enumerate(colors):
                source = root / f"source_{index}.png"
                target = root / f"frame_{index}.png"
                Image.new("RGBA", (12, 8), color).save(source)
                normalize_frame(
                    source,
                    target,
                    cell_size=(8, 8),
                    fit="stretch",
                    background=(0, 0, 0, 0),
                )
                normalized.append(target)

            atlas = root / "atlas.png"
            size = compose_atlas(
                normalized,
                atlas,
                columns=2,
                rows=2,
                cell_size=(8, 8),
                background=(0, 0, 0, 0),
            )
            self.assertEqual(size, (16, 16))
            with Image.open(atlas) as image:
                self.assertEqual(image.getpixel((0, 0)), colors[0])
                self.assertEqual(image.getpixel((8, 0)), colors[1])
                self.assertEqual(image.getpixel((0, 8)), colors[2])
                self.assertEqual(image.getpixel((8, 8)), colors[3])

    def test_compose_atlas_can_snap_final_output_to_power_of_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            frame = root / "frame.png"
            Image.new("RGBA", (216, 409), (255, 255, 255, 255)).save(frame)
            atlas = root / "atlas.png"
            size = compose_atlas(
                [frame],
                atlas,
                columns=10,
                rows=10,
                cell_size=(216, 409),
                background=(0, 0, 0, 0),
                atlas_size=(2048, 4096),
            )
            self.assertEqual(size, (2048, 4096))
            with Image.open(atlas) as image:
                self.assertEqual(image.size, (2048, 4096))

    def test_resolve_ffmpeg_from_directory_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            exe = root / "bin" / ("ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg")
            exe.parent.mkdir(parents=True)
            exe.write_text("", encoding="utf-8")
            self.assertEqual(Path(resolve_executable("ffmpeg", str(root))).resolve(), exe.resolve())

    def test_local_archive_state_explains_missing_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive = root / "ffmpeg-8.1.1.tar.xz"
            archive.write_text("archive", encoding="utf-8")
            message = local_ffmpeg_state("ffmpeg", [root])
            self.assertIn("Found archive(s) but no ffmpeg executable", message)
            self.assertIn(str(archive), message)

    def test_resolve_archive_override_reports_archive_not_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            archive = Path(temp_name) / "ffmpeg-8.1.1.tar.xz"
            archive.write_text("archive", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "archive, not an executable"):
                resolve_executable("ffmpeg", str(archive))

    def test_resolve_local_executable_before_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            exe = root / ("ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg")
            exe.write_text("", encoding="utf-8")
            with patch("vfx_delivery.flipbook_builder.local_ffmpeg_roots", return_value=[root]):
                self.assertEqual(Path(resolve_executable("ffmpeg", None)).resolve(), exe.resolve())

    def test_subprocess_error_includes_stderr(self) -> None:
        import subprocess

        error = subprocess.CalledProcessError(
            1,
            ["ffmpeg", "-i", "bad.mp4"],
            output="",
            stderr="Invalid data found when processing input",
        )
        message = format_subprocess_error("ffmpeg", ["ffmpeg", "-i", "bad.mp4"], error)
        self.assertIn("exit code 1", message)
        self.assertIn("Invalid data found", message)


if __name__ == "__main__":
    unittest.main()
