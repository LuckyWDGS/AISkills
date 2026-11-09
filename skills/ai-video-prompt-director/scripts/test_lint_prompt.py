#!/usr/bin/env python3
"""Regression tests: every annotated block in examples/ must lint as declared.

Annotation (an HTML comment right before a fenced block):
    <!-- lint platform=seedance type=character duration=15 expect=pass -->
    <!-- lint platform=seedance type=character duration=15 expect=fail:copy_zone,timecode -->
`expect=fail:` lists error codes that must appear (others may appear too).

Run from the skill directory:  python -X utf8 scripts/test_lint_prompt.py
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lint_prompt  # noqa: E402

EXAMPLES = HERE.parent / "examples"
ANNOTATED = re.compile(r"<!--\s*lint\s+(.*?)-->\s*\n```[^\n]*\n(.*?)```", re.S)


def annotated_blocks():
    for path in sorted(EXAMPLES.glob("*.md")):
        for m in ANNOTATED.finditer(path.read_text(encoding="utf-8")):
            opts = dict(kv.split("=", 1) for kv in m.group(1).split())
            yield path.name, opts, m.group(2)


class ExampleBlocks(unittest.TestCase):
    def test_examples_exist(self):
        self.assertGreaterEqual(len(list(annotated_blocks())), 6)

    def test_annotated_blocks(self):
        for name, opts, text in annotated_blocks():
            with self.subTest(file=name, expect=opts["expect"]):
                findings = lint_prompt.lint(
                    text,
                    opts.get("platform", "neutral"),
                    opts.get("type", "character"),
                    float(opts["duration"]) if "duration" in opts else None,
                    int(opts.get("max_chars", 7000)),
                )
                errors = {f.code for f in findings if f.severity == "error"}
                if opts["expect"] == "pass":
                    self.assertEqual(errors, set(), [f for f in findings if f.severity == "error"])
                else:
                    wanted = set(opts["expect"].split(":", 1)[1].split(","))
                    self.assertTrue(wanted <= errors, f"缺少预期错误 {wanted - errors}；实际 {errors}")


class Rules(unittest.TestCase):
    def run_lint(self, text, platform="neutral", ptype="character", duration=15.0):
        return lint_prompt.lint(text, platform, ptype, duration, 7000)

    def codes(self, findings, severity="error"):
        return {f.code for f in findings if f.severity == severity}

    def test_gap_detected(self):
        text = "画面内角色：\n- 甲：x\n画外声音或对象：无。\n不出场人物：无。\n0.0–5.0秒：a\n6.0–13.0秒：b\n13.0–15.0秒稳定尾帧：c"
        self.assertIn("timecode", self.codes(self.run_lint(text)))

    def test_short_tail(self):
        text = "画面内角色：\n- 甲：x\n画外声音或对象：无。\n不出场人物：无。\n0.0–14.0秒：a\n14.0–15.0秒稳定：b"
        self.assertIn("tail_frame", self.codes(self.run_lint(text)))

    def test_qita_is_not_pronoun(self):
        text = "画面内角色：\n- 甲：x\n画外声音或对象：无。\n不出场人物：其他人、其他同事、其他路人、其他邻居。\n0.0–15.0秒稳定尾帧：a"
        self.assertNotIn("pronoun", self.codes(self.run_lint(text), "warn"))

    def test_h3_speaker_after_dialogue(self):
        text = "\n".join(lint_prompt.H3_SECTIONS) + "\n0.0s–15.0s: 母亲说：<d>[Chinese] 好。</d>（S1）stable final frame"
        self.assertIn("h3_dialogue", self.codes(self.run_lint(text, "h3_full_reference")))

    def test_h3_freetext_allows_soundscape(self):
        text = "画面内角色：\n- 程序员（S1）：x\n画外声音或对象：无。\n不出场人物：无。\n0.0–15.0秒稳定：程序员（S1）说：<d>[Chinese] 好。</d>\noverall_soundscape：底噪。"
        self.assertEqual(self.codes(self.run_lint(text, "h3_freetext")), set())

    def test_seedance_rejects_h3_tags(self):
        text = "画面内角色：\n- 甲：x\n画外声音或对象：无。\n不出场人物：无。\n0.0–15.0秒稳定：甲（S1）说：<d>[Chinese] 好。</d>"
        self.assertIn("syntax_mix", self.codes(self.run_lint(text, "seedance")))

    def test_length_limit(self):
        text = "画面内角色：\n- 甲：x\n画外声音或对象：无。\n不出场人物：无。\n0.0–15.0秒稳定：" + "字" * 7100
        self.assertIn("length", self.codes(self.run_lint(text)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
