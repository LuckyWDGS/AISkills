from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unreal_material_tools import preview_readability_score
from unreal_material_tools.core import save_json


def write_png(path: Path, *, bright: bool) -> None:
    from PIL import Image  # type: ignore

    size = (64, 64)
    image = Image.new("RGBA", size, (0, 0, 0, 255))
    pixels = image.load()
    if bright:
        for y in range(18, 46):
            for x in range(18, 46):
                pixels[x, y] = (180, 220, 255, 255)
    image.save(path)


def write_json(root: Path, name: str, payload: dict[str, object]) -> Path:
    path = root / name
    save_json(path, payload)
    return path


def preview_payload(image_path: Path) -> dict[str, object]:
    return {
        "tool": "material_preview",
        "mode": "render",
        "material_path": "/Game/Materials/M_Test",
        "outputs": {"shaded_png": str(image_path), "shaded_ok": True},
    }


def run_tool(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = preview_readability_score.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


class PreviewReadabilityScoreTests(unittest.TestCase):
    def test_bright_center_preview_is_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "readable.png"
            write_png(image, bright=True)
            preview = write_json(root, "preview.json", preview_payload(image))
            code, stdout, stderr = run_tool(["--root", str(root), "--preview-report", str(preview), "--require-readable"])
            self.assertEqual(code, 0, stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            self.assertTrue(report["gate"]["readable"])

    def test_empty_preview_blocks_require_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "empty.png"
            write_png(image, bright=False)
            preview = write_json(root, "preview.json", preview_payload(image))
            code, stdout, stderr = run_tool(["--root", str(root), "--preview-report", str(preview), "--require-readable"])
            self.assertEqual(code, 2)
            self.assertIn("not ready", stderr)
            report = json.loads(Path(stdout.strip()).read_text(encoding="utf-8"))
            rules = {item["rule"] for item in report["findings"]}
            self.assertIn("almost_empty_frame", rules)


if __name__ == "__main__":
    unittest.main(verbosity=2)
