#!/usr/bin/env python3
"""Check the UE skill bundles' Markdown against their documentation conventions.

The conventions live in each bundle's
``unreal-engine-mcp/references/shared-conventions.md`` ("Documentation
conventions"). Standard library only.

    python tools/ue_docs_lint.py                 # lint skills/ue*/ ; exit 1 on a finding
    python tools/ue_docs_lint.py --reflow        # also add missing contents lists and rewrap long prose
    python tools/ue_docs_lint.py skills/ue5.9    # one bundle
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WRAP = 80          # target width when rewrapping
MAX_WIDTH = 100    # widest prose line the lint accepts
LONG_REFERENCE = 150
RECORDS = "## 验证记录"
SKILLS = ("unreal-engine-mcp", "unreal-material-artist", "niagara-vfx-artist", "unreal-sequencer",
          "vfx-flipbook-generator")

SESSION_WORDS = re.compile(
    r"本次|本轮|这次|上一轮|当时|\bthis (?:pass|run|session|audit|test)\b|(?<![`\d-])20\d\d-\d\d-\d\d(?![`\d-])", re.I)
ASSISTANTS = re.compile(r"\b(Codex|Claude|ChatGPT|Copilot)\b")
RETIRED = re.compile(r"UnrealBridge|unreal-bridge|Unreal Bridge", re.I)
OLD_TOOLSETS = re.compile(
    r"\b(MaterialTools|MaterialInstanceTools|ObjectTools|AssetTools|SceneTools|TextureTools|BlueprintTools|"
    r"ActorTools|ProgrammaticToolset|SequencerTools|SequencerKeyframingTools)\b")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")
SPECIAL = re.compile(r"^\s*(#{1,6}\s|\||<|```|~~~|---\s*$|\*\*\*\s*$|\[[^\]]+\]:\s)")


def width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def is_cjk(ch: str) -> bool:
    return unicodedata.east_asian_width(ch) in "WF"


def slug(heading: str) -> str:
    """GitHub-style anchor for a heading line's text."""
    text = re.sub(r"`", "", heading.strip().lower())
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = "".join(ch for ch in text if ch.isalnum() or ch in " -_" or is_cjk(ch) and unicodedata.category(ch)[0] == "L")
    return text.replace(" ", "-")


class Doc:
    def __init__(self, path: Path):
        self.path = path
        self.text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        self.lines = self.text.split("\n")
        self.kinds = self._classify()

    def _classify(self) -> list[str]:
        """Per line: 'front', 'code', 'table', 'heading', 'blank', 'record' or 'prose'."""
        kinds, fence, front, record = [], None, False, False
        for index, line in enumerate(self.lines):
            stripped = line.strip()
            if index == 0 and stripped == "---":
                front = True
                kinds.append("front")
                continue
            if front:
                kinds.append("front")
                front = stripped != "---"
                continue
            marker = re.match(r"^\s*(```|~~~)", line)
            if fence:
                kinds.append("code")
                if marker and marker.group(1) == fence:
                    fence = None
                continue
            if marker:
                fence = marker.group(1)
                kinds.append("code")
                continue
            if re.match(r"^#{1,6}\s", line):
                top = line.startswith("## ") or line.startswith("# ")
                record = line.strip() == RECORDS if top else record
                kinds.append("heading" if top or not record else "record-heading")
            elif not stripped:
                kinds.append("blank")
            elif stripped.startswith("|"):
                kinds.append("record-table" if record else "table")
            else:
                kinds.append("record" if record else "prose")
        return kinds

    def anchors(self) -> set[str]:
        found: dict[str, int] = {}
        out = set()
        for line, kind in zip(self.lines, self.kinds):
            if kind == "heading":
                base = slug(line.lstrip("#"))
                count = found.get(base, 0)
                found[base] = count + 1
                out.add(base if not count else f"{base}-{count}")
        return out


def lint_doc(doc: Doc, bundle: Path, docs: dict[Path, Doc]) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    rel = doc.path.relative_to(bundle)
    version = bundle.name.removeprefix("ue")
    is_skill = doc.path.name == "SKILL.md"
    in_references = "references" in rel.parts

    if is_skill:
        front = "\n".join(line for line, kind in zip(doc.lines, doc.kinds) if kind == "front")
        description = re.search(r"^description:\s*(.+)$", front, re.M)
        if not re.search(r"^name:\s*\S", front, re.M) or not description:
            findings.append((1, "SKILL.md needs `name` and `description` front matter"))
        else:
            text = description.group(1)
            if not re.search(r"\bUse when\b", text):
                findings.append((1, "description must say when to use the skill (\"Use when ...\")"))
            if ASSISTANTS.search(text):
                findings.append((1, "description must not name an assistant"))
        if rel.parts[0] != "vfx-flipbook-generator" and f"UE {version}" not in doc.text:
            findings.append((1, f"SKILL.md must state that it targets UE {version}"))
        if version == "5.9" and "Preview" not in doc.text:
            findings.append((1, "SKILL.md must state the verified build (UE 5.9.0 Preview)"))

    sections = sum(1 for line, kind in zip(doc.lines, doc.kinds) if kind == "heading" and line.startswith("## "))
    if in_references and len(doc.lines) > LONG_REFERENCE and doc.path.name != "index.md" and sections >= 3:
        if not re.search(r"^## (Contents|Table of Contents|目录)\s*$", doc.text, re.M | re.I):
            findings.append((1, f"reference longer than {LONG_REFERENCE} lines needs a `## Contents` list"))

    for number, (line, kind) in enumerate(zip(doc.lines, doc.kinds), start=1):
        if kind in {"prose", "heading", "table"}:
            match = SESSION_WORDS.search(re.sub(r"`[^`]*`", "", line))
            if match and in_references and version == "5.9":
                findings.append((number, f"session wording or date outside `{RECORDS}`: {match.group(0)!r}"))
            if version == "5.9" and (is_skill or rel.name.startswith("ue-5.9-") or rel.parts[0] == "unreal-engine-mcp"):
                old = OLD_TOOLSETS.search(line)
                if old and "unported" not in line and rel.name != "porting-helpers.md":
                    findings.append((number, f"UE 5.8 toolset name in a UE 5.9 document: {old.group(0)}"))
        if kind != "code" and RETIRED.search(line):
            findings.append((number, "mentions the retired UnrealBridge plugin"))
        if kind in {"prose", "record"} and width(line) > MAX_WIDTH:
            longest = max((width(token) for token in re.split(r"\s+", line)), default=0)
            atoms = [width(m.group(0)) for m in re.finditer(r"`[^`]*`|\[[^\]]*\]\([^)]*\)", line)]
            if max([longest, *atoms]) <= MAX_WIDTH - 8:
                findings.append((number, f"prose line is {width(line)} columns wide (limit {MAX_WIDTH})"))
        if kind == "code":
            continue
        for target in LINK.findall(line):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("<"):
                continue
            file_part, _, anchor = target.partition("#")
            dest = (doc.path.parent / file_part).resolve() if file_part else doc.path
            if file_part and not dest.exists():
                findings.append((number, f"broken link: {target}"))
                continue
            if dest.is_relative_to(bundle.parent) and dest.is_relative_to(bundle.parent / "ue5.8") != (
                    bundle.name == "ue5.8") and re.match(r"ue5\.\d", dest.relative_to(bundle.parent).parts[0]):
                findings.append((number, f"link crosses engine bundles: {target}"))
            if anchor and dest.suffix == ".md":
                other = docs.get(dest) or Doc(dest)
                if anchor.lower() not in other.anchors():
                    findings.append((number, f"broken anchor: {target}"))
    return findings


def reachable(bundle: Path, docs: dict[Path, Doc]) -> set[Path]:
    seen: set[Path] = set()
    queue = [bundle / name / "SKILL.md" for name in SKILLS if (bundle / name / "SKILL.md").exists()]
    queue += [bundle / name / "README.md" for name in SKILLS if (bundle / name / "README.md").exists()]
    while queue:
        path = queue.pop()
        if path in seen or path not in docs:
            continue
        seen.add(path)
        for line, kind in zip(docs[path].lines, docs[path].kinds):
            if kind == "code":
                continue
            for target in LINK.findall(line):
                file_part = target.partition("#")[0]
                if file_part and not re.match(r"^[a-z][a-z0-9+.-]*:", file_part):
                    queue.append((path.parent / file_part).resolve())
    return seen


# --- rewrapping ----------------------------------------------------------

ATOM = re.compile(r"`[^`]*`|!?\[[^\]]*\]\([^)]*\)|\S")
CLOSERS = set("，。；：、）】》」』！？,.;:!?)]}”’%")
OPENERS = set("（【《「『([{“‘")


def atoms(text: str) -> list[tuple[str, bool]]:
    """Unbreakable pieces of a paragraph, each with whether a space preceded it."""
    out: list[tuple[str, bool]] = []
    position, spaced = 0, False
    for match in ATOM.finditer(text):
        gap = text[position:match.start()]
        spaced = bool(gap) or (spaced and not out)
        piece = match.group(0)
        glue = False
        if out and not gap and len(piece) == 1:
            previous = out[-1][0]
            last = previous[-1]
            # Latin runs stay whole; punctuation stays attached to its neighbour.
            glue = ((not is_cjk(piece) and not is_cjk(last) and len(previous) and previous[0] not in "`[!")
                    or piece in CLOSERS or last in OPENERS)
            if previous[0] in "`[!" and len(previous) > 1 and not is_cjk(piece):
                glue = True
        elif out and not gap:
            last = out[-1][0][-1]
            glue = not is_cjk(last) or last in OPENERS
        if glue:
            out[-1] = (out[-1][0] + piece, out[-1][1])
        else:
            out.append((piece, bool(gap)))
        position = match.end()
    return out


def wrap(text: str, first: str, rest: str) -> list[str]:
    lines, current = [], first
    empty = True
    for piece, spaced in atoms(text):
        candidate = current + (" " if spaced and not empty else "") + piece
        starts_block = re.match(r"^([-*+>#|]|\d+[.)])(\s|$)", piece) is not None
        if not empty and width(candidate) > WRAP and not starts_block:
            lines.append(current)
            current, candidate = rest, rest + piece
        current, empty = candidate, False
    lines.append(current)
    return lines


def reflow(doc: Doc) -> str:
    out: list[str] = []
    index, total = 0, len(doc.lines)
    while index < total:
        line, kind = doc.lines[index], doc.kinds[index]
        if kind not in {"prose", "record"} or SPECIAL.match(line):
            out.append(line)
            index += 1
            continue
        block = [line]
        probe = index + 1
        while (probe < total and doc.kinds[probe] in {"prose", "record"} and not SPECIAL.match(doc.lines[probe])
               and not LIST_ITEM.match(doc.lines[probe]) and not doc.lines[probe].lstrip().startswith(">")):
            block.append(doc.lines[probe])
            probe += 1
        index = probe
        hard_break = any(item.endswith("  ") or item.endswith("\\") for item in block[:-1])
        quoted = block[0].lstrip().startswith(">")
        if hard_break or quoted or max(width(item) for item in block) <= 88:
            out.extend(block)
            continue
        item = LIST_ITEM.match(block[0])
        if item:
            first = block[0][:item.end()]
            rest = " " * width(first)
        else:
            first = rest = block[0][:len(block[0]) - len(block[0].lstrip())]
            if len(first) >= 4:      # indented code, or a continuation whose shape must stay
                out.extend(block)
                continue
        body = block[0][len(first):].strip()
        for extra in block[1:]:
            extra = extra.strip()
            joiner = "" if body and extra and is_cjk(body[-1]) and is_cjk(extra[0]) else " "
            body += joiner + extra
        out.extend(wrap(body, first, rest))
    return "\n".join(out)


def add_contents(doc: Doc) -> str | None:
    """Insert a contents list before the first level-2 heading of a long reference."""
    if (len(doc.lines) <= LONG_REFERENCE or doc.path.name == "index.md" or "references" not in doc.path.parts
            or re.search(r"^## (Contents|Table of Contents|目录)\s*$", doc.text, re.M | re.I)):
        return None
    entries, seen, first = [], {}, None
    for index, (line, kind) in enumerate(zip(doc.lines, doc.kinds)):
        if kind != "heading":
            continue
        base = slug(line.lstrip("#"))
        count = seen.get(base, 0)
        seen[base] = count + 1
        if line.startswith("## "):
            first = index if first is None else first
            entries.append(f"- [{line[3:].strip()}](#{base if not count else f'{base}-{count}'})")
    if first is None or len(entries) < 3:
        return None
    title = next((line for line in doc.lines if line.startswith("# ")), "")
    heading = "## 目录" if any(is_cjk(ch) for ch in title) else "## Contents"
    lines = doc.lines[:first] + [heading, "", *entries, ""] + doc.lines[first:]
    return "\n".join(lines)


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bundles", nargs="*", help="Bundle folders (default: every skills/ue*/)")
    parser.add_argument("--reflow", action="store_true",
                        help="Add missing contents lists and rewrap over-long prose before linting")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    bundles = [Path(item).resolve() for item in args.bundles] or sorted((REPO / "skills").glob("ue[0-9]*"))
    total = 0
    for bundle in bundles:
        paths = sorted(path for name in SKILLS for path in (bundle / name).rglob("*.md")
                       if "ffmpeg" not in path.parts)
        if args.reflow:
            changed = 0
            for path in paths:
                with_contents = add_contents(Doc(path))
                if with_contents is not None:
                    path.write_text(with_contents, encoding="utf-8", newline="\n")
                doc = Doc(path)
                new = reflow(doc)
                if new != doc.text:
                    if squash(new) != squash(doc.text):
                        raise SystemExit(f"reflow would change the text of {path}; nothing written for it")
                    path.write_text(new, encoding="utf-8", newline="\n")
                    changed += 1
            print(f"{bundle.name}: rewrapped {changed} file(s)")
        docs = {path: Doc(path) for path in paths}
        linked = reachable(bundle, docs)
        for path, doc in docs.items():
            findings = lint_doc(doc, bundle, docs)
            if "references" in path.parts and path not in linked:
                findings.append((1, "reference is not linked from SKILL.md, an index or another reference"))
            for number, message in findings:
                print(f"{path.relative_to(REPO).as_posix()}:{number}: {message}")
            total += len(findings)
    print(f"{total} finding(s)")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
