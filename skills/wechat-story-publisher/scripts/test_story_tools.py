"""Offline tests for story_manifest.py, compose_bubbles.py and qa_preview.py."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw  # noqa: E402

import compose_bubbles as cb  # noqa: E402
import qa_preview as qa  # noqa: E402
import story_manifest as sm  # noqa: E402

CJK_FONT = cb.find_font(None)


def unit_measure(text: str) -> float:
    return float(len(text))


def run(main, *argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class WrapTests(unittest.TestCase):
    def test_closing_punctuation_never_starts_a_line(self):
        lines = cb.wrap_text("一二三四，五六七八。九十", 4, unit_measure)
        self.assertTrue(all(line[0] not in cb.NO_LINE_START for line in lines), lines)
        self.assertEqual("".join(lines), "一二三四，五六七八。九十")

    def test_opening_punctuation_never_ends_a_line(self):
        lines = cb.wrap_text("一二三《四五六》七八", 4, unit_measure)
        self.assertTrue(all(line[-1] not in cb.NO_LINE_END for line in lines), lines)

    def test_single_character_last_line_is_merged(self):
        lines = cb.wrap_text("一二三四五六七八九", 4, unit_measure)
        self.assertGreaterEqual(len([c for c in lines[-1] if c not in cb.NO_LINE_START]), 2, lines)
        lines = cb.wrap_text("收据还在我手机里。", 6, unit_measure)
        self.assertNotEqual(lines[-1], "里。", lines)

    def test_latin_words_are_not_split(self):
        lines = cb.wrap_text("hello world again", 11, unit_measure)
        self.assertEqual(lines, ["hello world", "again"])


class StoryFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "base").mkdir()
        for i in range(1, 4):
            Image.new("RGB", (390, 600), (0, 0, 0)).save(self.root / "base" / f"p0{i}.png")
        code, _, err = run(sm.main, "init", "--base-dir", str(self.root / "base"),
                           "--pages-dir", str(self.root / "pages"), "--out", str(self.root / "story_manifest.json"))
        self.assertEqual(code, 0, err)
        self.manifest_path = self.root / "story_manifest.json"
        self.data = json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def save(self):
        self.manifest_path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")

    def bubble(self, **extra):
        value = {"speaker": "A", "text": "HELLO THERE", "box": [0.1, 0.1, 0.8, 0.25], "tail": [0.5, 0.7],
                 "fill": "#FFFFFF", "fill_alpha": 160, "text_color": "#FF0000"}
        value.update(extra)
        return value


class ManifestTests(StoryFixture):
    def test_init_lists_pages_in_order_with_relative_paths(self):
        self.assertEqual([p["id"] for p in self.data["pages"]], ["p01", "p02", "p03"])
        self.assertEqual(self.data["pages"][0]["base"], "base/p01.png")
        self.assertEqual(self.data["pages"][0]["image"], "pages/p01.png")

    def test_validation_errors(self):
        cases = (
            ({"speaker": "A", "text": "x", "box": [0.1, 0.1, 0.2, 0.1]}, "tail"),
            ({"speaker": "A", "text": "x", "box": [0.9, 0.1, 0.2, 0.1], "tail": [0.5, 0.5]}, "inside the page"),
            ({"text": "x", "box": [0.1, 0.1, 0.2, 0.1], "tail": [0.5, 0.5]}, "speaker"),
        )
        for bubble, message in cases:
            with self.subTest(message=message):
                self.data["pages"][0]["bubbles"] = [bubble]
                with self.assertRaisesRegex(sm.ManifestError, message):
                    sm.parse_manifest(self.data, self.manifest_path)
        self.data["pages"][0]["bubbles"] = []
        self.data["pages"][1]["id"] = "p01"
        with self.assertRaisesRegex(sm.ManifestError, "duplicate"):
            sm.parse_manifest(self.data, self.manifest_path)


class ComposeTests(StoryFixture):
    def compose(self, *extra):
        return run(cb.main, "--manifest", str(self.manifest_path), *extra)

    def test_fill_tail_and_text_alpha(self):
        self.data["pages"][0]["bubbles"] = [self.bubble()]
        self.save()
        code, out, err = self.compose()
        self.assertEqual(code, 0, out + err)
        with Image.open(self.root / "pages" / "p01.png") as opened:
            im = opened.convert("RGB")
        # Body interior near the edge (away from text) and tail interior: same 160/255 white over black.
        body = im.getpixel((60, 75))
        tail = im.getpixel((195, 330))
        self.assertTrue(all(abs(c - 160) <= 1 for c in body), body)
        self.assertEqual(body, tail)
        # Text is drawn opaque: some glyph pixels are exactly the text color.
        colors = {color for _count, color in im.crop((40, 60, 350, 210)).getcolors(maxcolors=1 << 24)}
        self.assertIn((255, 0, 0), colors)
        report = json.loads((self.root / "qa" / "compose-report.json").read_text(encoding="utf-8"))
        entry = report["pages"][0]["bubbles"][0]
        self.assertGreaterEqual(entry["font_px_at_reading_width"], 13)
        self.assertLessEqual(entry["font_px_at_reading_width"], 18)
        self.assertEqual(entry["fill_opacity_percent"], 63)

    def test_pages_without_bubbles_are_copied_and_versions_are_kept(self):
        self.data["pages"][0]["bubbles"] = [self.bubble()]
        self.save()
        self.assertEqual(self.compose()[0], 0)
        self.assertTrue((self.root / "pages" / "p02.png").is_file())
        code, out, _ = self.compose()
        self.assertEqual(sorted(json.loads(out)["unchanged"]), ["p01", "p02", "p03"])
        self.data["pages"][0]["bubbles"][0]["text"] = "BYE NOW"
        self.save()
        code, out, _ = self.compose("--pages", "p01")
        self.assertEqual(json.loads(out)["written"], ["p01"])
        self.assertEqual(len(list((self.root / "pages" / "_versions").glob("p01-*.png"))), 1)
        report = json.loads((self.root / "qa" / "compose-report.json").read_text(encoding="utf-8"))
        self.assertEqual([p["page"] for p in report["pages"]], ["p01", "p02", "p03"])

    def test_overflow_fails_without_writing(self):
        self.data["pages"][0]["bubbles"] = [self.bubble(text="A VERY LONG LINE " * 12, box=[0.1, 0.1, 0.2, 0.04])]
        self.save()
        code, out, _ = self.compose()
        self.assertEqual(code, 1)
        self.assertIn("text_overflow", json.dumps(json.loads(out)["errors"]))
        self.assertFalse((self.root / "pages" / "p01.png").exists())

    def test_watermark_and_avoid_region_warnings(self):
        self.data["watermark_zones"] = [[0.0, 0.9, 1.0, 0.1]]
        self.data["pages"][0]["bubbles"] = [self.bubble(box=[0.1, 0.8, 0.8, 0.15], tail=[0.5, 0.5])]
        self.data["pages"][0]["review_regions"] = [{"label": "face", "box": [0.3, 0.75, 0.4, 0.1], "avoid": True}]
        self.save()
        code, out, _ = self.compose("--dry-run")
        warnings = json.dumps(json.loads(out)["warnings"])
        self.assertIn("overlaps_watermark_zone", warnings)
        self.assertIn("covers_avoid_region:face", warnings)
        self.assertFalse((self.root / "pages" / "p01.png").exists())

    @unittest.skipUnless(CJK_FONT, "no CJK font on this machine")
    def test_chinese_text_renders_with_cjk_font(self):
        self.data["pages"][0]["bubbles"] = [self.bubble(text="退租那天，我把窗帘拆下来装进了袋子里。")]
        self.save()
        code, out, err = self.compose()
        self.assertEqual(code, 0, out + err)
        report = json.loads((self.root / "qa" / "compose-report.json").read_text(encoding="utf-8"))
        lines = report["pages"][0]["bubbles"][0]["lines"]
        self.assertTrue(all(line[0] not in cb.NO_LINE_START for line in lines), lines)


class QaPreviewTests(StoryFixture):
    def test_outputs_checks_and_version_diff(self):
        self.data["pages"][0]["bubbles"] = [self.bubble()]
        self.data["pages"][2]["bubbles"] = [self.bubble(kind="caption", shape="rect", text="THE END", tail=None)]
        self.data["pages"][1]["review_regions"] = [{"label": "hands", "box": [0.2, 0.2, 0.3, 0.3]}]
        self.save()
        self.assertEqual(run(cb.main, "--manifest", str(self.manifest_path))[0], 0)
        code, out, err = run(qa.main, "--manifest", str(self.manifest_path))
        self.assertEqual(code, 0, out + err)
        brief = json.loads(out)
        qa_dir = self.root / "qa"
        self.assertTrue((qa_dir / "contact-sheet.png").is_file())
        with Image.open(qa_dir / "narrow" / "p01.png") as narrow:
            self.assertEqual(narrow.width, 390)
        self.assertIn('src="../pages/p01.png"', (qa_dir / "reader.html").read_text(encoding="utf-8"))
        self.assertEqual(brief["crop_count"], 3)
        self.assertIsNone(brief["recheck"])
        self.assertIn("本篇完", json.dumps(brief["warnings"], ensure_ascii=False))

        # Edit p02 outside the composer: its neighbours need re-review, and p01's compose record stays valid.
        with Image.open(self.root / "pages" / "p02.png") as opened:
            im = opened.copy()
        ImageDraw.Draw(im).rectangle((0, 0, 20, 20), fill=(255, 255, 0))
        im.save(self.root / "pages" / "p02.png")
        code, out, _ = run(qa.main, "--manifest", str(self.manifest_path))
        diff = json.loads((qa_dir / "qa-report.json").read_text(encoding="utf-8"))["hashes"]["diff"]
        self.assertEqual(diff["changed"], ["p02"])
        self.assertEqual(diff["recheck"], ["p01", "p02", "p03"])
        self.assertTrue((qa_dir / "hashes.prev.json").is_file())

        # A page edited after composing makes its compose record stale.
        with Image.open(self.root / "pages" / "p01.png") as opened:
            im = opened.copy()
        ImageDraw.Draw(im).point((1, 1), fill=(1, 2, 3))
        im.save(self.root / "pages" / "p01.png")
        _, out, _ = run(qa.main, "--manifest", str(self.manifest_path), "--only", "check")
        self.assertIn("p01: compose report missing or stale", json.dumps(json.loads(out)["warnings"]))

    def test_page_limit_and_missing_files_are_errors(self):
        self.data["settings"]["max_pages"] = 2
        self.save()
        code, out, _ = run(qa.main, "--manifest", str(self.manifest_path), "--only", "check")
        errors = json.dumps(json.loads(out)["errors"])
        self.assertEqual(code, 1)
        self.assertIn("exceeds max_pages", errors)
        self.assertIn("missing", errors)


if __name__ == "__main__":
    unittest.main()
