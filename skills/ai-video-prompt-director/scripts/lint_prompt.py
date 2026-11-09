#!/usr/bin/env python3
"""Deterministic checks for a copy-ready AI video prompt.

Catches the mechanical mistakes that rules alone keep missing: copy-zone
pollution, mixed platform syntax, timecode gaps, missing stable tail, cast
header, H3 dialogue format and length. Judgment items (causality, subtext,
reference competition) stay in references/checklist.md.

Exit code: 0 when no errors (warnings allowed), 1 when any error, 2 on usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

PLATFORMS = ("neutral", "seedance", "h3_freetext", "h3_full_reference")
TYPES = ("character", "environment")
H3_SECTIONS = (
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
)

COPY_ZONE_PATTERNS = [
    (r"@(?:图|图片|视频|音频|image|Image|video|Video)\s*\d*", "临时@编号"),
    (r"\b(?:CHAR|ENV|PROP)-[A-Za-z0-9_-]+", "稳定资产ID"),
    (r"[A-Za-z]:\\[^\s，。]+|(?:\.{0,2}/)?[\w\-]+/[\w\-/]+\.(?:png|jpe?g|webp|mp4|mov|wav|mp3)\b", "文件路径"),
    (r"\b[0-9a-f]{64}\b", "SHA-256"),
    (r"承接上一[帧段镜]|接上一段|上一段|下一段|第[一二三四五六七八九十百\d]+集|段号|上传顺序|验收记录", "制作管理语句"),
]
SYNTAX_H3 = r"[（(]S\d+[）)]|</?d>|subject_definitions|retention_analysis|overall_soundscape|non_diegetic_music|<(?:Subject|Picture|Video|Audio)\s*\d+>"
SYNTAX_H3_NATIVE_ONLY = r"subject_definitions|retention_analysis|<(?:Subject|Picture|Video|Audio)\s*\d+>"
PRONOUN = r"(?<!其)他(?!们)|她(?!们)|对方|那里"
BUZZWORDS = r"电影感|高级感|震撼|氛围感|大片感|史诗感|唯美|绝美|情绪拉满"
CAMERA_PUSH = r"推进|推近"
TIMECODE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:秒|s|sec)?\s*[–—\-~～至到]\s*(\d+(?:\.\d+)?)\s*(?:秒|s\b|sec\b)"
)
TAIL_WORDS = r"尾帧|稳定|静止|停住|保持不变|不动|stable|still|final frame"


@dataclass
class Finding:
    severity: str  # error | warn
    code: str
    message: str
    line: int | None = None


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def extract_block(markdown: str, index: int) -> str:
    blocks = re.findall(r"```[^\n]*\n(.*?)```", markdown, flags=re.S)
    if not 1 <= index <= len(blocks):
        raise SystemExit(f"--block {index} 超出范围：文件里有 {len(blocks)} 个代码块")
    return blocks[index - 1]


def first_nonempty(text: str) -> str:
    for ln in text.splitlines():
        if ln.strip():
            return ln.strip()
    return ""


def check_copy_zone(text: str, out: list[Finding]) -> None:
    for pattern, label in COPY_ZONE_PATTERNS:
        for m in re.finditer(pattern, text):
            out.append(Finding("error", "copy_zone", f"复制区出现{label}：{m.group(0)!r}，应放代码块外", line_of(text, m.start())))


def check_syntax(text: str, platform: str, out: list[Finding]) -> None:
    if platform in ("neutral", "seedance"):
        for m in re.finditer(SYNTAX_H3, text):
            out.append(Finding("error", "syntax_mix", f"{platform}稿混入H3语法：{m.group(0)!r}", line_of(text, m.start())))
    elif platform == "h3_freetext":
        for m in re.finditer(SYNTAX_H3_NATIVE_ONLY, text):
            out.append(Finding("warn", "syntax_mix", f"H3自由文本稿出现全参考原生标签：{m.group(0)!r}；确认目标是否为全参考模式", line_of(text, m.start())))


def check_cast_header(text: str, platform: str, ptype: str, out: list[Finding]) -> None:
    if platform == "h3_full_reference":
        return
    head = first_nonempty(text)
    if ptype == "character":
        if not head.startswith("画面内角色"):
            out.append(Finding("error", "cast_header", f"人物戏复制区应从“画面内角色：”开始，实际开头：{head[:30]!r}", 1))
        if "不出场" not in text:
            out.append(Finding("warn", "cast_header", "缺少“不出场人物”清单，模型可能补入路人或配角"))
        if "画外声音" not in text:
            out.append(Finding("warn", "cast_header", "缺少“画外声音或对象”一行（没有也写“无”）"))
        m = re.search(r"画面内角色[：:]([^\n]+)", text)
        if m and re.search(r"[、，,]", m.group(1)):
            out.append(Finding("warn", "cast_header", "多个可见角色写在同一行，应一人一行", line_of(text, m.start())))
    elif ptype == "environment" and re.search(r"画面内角色[：:]", text):
        out.append(Finding("warn", "env_cast", "环境片出现“画面内角色”清单，确认不是为套模板补造人物"))


def check_timecodes(text: str, duration: float | None, out: list[Finding]) -> None:
    ranges = []
    for m in TIMECODE.finditer(text):
        a, b = float(m.group(1)), float(m.group(2))
        if b <= a:
            out.append(Finding("error", "timecode", f"时间段倒退或为零：{m.group(0)!r}", line_of(text, m.start())))
            continue
        line_no = line_of(text, m.start())
        line_text = text.splitlines()[line_no - 1]
        ranges.append((a, b, line_no, line_text))
    if not ranges:
        if duration:
            out.append(Finding("warn", "timecode", f"没有找到时间码；无法确认覆盖0–{duration:g}秒"))
        return
    if min(r[0] for r in ranges) > 0.05:
        out.append(Finding("error", "timecode", f"时间码没有从0秒开始（最早{min(r[0] for r in ranges):g}秒）"))
    covered = 0.0
    for a, b, ln, _ in sorted(ranges):
        if a > covered + 0.05:
            out.append(Finding("error", "timecode", f"时间码缺口：{covered:g}–{a:g}秒没有内容", ln))
        covered = max(covered, b)
    end = covered
    if duration is not None:
        if end < duration - 0.05:
            out.append(Finding("error", "timecode", f"时间码只覆盖到{end:g}秒，要求{duration:g}秒"))
        elif end > duration + 0.05:
            out.append(Finding("warn", "timecode", f"时间码到{end:g}秒，超过要求的{duration:g}秒"))
    finals = [r for r in ranges if abs(r[1] - end) <= 0.05]
    if not any(r[1] - r[0] >= 1.5 - 1e-6 for r in finals):
        out.append(Finding("error", "tail_frame", f"结尾时间段短于1.5秒，没有稳定尾帧空间（结束于{end:g}秒）"))
    elif not any(re.search(TAIL_WORDS, r[3]) for r in finals):
        out.append(Finding("warn", "tail_frame", "结尾时间段没有写明稳定/尾帧/静止", finals[-1][2]))


def check_length(text: str, max_chars: int, out: list[Finding]) -> None:
    n = len(text.strip())
    if n > max_chars:
        out.append(Finding("error", "length", f"正文{n}字符，超过上限{max_chars}"))


def check_style(text: str, platform: str, ptype: str, out: list[Finding]) -> None:
    if ptype == "character" and platform != "h3_full_reference":
        hits = [m.group(0) for m in re.finditer(PRONOUN, text)]
        if len(hits) > 3:
            out.append(Finding("warn", "pronoun", f"出现{len(hits)}处“他/她/对方/那里”类指代，多人画面中改用角色名或具体位置"))
    buzz = [m.group(0) for m in re.finditer(BUZZWORDS, text)]
    if len(buzz) >= 3:
        out.append(Finding("warn", "buzzword", f"空泛审美词{len(buzz)}处（{'、'.join(sorted(set(buzz)))}），换成可见的动作、光线或材质"))
    if ptype == "environment":
        pushes = len(re.findall(CAMERA_PUSH, text))
        if pushes >= 3:
            out.append(Finding("warn", "camera_repeat", f"出现{pushes}次推进/推近，连续推近会造成重复参观感"))
        if "旁白" in text:
            if not re.search(r"没有任何人物|无人物|无人|没有人物|画面内没有", text):
                out.append(Finding("warn", "env_voice", "有旁白但没写明画面内无人物，模型可能补出说话的人"))
            if "口型" not in text:
                out.append(Finding("warn", "env_voice", "有旁白但没写“无口型”，旁白可能被绑到一张嘴上"))


def check_h3(text: str, platform: str, out: list[Finding]) -> None:
    if platform not in ("h3_freetext", "h3_full_reference"):
        return
    if text.count("<d>") != text.count("</d>"):
        out.append(Finding("error", "h3_dialogue", "<d>与</d>数量不一致"))
    lines = text.splitlines()
    for m in re.finditer(r"<d>(.*?)</d>", text, flags=re.S):
        ln = line_of(text, m.start())
        inner = m.group(1).strip()
        if not re.match(r"\[[A-Za-z]+\]", inner):
            out.append(Finding("error", "h3_dialogue", f"<d>内应以语言标签开头，如[Chinese]：{inner[:20]!r}", ln))
        if re.search(r"镜头|字幕|画外|语气|camera|subtitle", inner):
            out.append(Finding("warn", "h3_dialogue", f"<d>内混入了说明文字：{inner[:20]!r}；身份、语气、镜头放在<d>外", ln))
        line_start = text.rfind("\n", 0, m.start()) + 1
        prev_close = text.rfind("</d>", line_start, m.start())
        before = text[max(line_start, prev_close + 4 if prev_close != -1 else line_start):m.start()]
        if not re.search(r"[（(]S\d+[）)]", before):
            out.append(Finding("error", "h3_dialogue", "<d>前没有说话人编号(Sx)；编号要写在发声动词和<d>之前", ln))
    if platform == "h3_full_reference":
        head = first_nonempty(text)
        if not head.startswith("subject_definitions"):
            out.append(Finding("error", "h3_sections", f"H3全参考原生稿应从subject_definitions开始，实际：{head[:30]!r}", 1))
        names = {ln.strip() for ln in lines}
        missing = [s for s in H3_SECTIONS if s not in names]
        if missing:
            out.append(Finding("error", "h3_sections", f"缺少原生段落：{', '.join(missing)}"))


def lint(text: str, platform: str, ptype: str, duration: float | None, max_chars: int) -> list[Finding]:
    out: list[Finding] = []
    check_copy_zone(text, out)
    check_syntax(text, platform, out)
    check_cast_header(text, platform, ptype, out)
    check_timecodes(text, duration, out)
    check_length(text, max_chars, out)
    check_style(text, platform, ptype, out)
    check_h3(text, platform, out)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="检查复制提示词的确定性问题；判断性问题见references/checklist.md")
    ap.add_argument("source", help="提示词文件；'-'从标准输入读取")
    ap.add_argument("--block", type=int, help="从Markdown中取第N个代码块（从1开始）")
    ap.add_argument("--platform", choices=PLATFORMS, default="neutral")
    ap.add_argument("--type", dest="ptype", choices=TYPES, default="character")
    ap.add_argument("--duration", type=float, help="要求的总时长（秒）")
    ap.add_argument("--max-chars", type=int, default=7000)
    ap.add_argument("--json", action="store_true", help="输出JSON")
    args = ap.parse_args(argv)

    raw = sys.stdin.read() if args.source == "-" else Path(args.source).read_text(encoding="utf-8")
    text = extract_block(raw, args.block) if args.block else raw
    findings = lint(text, args.platform, args.ptype, args.duration, args.max_chars)
    errors = [f for f in findings if f.severity == "error"]

    if args.json:
        print(json.dumps({"errors": len(errors), "warnings": len(findings) - len(errors),
                          "findings": [asdict(f) for f in findings]}, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            where = f" (第{f.line}行)" if f.line else ""
            print(f"{f.severity.upper():5} [{f.code}] {f.message}{where}")
        print(f"— {len(errors)} 个错误，{len(findings) - len(errors)} 个警告")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
