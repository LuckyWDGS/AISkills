#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Pillow is required. Install it with `pip install pillow` before running this script."
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
PROFILE_VARIANTS = {
    "dance-25": {"en": ASSETS / "dance-25-panel.json", "zh": ASSETS / "dance-25-panel-zh.json"},
    "commerce-fashion-25": {
        "en": ASSETS / "commerce-fashion-25-panel.json",
        "zh": ASSETS / "commerce-fashion-25-panel-zh.json",
    },
    "dreamy-25": {"en": ASSETS / "dreamy-25-panel.json", "zh": ASSETS / "dreamy-25-panel-zh.json"},
    "xianxia-fantasy-25": {
        "en": ASSETS / "xianxia-fantasy-25-panel.json",
        "zh": ASSETS / "xianxia-fantasy-25-panel-zh.json",
    },
    "start-end-9": {"en": ASSETS / "start-end-9-panel.json", "zh": ASSETS / "start-end-9-panel-zh.json"},
}
SUPPORTED_LANGUAGES = ("en", "zh")
KEYFRAME_ROLES = ("start", "bridge", "middle", "hero", "end", "loop")
MOTION_STRENGTH_LEVELS = ("low", "medium", "high")
PANEL_TEXT_FIELDS = (
    "source_panel",
    "text_source",
    "source_visual",
    "story_beat",
    "story_text",
    "subtitle",
    "voiceover",
    "subtitle_voiceover",
    "sound_design",
    "binding_status",
)
REFERENCE_ROLE_LABELS = {
    "face_anchors": {"zh": "脸部锚点", "en": "face anchors"},
    "outfit_anchors": {"zh": "服装锚点", "en": "outfit anchors"},
    "product_anchors": {"zh": "商品锚点", "en": "product anchors"},
    "scene_anchors": {"zh": "场景锚点", "en": "scene anchors"},
    "style_anchors": {"zh": "风格锚点", "en": "style anchors"},
    "generic_references": {"zh": "辅助参考图", "en": "generic references"},
}
REFERENCE_ROLE_DEFAULTS = {
    "face_anchors": {
        "weight": 1.0,
        "priority": 100,
        "crop": "face close-up / 3:4 portrait crop",
        "focus": "face identity, hairline, eyes, nose, mouth, expression",
        "lock": "hard-identity",
    },
    "outfit_anchors": {
        "weight": 0.85,
        "priority": 80,
        "crop": "full-body or garment crop",
        "focus": "silhouette, neckline, sleeve, hemline, fabric, accessories",
        "lock": "hard-outfit",
    },
    "product_anchors": {
        "weight": 0.95,
        "priority": 90,
        "crop": "product/detail macro crop",
        "focus": "product truth, logo, seam, texture, hardware, shape",
        "lock": "hard-detail",
    },
    "scene_anchors": {
        "weight": 0.65,
        "priority": 55,
        "crop": "wide environment crop",
        "focus": "scene layout, lighting direction, architecture, atmosphere",
        "lock": "soft-scene",
    },
    "style_anchors": {
        "weight": 0.45,
        "priority": 35,
        "crop": "style/color/mood crop",
        "focus": "palette, lighting, finish, lens mood, grading",
        "lock": "soft-style",
    },
    "generic_references": {
        "weight": 0.35,
        "priority": 20,
        "crop": "loose reference crop",
        "focus": "general inspiration only",
        "lock": "soft-inspiration",
    },
    "first_frame": {
        "weight": 1.0,
        "priority": 110,
        "crop": "full frame",
        "focus": "starting composition, camera, subject pose, environment",
        "lock": "hard-keyframe",
    },
    "last_frame": {
        "weight": 1.0,
        "priority": 110,
        "crop": "full frame",
        "focus": "ending composition, camera, subject pose, environment",
        "lock": "hard-keyframe",
    },
}
REFERENCE_CONFLICT_POLICY = {
    "zh": "冲突规则：先按 priority 处理，再按 weight 强弱处理；脸部身份不被服装/商品参考改写，商品/法器细节只锁定对应局部，服装锚点锁廓形和材质，场景与风格只影响环境和色调。",
    "en": "Conflict policy: resolve by priority first, then by weight; face identity is not rewritten by outfit/product references, product/prop anchors lock only their local details, outfit anchors lock silhouette/materials, scene/style anchors affect environment and mood only.",
}

DEFAULT_CONTEXT = {
    "commerce-fashion-25": {
        "en": {
            "subject": "the same female fashion host",
            "product": "the same truthful fashion item",
            "scene": "a clean premium livestream studio",
            "mood": "premium, social-native, and trustworthy",
            "platform": "Douyin/TikTok",
            "aspect": "9:16",
        },
        "zh": {
            "subject": "同一位女装主播",
            "product": "同一件真实可卖的服装单品",
            "scene": "干净高级的直播间影棚",
            "mood": "高级真实、亲和种草",
            "platform": "抖音",
            "aspect": "9:16",
        },
    },
    "dance-25": {
        "en": {
            "subject": "the same female dancer",
            "product": "the same dance outfit",
            "scene": "the same dance studio",
            "mood": "energetic, rhythmic, and charismatic",
            "platform": "short-video",
            "aspect": "9:16",
        },
        "zh": {
            "subject": "同一位女舞者",
            "product": "同一套舞蹈服装",
            "scene": "同一个舞蹈教室",
            "mood": "节奏强、利落、有感染力",
            "platform": "短视频",
            "aspect": "9:16",
        },
    },
    "dreamy-25": {
        "en": {
            "subject": "the same dreamy female lead",
            "product": "the same hero costume",
            "scene": "the same luminous fantasy environment",
            "mood": "ethereal, slow, and cinematic",
            "platform": "short-video",
            "aspect": "9:16",
        },
        "zh": {
            "subject": "同一位梦幻系女主角",
            "product": "同一套主视觉服装",
            "scene": "同一个发光梦境空间",
            "mood": "空灵、缓慢、电影感",
            "platform": "短视频",
            "aspect": "9:16",
        },
    },
    "xianxia-fantasy-25": {
        "en": {
            "subject": "the same xianxia protagonist",
            "product": "the same immortal costume, weapon, and magic props",
            "scene": "the same epic Chinese fantasy palace realm",
            "mood": "beautiful, mythic, vast, and cinematic",
            "platform": "short-video",
            "aspect": "9:16",
        },
        "zh": {
            "subject": "同一位玄幻仙侠主角",
            "product": "同一套仙侠服装、法器与随身道具",
            "scene": "同一个国风玄幻仙宫巨景",
            "mood": "唯美玄幻、仙气、史诗电影感",
            "platform": "短视频",
            "aspect": "9:16",
        },
    },
    "start-end-9": {
        "en": {
            "subject": "the same protagonist",
            "product": "the same outfit and props",
            "scene": "the same room",
            "mood": "clear, smooth, and controllable",
            "platform": "image-to-video planning",
            "aspect": "9:16",
        },
        "zh": {
            "subject": "同一位主角",
            "product": "同一套服装与道具",
            "scene": "同一个场景",
            "mood": "顺滑、清楚、可控",
            "platform": "图生视频规划",
            "aspect": "9:16",
        },
    },
}

PROFILE_TITLE_SUFFIX = {
    "commerce-fashion-25": {"en": "Commerce Storyboard", "zh": "带货分镜板"},
    "dance-25": {"en": "Dance Storyboard", "zh": "舞蹈分镜板"},
    "dreamy-25": {"en": "Dreamy Storyboard", "zh": "梦幻分镜板"},
    "xianxia-fantasy-25": {"en": "Xianxia Fantasy Storyboard", "zh": "玄幻仙侠分镜板"},
    "start-end-9": {"en": "Start-End Motion Board", "zh": "首尾帧桥接板"},
}

BRIEF_SPLIT_RE = re.compile(r"[，,、；;。|/\n]+")
PRODUCT_KEYWORDS_ZH = [
    "针织连衣裙",
    "针织裙",
    "连衣裙",
    "半身裙",
    "百褶裙",
    "牛仔裙",
    "风衣",
    "西装外套",
    "外套",
    "毛衣",
    "针织衫",
    "衬衫",
    "卫衣",
    "背心",
    "羽绒服",
    "大衣",
    "裤子",
    "阔腿裤",
    "牛仔裤",
    "套装",
]
SCENE_KEYWORDS_ZH = [
    "直播间",
    "影棚",
    "舞蹈教室",
    "舞室",
    "月光大厅",
    "镜厅",
    "试衣间",
    "卧室",
    "客厅",
    "街头",
    "天台",
    "秀场",
    "咖啡店",
    "湖边",
    "森林",
    "仙宫",
    "天宫",
    "神殿",
    "宫阙",
    "山门",
    "仙门",
    "古寺",
    "祭坛",
    "云海",
    "峡谷",
    "悬崖",
    "瀑布",
    "天池",
    "桃花林",
    "巨树",
    "山海",
]
SUBJECT_KEYWORDS_ZH = [
    "女主播",
    "主播",
    "模特",
    "舞者",
    "女生",
    "女孩",
    "姐姐",
    "博主",
    "主角",
    "女主",
    "男主",
    "男生",
    "少年",
    "仙女",
    "修士",
    "剑修",
    "剑客",
    "道士",
    "神女",
    "弟子",
]
MOOD_KEYWORDS_ZH = [
    "高级真实",
    "亲和种草",
    "梦幻空灵",
    "电影感",
    "法式",
    "轻熟",
    "温柔",
    "通勤",
    "高级",
    "真实",
    "空灵",
    "梦幻",
    "松弛",
    "酷飒",
    "甜美",
    "慵懒",
    "清冷",
    "华丽",
    "唯美玄幻",
    "玄幻",
    "仙侠",
    "国风",
    "神话",
    "东方幻想",
    "史诗",
    "宏大",
    "仙气",
    "山海经",
]
FOCUS_POINT_KEYWORDS_ZH = [
    "面料垂感",
    "显瘦",
    "显高",
    "遮肉",
    "腿长",
    "腰线",
    "轻盈",
    "弹力",
    "亲肤",
    "透气",
    "版型",
    "质感",
    "面料",
    "动作补全",
    "首尾帧桥接",
    "踩点",
    "首尾帧",
    "关键帧",
    "巨景",
    "仙宫巨景",
    "云雾",
    "丁达尔光",
    "神光",
    "光束",
    "粒子",
    "飞鱼",
    "灵兽",
    "御剑",
    "飞升",
    "结印",
]
ACTION_KEYWORDS_ZH = [
    "转身",
    "回头",
    "抬手",
    "走近",
    "甩头",
    "旋转",
    "踩点",
    "摆臂",
    "抬腿",
    "前进一步",
    "御剑",
    "飞升",
    "结印",
    "拔剑",
    "入殿",
    "登阶",
    "回眸",
]
PLATFORM_KEYWORDS = {
    "抖音": "抖音",
    "douyin": "Douyin",
    "tiktok": "TikTok",
    "reels": "Reels",
    "小红书": "小红书",
}
NOISE_TERMS_ZH = [
    "分镜",
    "镜头",
    "视频",
    "短视频",
    "脚本",
    "方案",
    "带货",
    "展示",
    "上新",
    "种草",
    "做一套",
    "做一个",
]
DEFAULT_DOMESTIC_SAFE_LEXICON = ASSETS / "domestic-video-safe-lexicon.json"
DEFAULT_DOMESTIC_SCAN_EXCLUDE_NAMES = {
    "README.md",
    "sensitive-replacement-report.md",
    "domestic-video-safe-lexicon.json",
}
DOMESTIC_SCAN_SUFFIXES = {".txt", ".md", ".json"}
MARKDOWN_FENCE_RE = re.compile(r"```(?:text|prompt)?\s*\n(.*?)\n```", re.IGNORECASE | re.DOTALL)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed storyboard specs, apply a brief, render contact sheets, and export shot lists."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_spec = subparsers.add_parser("new-spec", help="Copy a template spec into a new JSON file.")
    new_spec.add_argument(
        "--profile",
        choices=sorted(PROFILE_VARIANTS),
        required=True,
        help="Template profile to copy.",
    )
    new_spec.add_argument(
        "--language",
        choices=SUPPORTED_LANGUAGES,
        default="en",
        help="Template language. Defaults to English.",
    )
    new_spec.add_argument("--out", required=True, type=Path, help="Output JSON path.")
    new_spec.add_argument("--title", help="Optional title override.")
    new_spec.add_argument("--subtitle", help="Optional subtitle override.")

    apply_brief = subparsers.add_parser(
        "apply-brief",
        help="Apply a short brief and global lock to an existing storyboard spec.",
    )
    apply_brief.add_argument("--spec", required=True, type=Path, help="Input JSON spec path.")
    apply_brief.add_argument("--out", required=True, type=Path, help="Output JSON path.")
    apply_brief.add_argument("--brief", required=True, help="Short concept or campaign brief.")
    apply_brief.add_argument("--language", choices=SUPPORTED_LANGUAGES, help="Override detected language.")
    apply_brief.add_argument("--subject", help="Explicit protagonist summary.")
    apply_brief.add_argument("--product", help="Explicit product or outfit summary.")
    apply_brief.add_argument("--scene", help="Explicit environment or room summary.")
    apply_brief.add_argument("--mood", help="Explicit tone or visual direction.")
    apply_brief.add_argument("--platform", help="Explicit platform label such as 抖音 or TikTok.")
    apply_brief.add_argument("--aspect", help="Explicit aspect such as 9:16.")
    apply_brief.add_argument("--title", help="Optional title override.")
    apply_brief.add_argument("--subtitle", help="Optional subtitle override.")

    inspect_brief = subparsers.add_parser(
        "inspect-brief",
        help="Parse a short brief into inferred storyboard context without editing a spec.",
    )
    inspect_brief.add_argument("--brief", required=True, help="Short concept or campaign brief.")
    inspect_brief.add_argument(
        "--profile",
        choices=sorted(PROFILE_VARIANTS),
        default="commerce-fashion-25",
        help="Profile hint used for inference.",
    )
    inspect_brief.add_argument("--language", choices=SUPPORTED_LANGUAGES, help="Override detected language.")
    inspect_brief.add_argument("--subject", help="Explicit protagonist summary.")
    inspect_brief.add_argument("--product", help="Explicit product or outfit summary.")
    inspect_brief.add_argument("--scene", help="Explicit environment or room summary.")
    inspect_brief.add_argument("--mood", help="Explicit tone or visual direction.")
    inspect_brief.add_argument("--platform", help="Explicit platform label such as 抖音 or TikTok.")
    inspect_brief.add_argument("--aspect", help="Explicit aspect such as 9:16.")
    inspect_brief.add_argument("--out", type=Path, help="Optional JSON output path.")

    attach_refs = subparsers.add_parser(
        "attach-references",
        help="Attach protagonist images, generic references, and first/last frames to a spec.",
    )
    attach_refs.add_argument("--spec", required=True, type=Path, help="Input JSON spec path.")
    attach_refs.add_argument("--out", required=True, type=Path, help="Output JSON path.")
    attach_refs.add_argument("--panel", type=int, help="Optional panel index for panel-specific references.")
    attach_refs.add_argument("--panel-note", help="Optional note about why these references apply to the panel.")
    attach_refs.add_argument(
        "--protagonist-image",
        action="append",
        default=[],
        help="Path to a protagonist identity reference image. Repeatable.",
    )
    attach_refs.add_argument("--face-anchor", action="append", default=[], help="Path to a face identity anchor. Repeatable.")
    attach_refs.add_argument("--outfit-anchor", action="append", default=[], help="Path to an outfit or wardrobe anchor. Repeatable.")
    attach_refs.add_argument("--product-anchor", action="append", default=[], help="Path to a product or garment-detail anchor. Repeatable.")
    attach_refs.add_argument("--scene-anchor", action="append", default=[], help="Path to a scene or environment anchor. Repeatable.")
    attach_refs.add_argument("--style-anchor", action="append", default=[], help="Path to a style or grading anchor. Repeatable.")
    attach_refs.add_argument(
        "--reference-image",
        action="append",
        default=[],
        help="Path to a generic style, scene, or product reference image. Repeatable.",
    )
    attach_refs.add_argument("--first-frame", help="Path to a locked first-frame image.")
    attach_refs.add_argument("--last-frame", help="Path to a locked last-frame image.")
    attach_refs.add_argument("--reference-weight", type=float, help="Override weight for references added by this command, 0.0-1.0.")
    attach_refs.add_argument("--reference-priority", type=int, help="Override priority for references added by this command. Higher wins conflicts.")
    attach_refs.add_argument("--reference-crop", help="Override crop guidance for references added by this command.")
    attach_refs.add_argument("--reference-focus", help="Override focus guidance for references added by this command.")
    attach_refs.add_argument("--reference-lock", help="Override lock strength such as hard-identity, hard-detail, soft-style.")

    annotate_panel = subparsers.add_parser(
        "annotate-panel",
        help="Set video handoff fields or shot metadata for a single panel.",
    )
    annotate_panel.add_argument("--spec", required=True, type=Path, help="Input JSON spec path.")
    annotate_panel.add_argument("--out", required=True, type=Path, help="Output JSON path.")
    annotate_panel.add_argument("--panel", required=True, type=int, help="1-based panel index to annotate.")
    annotate_panel.add_argument("--keyframe-role", choices=KEYFRAME_ROLES, help="Video keyframe role.")
    annotate_panel.add_argument("--duration-sec", type=float, help="Planned shot duration in seconds.")
    annotate_panel.add_argument("--camera-move", help="Camera move such as static, push-in, orbit, or track-left.")
    annotate_panel.add_argument("--transition-to-next", help="Transition such as cut, dissolve, whip, or match-cut.")
    annotate_panel.add_argument("--motion-strength", choices=MOTION_STRENGTH_LEVELS, help="Relative motion strength.")
    annotate_panel.add_argument("--loop-safe", choices=("true", "false"), help="Whether this panel is loop-safe.")
    annotate_panel.add_argument("--shot-note", help="Optional production note for the panel.")
    annotate_panel.add_argument("--source-panel", help="Original source panel or beat id, such as V2#03 or beat-03.")
    annotate_panel.add_argument("--text-source", help="Source text or script beat this panel adapts, such as 原文第3句.")
    annotate_panel.add_argument("--source-visual", help="Original visual/caption text this panel must preserve.")
    annotate_panel.add_argument("--story-beat", help="Concise narrative information point advanced by this panel.")
    annotate_panel.add_argument("--story-text", help="Prior story/script text that this shot must visualize.")
    annotate_panel.add_argument("--subtitle", help="Exact subtitle line for post-production.")
    annotate_panel.add_argument("--voiceover", help="Exact voiceover or spoken line for post-production.")
    annotate_panel.add_argument("--subtitle-voiceover", help="Exact subtitle or voiceover line for post-production.")
    annotate_panel.add_argument("--sound-design", help="Sound, ambience, or music cue paired with this panel.")
    annotate_panel.add_argument("--binding-status", help="Text binding status such as source, derived, override, or generated/original.")

    render = subparsers.add_parser("render-sheet", help="Render a contact sheet PNG from a JSON spec.")
    render.add_argument("--spec", required=True, type=Path, help="Input JSON spec path.")
    render.add_argument("--out", required=True, type=Path, help="Output image path.")

    export = subparsers.add_parser(
        "export-markdown",
        help="Export the storyboard as a markdown shot list.",
    )
    export.add_argument("--spec", required=True, type=Path, help="Input JSON spec path.")
    export.add_argument("--out", required=True, type=Path, help="Output markdown path.")

    export_prompts = subparsers.add_parser(
        "export-prompts",
        help="Export per-panel prompts, grouped prompts, and machine-readable prompt packs.",
    )
    export_prompts.add_argument("--spec", required=True, type=Path, help="Input JSON spec path.")
    export_prompts.add_argument("--out-dir", required=True, type=Path, help="Output directory.")
    export_prompts.add_argument("--group-size", type=int, default=5, help="Panels per group prompt. Defaults to 5.")

    scan_domestic = subparsers.add_parser(
        "scan-domestic-safety",
        help="Scan domestic video prompt bodies for sensitive terms and negative-prompt markers.",
    )
    scan_domestic.add_argument(
        "--path",
        action="append",
        required=True,
        type=Path,
        help="File or directory to scan. Repeatable.",
    )
    scan_domestic.add_argument(
        "--lexicon",
        type=Path,
        default=DEFAULT_DOMESTIC_SAFE_LEXICON,
        help="Domestic safety lexicon JSON. Defaults to the bundled heuristic lexicon.",
    )
    scan_domestic.add_argument(
        "--exclude-name",
        action="append",
        default=None,
        help="File name to skip, such as README.md. Repeatable.",
    )
    scan_domestic.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")

    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates: list[str] = []
    if bold:
        candidates.extend(
            [
                "C:/Windows/Fonts/msyhbd.ttc",
                "C:/Windows/Fonts/simhei.ttf",
                "C:/Windows/Fonts/segoeuib.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
            ]
        )
    candidates.extend(
        [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
    )
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def is_cjk(char: str) -> bool:
    code = ord(char)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0x3040 <= code <= 0x30FF
        or 0xAC00 <= code <= 0xD7AF
        or 0xF900 <= code <= 0xFAFF
    )


def contains_cjk(text: str) -> bool:
    return any(is_cjk(char) for char in text)


def wrap_segment_by_char(
    draw: ImageDraw.ImageDraw,
    segment: str,
    font: ImageFont.ImageFont,
    width: int,
) -> list[str]:
    if not segment:
        return []

    lines: list[str] = []
    current = ""
    for char in segment:
        trial = f"{current}{char}"
        if current and draw.textbbox((0, 0), trial, font=font)[2] > width:
            lines.append(current)
            current = char
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    if not text.strip():
        return []

    lines: list[str] = []
    for paragraph in text.splitlines():
        stripped = paragraph.strip()
        if not stripped:
            lines.append("")
            continue

        if contains_cjk(stripped) or " " not in stripped:
            lines.extend(wrap_segment_by_char(draw, stripped, font, width))
            continue

        words = stripped.split()
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if draw.textbbox((0, 0), trial, font=font)[2] <= width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)

    return lines


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def split_brief_segments(text: str) -> list[str]:
    return [segment.strip() for segment in BRIEF_SPLIT_RE.split(text) if segment.strip()]


def remove_terms(text: str, terms: list[str]) -> str:
    cleaned = text
    for term in terms:
        cleaned = cleaned.replace(term, "")
    return re.sub(r"\s+", " ", cleaned).strip(" ：:，,;；。. ")


def first_matching_segment(segments: list[str], keywords: list[str]) -> str | None:
    for segment in segments:
        if any(keyword in segment for keyword in keywords):
            return segment
    return None


def summarize_focus_points(points: list[str], language: str) -> str:
    if not points:
        return ""
    joined = "、".join(points) if language == "zh" else ", ".join(points)
    if language == "zh":
        return f"重点强调{joined}"
    return f"Emphasize {joined}"


def default_reference_inputs() -> dict[str, Any]:
    return {
        "global": {
            "face_anchors": [],
            "outfit_anchors": [],
            "product_anchors": [],
            "scene_anchors": [],
            "style_anchors": [],
            "generic_references": [],
            "first_frame": None,
            "last_frame": None,
        },
        "panels": {},
    }


def default_reference_scope() -> dict[str, Any]:
    return {
        "face_anchors": [],
        "outfit_anchors": [],
        "product_anchors": [],
        "scene_anchors": [],
        "style_anchors": [],
        "generic_references": [],
        "panel_note": "",
    }


def reference_defaults(role_key: str | None, role: str | None = None) -> dict[str, Any]:
    if role_key and role_key in REFERENCE_ROLE_DEFAULTS:
        return dict(REFERENCE_ROLE_DEFAULTS[role_key])
    role_text = role or ""
    if "identity" in role_text or "face" in role_text:
        return dict(REFERENCE_ROLE_DEFAULTS["face_anchors"])
    if "outfit" in role_text or "wardrobe" in role_text:
        return dict(REFERENCE_ROLE_DEFAULTS["outfit_anchors"])
    if "product" in role_text or "detail" in role_text or "prop" in role_text:
        return dict(REFERENCE_ROLE_DEFAULTS["product_anchors"])
    if "scene" in role_text:
        return dict(REFERENCE_ROLE_DEFAULTS["scene_anchors"])
    if "style" in role_text:
        return dict(REFERENCE_ROLE_DEFAULTS["style_anchors"])
    if "first-frame" in role_text:
        return dict(REFERENCE_ROLE_DEFAULTS["first_frame"])
    if "last-frame" in role_text:
        return dict(REFERENCE_ROLE_DEFAULTS["last_frame"])
    return dict(REFERENCE_ROLE_DEFAULTS["generic_references"])


def clamp_weight(value: Any, fallback: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return fallback


def normalize_priority(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def reference_rank(item: dict[str, Any]) -> tuple[int, float]:
    return (
        normalize_priority(item.get("priority"), 0),
        clamp_weight(item.get("weight"), 0.0),
    )


def normalize_reference_entry(item: Any, role_key: str | None = None) -> dict[str, Any] | None:
    if isinstance(item, dict) and item.get("path"):
        role = str(item.get("role", ""))
        defaults = reference_defaults(role_key, role)
        return {
            "path": str(item["path"]),
            "role": role,
            "name": str(item.get("name", Path(str(item["path"])).name)),
            "weight": clamp_weight(item.get("weight"), defaults["weight"]),
            "priority": normalize_priority(item.get("priority"), defaults["priority"]),
            "crop": str(item.get("crop") or defaults["crop"]),
            "focus": str(item.get("focus") or defaults["focus"]),
            "lock": str(item.get("lock") or defaults["lock"]),
        }
    return None


def normalize_reference_list(items: Any, role_key: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    normalized = [entry for entry in (normalize_reference_entry(item, role_key) for item in items) if entry]
    return merge_asset_entries([], normalized)


def normalize_reference_scope(scope: Any) -> dict[str, Any]:
    normalized = default_reference_scope()
    if not isinstance(scope, dict):
        return normalized
    for key in ("face_anchors", "outfit_anchors", "product_anchors", "scene_anchors", "style_anchors", "generic_references"):
        normalized[key] = normalize_reference_list(scope.get(key, []), key)
    normalized["panel_note"] = str(scope.get("panel_note", "")).strip()
    return normalized


def ensure_reference_inputs(spec: dict[str, Any]) -> dict[str, Any]:
    existing = spec.get("reference_inputs")
    normalized = default_reference_inputs()
    if isinstance(existing, dict):
        if isinstance(existing.get("global"), dict) or isinstance(existing.get("panels"), dict):
            normalized["global"] = normalize_reference_scope(existing.get("global", {}))
            if isinstance(existing.get("global", {}).get("first_frame"), dict) or existing.get("global", {}).get("first_frame") is None:
                normalized["global"]["first_frame"] = normalize_reference_entry(existing.get("global", {}).get("first_frame"), "first_frame") if existing.get("global", {}).get("first_frame") else None
            if isinstance(existing.get("global", {}).get("last_frame"), dict) or existing.get("global", {}).get("last_frame") is None:
                normalized["global"]["last_frame"] = normalize_reference_entry(existing.get("global", {}).get("last_frame"), "last_frame") if existing.get("global", {}).get("last_frame") else None
            if isinstance(existing.get("panels"), dict):
                normalized["panels"] = {
                    str(panel_key): normalize_reference_scope(panel_scope)
                    for panel_key, panel_scope in existing["panels"].items()
                }
        else:
            normalized["global"]["face_anchors"] = normalize_reference_list(existing.get("protagonist_images", []), "face_anchors")
            normalized["global"]["generic_references"] = normalize_reference_list(existing.get("reference_images", []), "generic_references")
            first_frame = existing.get("first_frame")
            last_frame = existing.get("last_frame")
            normalized["global"]["first_frame"] = normalize_reference_entry(first_frame, "first_frame") if isinstance(first_frame, dict) else None
            normalized["global"]["last_frame"] = normalize_reference_entry(last_frame, "last_frame") if isinstance(last_frame, dict) else None
    spec["reference_inputs"] = normalized
    return normalized


def default_video_handoff(index: int, total: int, profile_id: str) -> dict[str, Any]:
    keyframe_role = "middle"
    if index == 1:
        keyframe_role = "start"
    elif index == total:
        keyframe_role = "end"
    elif profile_id == "start-end-9":
        keyframe_role = "bridge"

    loop_safe = bool(profile_id == "dance-25" and index == total)
    if profile_id == "commerce-fashion-25":
        duration = 1.0
    elif profile_id == "dance-25":
        duration = 0.8
    elif profile_id == "dreamy-25":
        duration = 1.6
    elif profile_id == "xianxia-fantasy-25":
        duration = 1.8
    else:
        duration = 1.2

    return {
        "keyframe_role": keyframe_role,
        "duration_sec": duration,
        "camera_move": "static",
        "transition_to_next": "cut",
        "motion_strength": "medium",
        "loop_safe": loop_safe,
        "shot_note": "",
    }


def normalize_panel_text(value: Any) -> str:
    return str(value or "").strip()


def build_panel_text_lock(panel: dict[str, Any], language: str) -> str:
    source_panel = normalize_panel_text(panel.get("source_panel"))
    text_source = normalize_panel_text(panel.get("text_source"))
    source_visual = normalize_panel_text(panel.get("source_visual"))
    story_beat = normalize_panel_text(panel.get("story_beat"))
    story_text = normalize_panel_text(panel.get("story_text"))
    subtitle = normalize_panel_text(panel.get("subtitle"))
    voiceover = normalize_panel_text(panel.get("voiceover"))
    subtitle_voiceover = normalize_panel_text(panel.get("subtitle_voiceover"))
    sound_design = normalize_panel_text(panel.get("sound_design"))
    binding_status = normalize_panel_text(panel.get("binding_status"))
    story_text_for_prompt = story_text
    if story_text_for_prompt and story_text_for_prompt in {source_visual, story_beat}:
        story_text_for_prompt = ""
    subtitle_voiceover_for_prompt = subtitle_voiceover
    if subtitle_voiceover_for_prompt and (subtitle or voiceover):
        subtitle_voiceover_for_prompt = ""
    text_fields = (
        source_panel,
        text_source,
        source_visual,
        story_beat,
        story_text_for_prompt,
        subtitle,
        voiceover,
        subtitle_voiceover_for_prompt,
        sound_design,
        binding_status,
    )
    if not any(text_fields):
        return ""

    if language == "zh":
        parts: list[str] = []
        if source_panel:
            parts.append(f"来源格：{source_panel}")
        if text_source:
            parts.append(f"文本来源：{text_source}")
        if source_visual:
            parts.append(f"原始画面文字：{source_visual}")
        if story_beat:
            parts.append(f"剧情节拍：{story_beat}")
        if story_text_for_prompt:
            parts.append(f"剧情承接：{story_text_for_prompt}")
        if subtitle:
            parts.append(f"字幕（后期叠加，画面保持无文字干净帧）：{subtitle}")
        if voiceover:
            parts.append(f"旁白/口播：{voiceover}")
        if subtitle_voiceover_for_prompt:
            parts.append(f"字幕/旁白（后期叠加，画面保持无文字干净帧）：{subtitle_voiceover_for_prompt}")
        if sound_design:
            parts.append(f"声音氛围：{sound_design}")
        if binding_status:
            parts.append(f"绑定状态：{binding_status}")
        return " ".join(parts)

    parts = []
    if source_panel:
        parts.append(f"Source panel: {source_panel}.")
    if text_source:
        parts.append(f"Text source: {text_source}.")
    if source_visual:
        parts.append(f"Source visual text: {source_visual}.")
    if story_beat:
        parts.append(f"Story beat: {story_beat}.")
    if story_text_for_prompt:
        parts.append(f"Story text: {story_text_for_prompt}.")
    if subtitle:
        parts.append(f"Subtitle for post-production; keep the generated image frame text-free: {subtitle}.")
    if voiceover:
        parts.append(f"Voiceover: {voiceover}.")
    if subtitle_voiceover_for_prompt:
        parts.append(
            "Subtitle/voiceover for post-production; "
            f"keep the generated image frame text-free: {subtitle_voiceover_for_prompt}."
        )
    if sound_design:
        parts.append(f"Sound atmosphere: {sound_design}.")
    if binding_status:
        parts.append(f"Binding status: {binding_status}.")
    return " ".join(parts)


def ensure_panel_schema(spec: dict[str, Any]) -> None:
    profile_id = infer_profile_from_spec(spec)
    panels = spec.get("panels", [])
    total = len(panels)
    for index, panel in enumerate(panels, start=1):
        if "shot_target" not in panel:
            base_prompt = str(panel.get("prompt", "")).strip()
            if "镜头目标：" in base_prompt:
                base_prompt = base_prompt.split("镜头目标：", 1)[1].strip()
            elif "Shot target:" in base_prompt:
                base_prompt = base_prompt.split("Shot target:", 1)[1].strip()
            panel["shot_target"] = base_prompt
        for field in PANEL_TEXT_FIELDS:
            panel[field] = normalize_panel_text(panel.get(field))
        existing = panel.get("video_handoff")
        defaults = default_video_handoff(index, total, profile_id)
        merged = defaults.copy()
        if isinstance(existing, dict):
            merged.update({key: existing[key] for key in defaults if key in existing and existing[key] not in (None, "")})
        panel["video_handoff"] = merged


def ensure_color(value: str | None, fallback: str) -> str:
    return value or fallback


def fit_image(path: Path, size: tuple[int, int]) -> Image.Image | None:
    if not path.exists():
        return None
    with Image.open(path) as image:
        source = image.convert("RGB")
        return ImageOps.fit(source, size, method=Image.Resampling.LANCZOS)


def render_placeholder(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    caption: str,
    prompt: str,
    fonts: dict[str, ImageFont.ImageFont],
    colors: dict[str, str],
) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=24, fill=colors["placeholder_fill"])
    placeholder_text = prompt.strip() or caption.strip() or label.strip()
    if "镜头目标：" in placeholder_text:
        placeholder_text = placeholder_text.split("镜头目标：", 1)[1].strip()
    elif "Shot target:" in placeholder_text:
        placeholder_text = placeholder_text.split("Shot target:", 1)[1].strip()
    lines = wrap_text(draw, placeholder_text, fonts["body"], x1 - x0 - 48)[:8]
    block = "\n".join(lines) if lines else "Image pending"
    draw.multiline_text(
        (x0 + 24, y0 + 78),
        block,
        font=fonts["body"],
        fill=colors["placeholder_text"],
        spacing=6,
    )


def render_panel(
    sheet: Image.Image,
    draw: ImageDraw.ImageDraw,
    panel: dict[str, Any],
    index: int,
    box: tuple[int, int, int, int],
    fonts: dict[str, ImageFont.ImageFont],
    colors: dict[str, str],
) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=28, fill=colors["panel_fill"], outline=colors["panel_border"], width=3)

    caption_height = max(112, int((y1 - y0) * 0.28))
    inner_margin = 18
    image_box = (x0 + inner_margin, y0 + inner_margin, x1 - inner_margin, y1 - caption_height)
    caption_box = (x0 + inner_margin, y1 - caption_height + 8, x1 - inner_margin, y1 - inner_margin)

    image_path_value = panel.get("image", "")
    image_path = Path(image_path_value) if image_path_value else None
    frame_image = fit_image(image_path, (image_box[2] - image_box[0], image_box[3] - image_box[1])) if image_path else None

    if frame_image is not None:
        sheet.paste(frame_image, image_box)
    else:
        render_placeholder(
            draw,
            image_box,
            str(panel.get("label", f"Panel {index}")),
            str(panel.get("caption", "")),
            str(panel.get("prompt", "")),
            fonts,
            colors,
        )

    chip_w = 96
    chip_h = 42
    chip_box = (x0 + 18, y0 + 18, x0 + 18 + chip_w, y0 + 18 + chip_h)
    draw.rounded_rectangle(chip_box, radius=16, fill=colors["chip_fill"])
    draw.text((chip_box[0] + 18, chip_box[1] + 9), f"{index:02d}", font=fonts["chip"], fill=colors["chip_text"])

    label = str(panel.get("label", f"Panel {index}"))
    caption = str(panel.get("caption", ""))
    draw.text((caption_box[0], caption_box[1]), label, font=fonts["label"], fill=colors["label_text"])

    body_width = caption_box[2] - caption_box[0]
    wrapped = wrap_text(draw, caption, fonts["body"], body_width)
    if wrapped:
        draw.multiline_text(
            (caption_box[0], caption_box[1] + 34),
            "\n".join(wrapped[:4]),
            font=fonts["body"],
            fill=colors["body_text"],
            spacing=5,
        )


def render_sheet(spec_path: Path, out_path: Path) -> None:
    spec = load_json(spec_path)
    ensure_reference_inputs(spec)
    ensure_panel_schema(spec)
    canvas = spec.get("canvas", {})
    grid = spec.get("grid", {})
    theme = spec.get("theme", {})

    width = int(canvas.get("width", 2400))
    height = int(canvas.get("height", 3200))
    background = ensure_color(canvas.get("background"), "#f4efe7")
    title = str(spec.get("title", "Storyboard")).strip()
    subtitle = str(spec.get("subtitle", "")).strip()
    columns = int(grid.get("columns", 5))
    rows = int(grid.get("rows", 5))
    margin = int(grid.get("margin", 72))
    gap = int(grid.get("gap", 28))
    header_height = int(spec.get("header_height", 190))

    colors = {
        "panel_fill": ensure_color(theme.get("panel_fill"), "#fffaf2"),
        "panel_border": ensure_color(theme.get("panel_border"), "#2c241d"),
        "placeholder_fill": ensure_color(theme.get("placeholder_fill"), "#eadfcf"),
        "placeholder_text": ensure_color(theme.get("placeholder_text"), "#55483b"),
        "chip_fill": ensure_color(theme.get("chip_fill"), "#201a14"),
        "chip_text": ensure_color(theme.get("chip_text"), "#fff9f1"),
        "label_text": ensure_color(theme.get("label_text"), "#201a14"),
        "body_text": ensure_color(theme.get("body_text"), "#51463a"),
        "title_text": ensure_color(theme.get("title_text"), "#1a1612"),
        "subtitle_text": ensure_color(theme.get("subtitle_text"), "#6b5e52"),
    }
    fonts = {
        "title": load_font(int(spec.get("title_font_size", 56)), bold=True),
        "subtitle": load_font(int(spec.get("subtitle_font_size", 26))),
        "chip": load_font(22, bold=True),
        "label": load_font(int(spec.get("label_font_size", 24)), bold=True),
        "body": load_font(int(spec.get("caption_font_size", 20))),
    }

    sheet = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(sheet)

    draw.text((margin, 42), title, font=fonts["title"], fill=colors["title_text"])
    if subtitle:
        draw.text((margin, 114), subtitle, font=fonts["subtitle"], fill=colors["subtitle_text"])

    panel_width = int((width - (margin * 2) - (gap * (columns - 1))) / columns)
    panel_height = int((height - header_height - margin - (gap * (rows - 1))) / rows)

    panels = spec.get("panels", [])
    for idx, panel in enumerate(panels[: columns * rows], start=1):
        col = (idx - 1) % columns
        row = (idx - 1) // columns
        x0 = margin + col * (panel_width + gap)
        y0 = header_height + row * (panel_height + gap)
        x1 = x0 + panel_width
        y1 = y0 + panel_height
        render_panel(sheet, draw, panel, idx, (x0, y0, x1, y1), fonts, colors)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def detect_language(explicit: str | None, *values: str) -> str:
    if explicit:
        return explicit
    text = " ".join(value for value in values if value)
    return "zh" if contains_cjk(text) else "en"


def infer_profile_from_spec(spec: dict[str, Any]) -> str:
    profile_id = str(spec.get("profile_id", "")).strip()
    if profile_id in PROFILE_VARIANTS:
        return profile_id

    title = str(spec.get("title", ""))
    if "舞" in title or "dance" in title.lower():
        return "dance-25"
    if any(keyword in title for keyword in ("玄幻", "仙侠", "国风", "神话")) or "xianxia" in title.lower():
        return "xianxia-fantasy-25"
    if "梦" in title or "dream" in title.lower():
        return "dreamy-25"
    if "首尾" in title or "start" in title.lower():
        return "start-end-9"
    return "commerce-fashion-25"


def find_first_keyword(text: str, keywords: list[str]) -> str | None:
    for keyword in keywords:
        if keyword in text:
            return keyword
    return None


def infer_platform(brief: str, language: str) -> str:
    lowered = brief.lower()
    if "tiktok" in lowered:
        return "TikTok"
    if "douyin" in lowered or "抖音" in brief:
        return "Douyin" if language == "en" else "抖音"
    if "reels" in lowered:
        return "Reels"
    if "小红书" in brief:
        return "Xiaohongshu" if language == "en" else "小红书"
    return "短视频" if language == "zh" else "short-video"


def clean_subject_segment(segment: str) -> str:
    cleaned = remove_terms(segment, ["主角是", "人设是", "角色是", "镜头里是", "博主是"])
    action_positions = [cleaned.find(action) for action in ACTION_KEYWORDS_ZH if cleaned.find(action) > 0]
    if action_positions:
        cleaned = cleaned[: min(action_positions)]
    cleaned = cleaned.strip(" ：:，,;；。. ")
    return cleaned or segment.strip()


def clean_product_segment(segment: str) -> str:
    cleaned = remove_terms(segment, NOISE_TERMS_ZH + list(PLATFORM_KEYWORDS.keys()))
    cleaned = remove_terms(cleaned, ["重点突出", "重点", "主打", "适合", "做成", "想要"])
    return cleaned or segment.strip()


def clean_scene_segment(segment: str) -> str:
    cleaned = remove_terms(segment, ["场景在", "场景是", "背景是", "背景在", "空间是", "环境是"])
    return cleaned or segment.strip()


def clean_mood_segment(segment: str) -> str:
    cleaned = remove_terms(segment, ["短视频", "视频"] + NOISE_TERMS_ZH)
    cleaned = remove_terms(cleaned, ["重点突出", "重点", "风格", "氛围", "感觉", "整体", "主打"])
    if cleaned.endswith("短"):
        cleaned = cleaned[:-1]
    return cleaned or segment.strip()


def infer_subject(profile_id: str, brief: str, language: str) -> str:
    if language == "zh":
        segments = split_brief_segments(brief)
        matched = first_matching_segment(segments, SUBJECT_KEYWORDS_ZH)
        if matched:
            return clean_subject_segment(matched)
        if profile_id == "commerce-fashion-25":
            if "姐姐" in brief:
                return "温柔姐姐系女主播"
            if "主播" in brief:
                return "带货女主播"
        if profile_id == "dance-25" and ("舞" in brief or "跳" in brief):
            return "女舞者" if "女" in brief or "女生" in brief else "舞者"
        return DEFAULT_CONTEXT[profile_id][language]["subject"]
    return DEFAULT_CONTEXT[profile_id][language]["subject"]


def infer_product(profile_id: str, brief: str, language: str) -> str:
    if profile_id == "commerce-fashion-25":
        if language == "zh":
            segments = split_brief_segments(brief)
            candidates = [
                clean_product_segment(segment)
                for segment in segments
                if any(keyword in segment for keyword in PRODUCT_KEYWORDS_ZH)
            ]
            candidates = unique_preserve_order(candidates)
            return max(candidates, key=len) if candidates else "服装单品"
        return (
            find_first_keyword(
                brief.lower(),
                ["knit dress", "dress", "jacket", "blazer", "shirt", "hoodie", "coat", "skirt", "pants"],
            )
            or "fashion item"
        )
    if profile_id == "dance-25":
        return "舞蹈服装" if language == "zh" else "dance outfit"
    if profile_id == "dreamy-25":
        return "主视觉服装" if language == "zh" else "hero costume"
    if profile_id == "xianxia-fantasy-25":
        return "仙侠服装、法器与随身道具" if language == "zh" else "immortal costume, weapon, and magic props"
    return "服装与道具" if language == "zh" else "outfit and props"


def infer_scene(profile_id: str, brief: str, language: str) -> str:
    if language == "zh":
        segments = split_brief_segments(brief)
        matched_segment = first_matching_segment(segments, SCENE_KEYWORDS_ZH)
        matched = clean_scene_segment(matched_segment) if matched_segment else None
        if matched:
            return matched
    else:
        matched = find_first_keyword(
            brief.lower(),
            [
                "livestream studio",
                "dance studio",
                "stage",
                "rooftop",
                "street",
                "mirror hall",
                "fitting room",
                "xianxia palace",
                "immortal palace",
                "cloud sea",
                "mountain gate",
                "ancient temple",
                "giant sacred tree",
            ],
        )
        if matched:
            return matched
    return DEFAULT_CONTEXT[profile_id][language]["scene"]


def infer_mood(profile_id: str, brief: str, language: str) -> str:
    if language == "zh":
        segments = split_brief_segments(brief)
        candidates = [
            clean_mood_segment(segment)
            for segment in segments
            if any(keyword in segment for keyword in MOOD_KEYWORDS_ZH)
            and not any(keyword in segment for keyword in SUBJECT_KEYWORDS_ZH + PRODUCT_KEYWORDS_ZH + SCENE_KEYWORDS_ZH)
        ]
        candidates = unique_preserve_order(candidates)
        if candidates:
            return "、".join(candidates[:2])
    return DEFAULT_CONTEXT[profile_id][language]["mood"]


def infer_focus_points(profile_id: str, brief: str, language: str) -> list[str]:
    if language != "zh":
        return []
    points = [keyword for keyword in FOCUS_POINT_KEYWORDS_ZH if keyword in brief]
    if profile_id == "dance-25":
        points.extend(keyword for keyword in ACTION_KEYWORDS_ZH if keyword in brief)
    points = unique_preserve_order(points)
    filtered: list[str] = []
    for point in points:
        if any(point != other and point in other for other in points):
            continue
        filtered.append(point)
    return filtered


def infer_action_goal(profile_id: str, brief: str, language: str) -> str:
    if language != "zh":
        return ""
    if profile_id not in {"dance-25", "start-end-9", "xianxia-fantasy-25"}:
        return ""
    segments = split_brief_segments(brief)
    candidates = [
        segment
        for segment in segments
        if any(keyword in segment for keyword in ACTION_KEYWORDS_ZH)
    ]
    candidates = unique_preserve_order(candidates)
    return candidates[0] if candidates else ""


def infer_context(
    profile_id: str,
    brief: str,
    language: str,
    subject: str | None,
    product: str | None,
    scene: str | None,
    mood: str | None,
    platform: str | None,
    aspect: str | None,
) -> dict[str, Any]:
    context = dict(DEFAULT_CONTEXT[profile_id][language])
    context["brief"] = brief.strip()
    context["subject"] = subject or infer_subject(profile_id, brief, language)
    context["product"] = product or infer_product(profile_id, brief, language)
    context["scene"] = scene or infer_scene(profile_id, brief, language)
    context["mood"] = mood or infer_mood(profile_id, brief, language)
    context["platform"] = platform or infer_platform(brief, language)
    context["aspect"] = aspect or context["aspect"]
    context["focus_points"] = infer_focus_points(profile_id, brief, language)
    context["action_goal"] = infer_action_goal(profile_id, brief, language)
    context["parsed_segments"] = split_brief_segments(brief)
    return context


def build_global_lock(profile_id: str, context: dict[str, Any], language: str) -> str:
    focus_clause = summarize_focus_points(context.get("focus_points", []), language)
    action_goal = str(context.get("action_goal", "")).strip()
    if language == "zh":
        action_clause = f"动作目标{action_goal}；" if action_goal else ""
        focus_text = f"{focus_clause}；" if focus_clause else ""
        return (
            f"统一设定：同一位主角为{context['subject']}；同一核心对象为{context['product']}；"
            f"同一环境为{context['scene']}；平台为{context['platform']}；画幅为{context['aspect']}；"
            f"整体气质{context['mood']}；{focus_text}{action_clause}保持人脸、发型、服装廓形、颜色和场景连续一致。"
        )
    focus_text = f"{focus_clause}. " if focus_clause else ""
    action_clause = f"Action goal: {action_goal}. " if action_goal else ""
    return (
        f"Global lock: the same protagonist is {context['subject']}; the same core product or outfit is "
        f"{context['product']}; the same environment is {context['scene']}; platform intent is {context['platform']}; "
        f"aspect is {context['aspect']}; overall tone is {context['mood']}; {focus_text}{action_clause}preserve face, hair, outfit silhouette, "
        f"colors, and environment continuity across all panels."
    )


def build_title(profile_id: str, context: dict[str, Any], language: str) -> str:
    suffix = PROFILE_TITLE_SUFFIX[profile_id][language]
    if language == "zh":
        headline = context["scene"] if profile_id == "xianxia-fantasy-25" else context["product"]
        return f"{headline}{suffix}"
    headline_source = context["scene"] if profile_id == "xianxia-fantasy-25" else context["product"]
    headline = headline_source.title()
    return f"{headline} {suffix}"


def build_subtitle(profile_id: str, context: dict[str, Any], language: str) -> str:
    panel_count = "9格" if profile_id == "start-end-9" and language == "zh" else "25格" if language == "zh" else "9-panel" if profile_id == "start-end-9" else "25-panel"
    if language == "zh":
        return f"{context['platform']} · {panel_count} · {context['scene']} · {context['mood']}"
    return f"{context['platform']} · {panel_count} · {context['scene']} · {context['mood']}"


def load_profile_template(profile: str, language: str) -> dict[str, Any]:
    template_path = PROFILE_VARIANTS[profile][language]
    payload = load_json(template_path)
    payload["profile_id"] = profile
    payload["language"] = language
    ensure_reference_inputs(payload)
    ensure_panel_schema(payload)
    return payload


def new_spec(profile: str, language: str, out_path: Path, title: str | None, subtitle: str | None) -> None:
    payload = load_profile_template(profile, language)
    if title:
        payload["title"] = title
    if subtitle:
        payload["subtitle"] = subtitle
    save_json(out_path, payload)


def validate_existing_image_paths(paths: list[str]) -> list[str]:
    resolved: list[str] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"Reference image not found: {path}")
        resolved.append(str(path))
    return resolved


def asset_entry(
    path: str,
    role: str,
    role_key: str | None = None,
    weight: float | None = None,
    priority: int | None = None,
    crop: str | None = None,
    focus: str | None = None,
    lock: str | None = None,
) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    defaults = reference_defaults(role_key, role)
    return {
        "path": str(resolved),
        "role": role,
        "name": resolved.name,
        "weight": clamp_weight(weight, defaults["weight"]),
        "priority": normalize_priority(priority, defaults["priority"]),
        "crop": crop or defaults["crop"],
        "focus": focus or defaults["focus"],
        "lock": lock or defaults["lock"],
    }


def merge_reference_scope(base_scope: dict[str, Any], overlay_scope: dict[str, Any]) -> dict[str, Any]:
    merged = default_reference_scope()
    for key in ("face_anchors", "outfit_anchors", "product_anchors", "scene_anchors", "style_anchors", "generic_references"):
        merged[key] = merge_asset_entries(
            list(base_scope.get(key, [])) if isinstance(base_scope.get(key), list) else [],
            list(overlay_scope.get(key, [])) if isinstance(overlay_scope.get(key), list) else [],
        )
    merged["panel_note"] = str(overlay_scope.get("panel_note") or base_scope.get("panel_note") or "").strip()
    return merged


def get_panel_reference_scope(reference_inputs: dict[str, Any], panel_index: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    global_scope = normalize_reference_scope(reference_inputs.get("global", {}))
    panel_scope = normalize_reference_scope(reference_inputs.get("panels", {}).get(str(panel_index), {}))
    combined_scope = merge_reference_scope(global_scope, panel_scope)
    return global_scope, panel_scope, combined_scope


def describe_reference_scope(scope: dict[str, Any], language: str, prefix: str | None = None) -> str:
    parts: list[str] = []
    for key, labels in REFERENCE_ROLE_LABELS.items():
        count = len(scope.get(key, [])) if isinstance(scope.get(key), list) else 0
        if not count:
            continue
        entries = sorted(scope.get(key, []), key=reference_rank, reverse=True)
        top = entries[0] if entries else {}
        if language == "zh":
            parts.append(f"{labels['zh']}{count}张(最高P{top.get('priority')}/W{top.get('weight')})")
        else:
            parts.append(f"{count} {labels['en']} (top P{top.get('priority')}/W{top.get('weight')})")

    if scope.get("panel_note"):
        if language == "zh":
            parts.append(f"说明：{scope['panel_note']}")
        else:
            parts.append(f"note: {scope['panel_note']}")

    if not parts:
        return ""
    if language == "zh":
        lead = prefix or "参考输入"
        return f"{lead}：{'；'.join(parts)}"
    lead = prefix or "Reference inputs"
    return f"{lead}: {'; '.join(parts)}"


def describe_reference_strategy(scope: dict[str, Any], language: str) -> str:
    strategy_parts: list[str] = []
    for key, labels in REFERENCE_ROLE_LABELS.items():
        entries = scope.get(key, [])
        if not isinstance(entries, list) or not entries:
            continue
        top = sorted(entries, key=reference_rank, reverse=True)[0]
        label = labels["zh"] if language == "zh" else labels["en"]
        if language == "zh":
            strategy_parts.append(
                f"{label}: P{top.get('priority')}, W{top.get('weight')}, 裁剪={top.get('crop')}, 关注={top.get('focus')}, 锁定={top.get('lock')}"
            )
        else:
            strategy_parts.append(
                f"{label}: P{top.get('priority')}, W{top.get('weight')}, crop={top.get('crop')}, focus={top.get('focus')}, lock={top.get('lock')}"
            )
    if not strategy_parts:
        return ""
    if language == "zh":
        return f"参考权重与裁剪策略：{'；'.join(strategy_parts)}。{REFERENCE_CONFLICT_POLICY['zh']}"
    return f"Reference weight and crop strategy: {'; '.join(strategy_parts)}. {REFERENCE_CONFLICT_POLICY['en']}"


def build_reference_lock(reference_inputs: dict[str, Any], language: str, panel_index: int | None = None) -> str:
    global_scope = normalize_reference_scope(reference_inputs.get("global", {}))
    has_first = isinstance(reference_inputs.get("global", {}).get("first_frame"), dict)
    has_last = isinstance(reference_inputs.get("global", {}).get("last_frame"), dict)
    global_summary = describe_reference_scope(global_scope, language, "全局参考" if language == "zh" else "Global references")

    parts: list[str] = []
    if global_summary:
        parts.append(global_summary)
    if has_first:
        parts.append("已提供首帧" if language == "zh" else "first frame locked")
    if has_last:
        parts.append("已提供尾帧" if language == "zh" else "last frame locked")

    if panel_index is not None:
        _, panel_scope, combined_scope = get_panel_reference_scope(reference_inputs, panel_index)
        panel_summary = describe_reference_scope(panel_scope, language, "本格覆盖参考" if language == "zh" else "Panel-specific overrides")
        if panel_summary:
            parts.append(panel_summary)
        strategy = describe_reference_strategy(combined_scope, language)
        if strategy:
            parts.append(strategy)
    else:
        strategy = describe_reference_strategy(global_scope, language)
        if strategy:
            parts.append(strategy)

    if not parts:
        return ""
    if language == "zh":
        return f"参考输入：{'；'.join(parts)}；优先遵循参考图的人物、服装、商品和场景连续性。"
    return f"Reference inputs: {'; '.join(parts)}; prioritize continuity from the attached identity, outfit, product, and scene anchors."


def compose_panel_prompt(
    shot_target: str,
    brief_context: dict[str, Any],
    reference_inputs: dict[str, Any],
    language: str,
    panel_index: int,
    text_lock: str = "",
) -> str:
    global_lock = str(brief_context.get("global_lock", "")).strip()
    reference_lock = build_reference_lock(reference_inputs, language, panel_index=panel_index)
    if language == "zh":
        parts = [part for part in [global_lock, reference_lock, text_lock, f"镜头目标：{shot_target}"] if part]
    else:
        parts = [part for part in [global_lock, reference_lock, text_lock, f"Shot target: {shot_target}"] if part]
    return " ".join(parts)


def refresh_prompts_from_context(spec: dict[str, Any]) -> None:
    language = detect_language(spec.get("language"), str(spec.get("title", "")), str(spec.get("subtitle", "")))
    brief_context = spec.get("brief_context")
    reference_inputs = ensure_reference_inputs(spec)
    ensure_panel_schema(spec)
    if not isinstance(brief_context, dict):
        brief_context = {}
    else:
        brief_context["reference_summary"] = build_reference_lock(reference_inputs, language)
    for index, panel in enumerate(spec.get("panels", []), start=1):
        shot_target = str(panel.get("shot_target") or panel.get("prompt") or "").strip()
        if "镜头目标：" in shot_target:
            shot_target = shot_target.split("镜头目标：", 1)[1].strip()
        elif "Shot target:" in shot_target:
            shot_target = shot_target.split("Shot target:", 1)[1].strip()
        panel["shot_target"] = shot_target
        text_lock = build_panel_text_lock(panel, language)
        panel["prompt"] = compose_panel_prompt(shot_target, brief_context, reference_inputs, language, index, text_lock)


def apply_brief_to_spec(
    spec_path: Path,
    out_path: Path,
    brief: str,
    language: str | None,
    subject: str | None,
    product: str | None,
    scene: str | None,
    mood: str | None,
    platform: str | None,
    aspect: str | None,
    title: str | None,
    subtitle: str | None,
) -> None:
    spec = load_json(spec_path)
    ensure_reference_inputs(spec)
    ensure_panel_schema(spec)
    profile_id = infer_profile_from_spec(spec)
    resolved_language = detect_language(
        language,
        brief,
        subject or "",
        product or "",
        scene or "",
        mood or "",
        platform or "",
        str(spec.get("title", "")),
    )
    context = infer_context(profile_id, brief, resolved_language, subject, product, scene, mood, platform, aspect)
    global_lock = build_global_lock(profile_id, context, resolved_language)

    spec["profile_id"] = profile_id
    spec["language"] = resolved_language
    spec["title"] = title or build_title(profile_id, context, resolved_language)
    spec["subtitle"] = subtitle or build_subtitle(profile_id, context, resolved_language)
    spec["brief_context"] = {
        **context,
        "global_lock": global_lock,
    }
    for panel in spec.get("panels", []):
        base_prompt = str(panel.get("shot_target") or panel.get("prompt", "")).strip()
        if "镜头目标：" in base_prompt:
            base_prompt = base_prompt.split("镜头目标：", 1)[1].strip()
        elif "Shot target:" in base_prompt:
            base_prompt = base_prompt.split("Shot target:", 1)[1].strip()
        panel["shot_target"] = base_prompt
    refresh_prompts_from_context(spec)
    save_json(out_path, spec)


def inspect_brief(
    profile_id: str,
    brief: str,
    language: str | None,
    subject: str | None,
    product: str | None,
    scene: str | None,
    mood: str | None,
    platform: str | None,
    aspect: str | None,
    out_path: Path | None,
) -> None:
    resolved_language = detect_language(language, brief, subject or "", product or "", scene or "", mood or "", platform or "")
    context = infer_context(profile_id, brief, resolved_language, subject, product, scene, mood, platform, aspect)
    payload = {
        "profile_id": profile_id,
        "language": resolved_language,
        "title": build_title(profile_id, context, resolved_language),
        "subtitle": build_subtitle(profile_id, context, resolved_language),
        "reference_inputs": default_reference_inputs(),
        "brief_context": {
            **context,
            "global_lock": build_global_lock(profile_id, context, resolved_language),
        },
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def merge_asset_entries(existing: list[dict[str, Any]], additions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_path: dict[str, dict[str, Any]] = {str(item.get("path", "")): item for item in existing if isinstance(item, dict)}
    for item in additions:
        by_path[item["path"]] = item
    return list(by_path.values())


def attach_references_to_spec(
    spec_path: Path,
    out_path: Path,
    panel: int | None,
    panel_note: str | None,
    protagonist_images: list[str],
    face_anchors: list[str],
    outfit_anchors: list[str],
    product_anchors: list[str],
    scene_anchors: list[str],
    style_anchors: list[str],
    reference_images: list[str],
    first_frame: str | None,
    last_frame: str | None,
    reference_weight: float | None,
    reference_priority: int | None,
    reference_crop: str | None,
    reference_focus: str | None,
    reference_lock: str | None,
) -> None:
    spec = load_json(spec_path)
    reference_inputs = ensure_reference_inputs(spec)
    ensure_panel_schema(spec)

    if panel is not None and (panel < 1 or panel > len(spec.get("panels", []))):
        raise SystemExit(f"Panel index out of range: {panel}")

    metadata = {
        "weight": reference_weight,
        "priority": reference_priority,
        "crop": reference_crop,
        "focus": reference_focus,
        "lock": reference_lock,
    }
    protagonist_entries = [asset_entry(path, "identity-anchor", "face_anchors", **metadata) for path in validate_existing_image_paths(protagonist_images)]
    role_entries = {
        "face_anchors": protagonist_entries + [asset_entry(path, "face-anchor", "face_anchors", **metadata) for path in validate_existing_image_paths(face_anchors)],
        "outfit_anchors": [asset_entry(path, "outfit-anchor", "outfit_anchors", **metadata) for path in validate_existing_image_paths(outfit_anchors)],
        "product_anchors": [asset_entry(path, "product-anchor", "product_anchors", **metadata) for path in validate_existing_image_paths(product_anchors)],
        "scene_anchors": [asset_entry(path, "scene-anchor", "scene_anchors", **metadata) for path in validate_existing_image_paths(scene_anchors)],
        "style_anchors": [asset_entry(path, "style-anchor", "style_anchors", **metadata) for path in validate_existing_image_paths(style_anchors)],
        "generic_references": [asset_entry(path, "generic-reference", "generic_references", **metadata) for path in validate_existing_image_paths(reference_images)],
    }

    target_scope: dict[str, Any]
    if panel is None:
        target_scope = reference_inputs["global"]
    else:
        panel_key = str(panel)
        panels_scope = reference_inputs.setdefault("panels", {})
        target_scope = normalize_reference_scope(panels_scope.get(panel_key, {}))
        panels_scope[panel_key] = target_scope

    for key, entries in role_entries.items():
        target_scope[key] = merge_asset_entries(target_scope.get(key, []), entries)
    if panel_note:
        target_scope["panel_note"] = panel_note
    if first_frame:
        reference_inputs["global"]["first_frame"] = asset_entry(validate_existing_image_paths([first_frame])[0], "first-frame", "first_frame", **metadata)
    if last_frame:
        reference_inputs["global"]["last_frame"] = asset_entry(validate_existing_image_paths([last_frame])[0], "last-frame", "last_frame", **metadata)

    refresh_prompts_from_context(spec)
    save_json(out_path, spec)


def annotate_panel(
    spec_path: Path,
    out_path: Path,
    panel_index: int,
    keyframe_role: str | None,
    duration_sec: float | None,
    camera_move: str | None,
    transition_to_next: str | None,
    motion_strength: str | None,
    loop_safe: str | None,
    shot_note: str | None,
    source_panel: str | None,
    text_source: str | None,
    source_visual: str | None,
    story_beat: str | None,
    story_text: str | None,
    subtitle: str | None,
    voiceover: str | None,
    subtitle_voiceover: str | None,
    sound_design: str | None,
    binding_status: str | None,
) -> None:
    spec = load_json(spec_path)
    ensure_reference_inputs(spec)
    ensure_panel_schema(spec)
    panels = spec.get("panels", [])
    if panel_index < 1 or panel_index > len(panels):
        raise SystemExit(f"Panel index out of range: {panel_index}")

    panel = panels[panel_index - 1]
    handoff = panel.setdefault("video_handoff", default_video_handoff(panel_index, len(panels), infer_profile_from_spec(spec)))
    if keyframe_role:
        handoff["keyframe_role"] = keyframe_role
    if duration_sec is not None:
        handoff["duration_sec"] = duration_sec
    if camera_move:
        handoff["camera_move"] = camera_move
    if transition_to_next:
        handoff["transition_to_next"] = transition_to_next
    if motion_strength:
        handoff["motion_strength"] = motion_strength
    if loop_safe is not None:
        handoff["loop_safe"] = loop_safe.lower() == "true"
    if shot_note is not None:
        handoff["shot_note"] = shot_note
    if source_panel is not None:
        panel["source_panel"] = normalize_panel_text(source_panel)
    if text_source is not None:
        panel["text_source"] = normalize_panel_text(text_source)
    if source_visual is not None:
        panel["source_visual"] = normalize_panel_text(source_visual)
    if story_beat is not None:
        panel["story_beat"] = normalize_panel_text(story_beat)
    if story_text is not None:
        panel["story_text"] = normalize_panel_text(story_text)
    if subtitle is not None:
        panel["subtitle"] = normalize_panel_text(subtitle)
    if voiceover is not None:
        panel["voiceover"] = normalize_panel_text(voiceover)
    if subtitle_voiceover is not None:
        panel["subtitle_voiceover"] = normalize_panel_text(subtitle_voiceover)
    if sound_design is not None:
        panel["sound_design"] = normalize_panel_text(sound_design)
    if binding_status is not None:
        panel["binding_status"] = normalize_panel_text(binding_status)

    refresh_prompts_from_context(spec)
    save_json(out_path, spec)


def export_markdown(spec_path: Path, out_path: Path) -> None:
    spec = load_json(spec_path)
    ensure_reference_inputs(spec)
    ensure_panel_schema(spec)
    language = detect_language(spec.get("language"), str(spec.get("title", "")), str(spec.get("subtitle", "")))
    title = str(spec.get("title", "Storyboard"))
    subtitle = str(spec.get("subtitle", ""))
    lines = [f"# {title}", ""]
    if subtitle:
        lines.extend([subtitle, ""])

    context = spec.get("brief_context")
    if isinstance(context, dict):
        if language == "zh":
            lines.extend(
                [
                    "## 全局锁定",
                    "",
                    f"- Brief：{context.get('brief', '')}",
                    f"- 主角：{context.get('subject', '')}",
                    f"- 商品/服装：{context.get('product', '')}",
                    f"- 场景：{context.get('scene', '')}",
                    f"- 风格：{context.get('mood', '')}",
                    f"- 平台：{context.get('platform', '')}",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "## Global Lock",
                    "",
                    f"- Brief: {context.get('brief', '')}",
                    f"- Subject: {context.get('subject', '')}",
                    f"- Product/Outfit: {context.get('product', '')}",
                    f"- Scene: {context.get('scene', '')}",
                    f"- Mood: {context.get('mood', '')}",
                    f"- Platform: {context.get('platform', '')}",
                    "",
                ]
            )

    reference_inputs = ensure_reference_inputs(spec)
    global_scope = normalize_reference_scope(reference_inputs.get("global", {}))
    global_reference_summary = describe_reference_scope(global_scope, language, "全局参考" if language == "zh" else "Global references")
    if global_reference_summary or isinstance(reference_inputs["global"].get("first_frame"), dict) or isinstance(reference_inputs["global"].get("last_frame"), dict):
        lines.extend(["## 参考输入" if language == "zh" else "## Reference Inputs", ""])
        if global_reference_summary:
            lines.append(f"- {global_reference_summary}")
        for key in ("first_frame", "last_frame"):
            entry = reference_inputs["global"].get(key)
            if isinstance(entry, dict):
                label = "首帧" if key == "first_frame" and language == "zh" else "尾帧" if language == "zh" else "First frame" if key == "first_frame" else "Last frame"
                lines.append(f"- {label}：{entry.get('path', '')}" if language == "zh" else f"- {label}: {entry.get('path', '')}")
        lines.append("")

    panel_overrides = reference_inputs.get("panels", {})
    if isinstance(panel_overrides, dict) and panel_overrides:
        lines.extend(["## 分格参考覆盖" if language == "zh" else "## Panel Reference Overrides", ""])
        for panel_key in sorted(panel_overrides, key=lambda value: int(value)):
            summary = describe_reference_scope(normalize_reference_scope(panel_overrides[panel_key]), language, f"第{panel_key}格" if language == "zh" else f"Panel {panel_key}")
            if summary:
                lines.append(f"- {summary}")
        lines.append("")

    lines.extend(
        [
            "| # | Label | Image | Caption | Source Panel | Source Visual | Story Beat | Subtitle | Voiceover | Subtitle/VO | Sound | Binding | Shot Target | Keyframe | Duration | Camera | Transition | Motion | Loop |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for panel in spec.get("panels", []):
        handoff = panel.get("video_handoff", {})
        index = panel.get("index", "")
        label = str(panel.get("label", "")).replace("|", "/")
        image = str(panel.get("image", "")).replace("|", "/")
        caption = str(panel.get("caption", "")).replace("|", "/")
        source_panel = str(panel.get("source_panel", "") or panel.get("text_source", "")).replace("|", "/")
        source_visual = str(panel.get("source_visual", "")).replace("|", "/")
        story_beat = str(panel.get("story_beat", "") or panel.get("story_text", "")).replace("|", "/")
        subtitle = str(panel.get("subtitle", "")).replace("|", "/")
        voiceover = str(panel.get("voiceover", "")).replace("|", "/")
        subtitle_voiceover = str(panel.get("subtitle_voiceover", "")).replace("|", "/")
        sound_design = str(panel.get("sound_design", "")).replace("|", "/")
        binding_status = str(panel.get("binding_status", "")).replace("|", "/")
        shot_target = str(panel.get("shot_target", panel.get("prompt", ""))).replace("|", "/")
        lines.append(
            f"| {index} | {label} | {image} | {caption} | {source_panel} | {source_visual} | {story_beat} | {subtitle} | {voiceover} | {subtitle_voiceover} | {sound_design} | {binding_status} | {shot_target} | "
            f"{handoff.get('keyframe_role', '')} | {handoff.get('duration_sec', '')} | {handoff.get('camera_move', '')} | "
            f"{handoff.get('transition_to_next', '')} | {handoff.get('motion_strength', '')} | {handoff.get('loop_safe', '')} |"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def export_prompts(spec_path: Path, out_dir: Path, group_size: int) -> None:
    spec = load_json(spec_path)
    ensure_reference_inputs(spec)
    ensure_panel_schema(spec)
    refresh_prompts_from_context(spec)

    if group_size <= 0:
        raise SystemExit("group_size must be positive.")

    out_dir.mkdir(parents=True, exist_ok=True)
    panel_dir = out_dir / "panel-prompts"
    group_dir = out_dir / "group-prompts"
    panel_dir.mkdir(parents=True, exist_ok=True)
    group_dir.mkdir(parents=True, exist_ok=True)

    language = detect_language(spec.get("language"), str(spec.get("title", "")), str(spec.get("subtitle", "")))
    title = str(spec.get("title", "Storyboard"))
    subtitle = str(spec.get("subtitle", ""))
    context = spec.get("brief_context", {})
    reference_inputs = ensure_reference_inputs(spec)

    panel_rows: list[dict[str, Any]] = []
    for index, panel in enumerate(spec.get("panels", []), start=1):
        global_scope, panel_scope, combined_scope = get_panel_reference_scope(reference_inputs, index)
        handoff = panel.get("video_handoff", {})
        row = {
            "panel_index": index,
            "label": panel.get("label", ""),
            "image": panel.get("image", ""),
            "caption": panel.get("caption", ""),
            "source_panel": panel.get("source_panel", ""),
            "text_source": panel.get("text_source", ""),
            "source_visual": panel.get("source_visual", ""),
            "story_beat": panel.get("story_beat", ""),
            "story_text": panel.get("story_text", ""),
            "subtitle": panel.get("subtitle", ""),
            "voiceover": panel.get("voiceover", ""),
            "subtitle_voiceover": panel.get("subtitle_voiceover", ""),
            "sound_design": panel.get("sound_design", ""),
            "binding_status": panel.get("binding_status", ""),
            "shot_target": panel.get("shot_target", ""),
            "prompt": panel.get("prompt", ""),
            "video_handoff": handoff,
            "global_reference_scope": global_scope,
            "panel_reference_scope": panel_scope,
            "combined_reference_scope": combined_scope,
            "first_frame": reference_inputs["global"].get("first_frame"),
            "last_frame": reference_inputs["global"].get("last_frame"),
        }
        panel_rows.append(row)

        prompt_text_lines = [
            f"# Panel {index:02d}",
            f"Label: {row['label']}",
            f"Image: {row['image']}",
            f"Caption: {row['caption']}",
            f"Source panel: {row['source_panel']}",
            f"Text source: {row['text_source']}",
            f"Source visual: {row['source_visual']}",
            f"Story beat: {row['story_beat']}",
            f"Story text: {row['story_text']}",
            f"Subtitle: {row['subtitle']}",
            f"Voiceover: {row['voiceover']}",
            f"Subtitle/voiceover: {row['subtitle_voiceover']}",
            f"Sound design: {row['sound_design']}",
            f"Binding status: {row['binding_status']}",
            "",
            row["prompt"],
            "",
            "## Video Handoff",
            json.dumps(handoff, ensure_ascii=False, indent=2),
            "",
            "## Combined References",
            json.dumps(combined_scope, ensure_ascii=False, indent=2),
        ]
        (panel_dir / f"panel-{index:02d}.txt").write_text("\n".join(prompt_text_lines).strip() + "\n", encoding="utf-8")

    jsonl_path = out_dir / "panels.jsonl"
    jsonl_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in panel_rows),
        encoding="utf-8",
    )

    csv_headers = [
        "panel_index",
        "label",
        "image",
        "caption",
        "source_panel",
        "text_source",
        "source_visual",
        "story_beat",
        "story_text",
        "subtitle",
        "voiceover",
        "subtitle_voiceover",
        "sound_design",
        "binding_status",
        "shot_target",
        "prompt",
        "keyframe_role",
        "duration_sec",
        "camera_move",
        "transition_to_next",
        "motion_strength",
        "loop_safe",
        "face_anchor_paths",
        "outfit_anchor_paths",
        "product_anchor_paths",
        "scene_anchor_paths",
        "style_anchor_paths",
        "generic_reference_paths",
        "reference_weights",
        "reference_priorities",
        "reference_crops",
        "reference_focuses",
        "reference_locks",
        "first_frame_path",
        "last_frame_path",
        "panel_reference_note",
    ]
    csv_lines = [",".join(csv_headers)]
    for row in panel_rows:
        handoff = row["video_handoff"]
        combined_scope = row["combined_reference_scope"]
        first_frame = row["first_frame"] or {}
        last_frame = row["last_frame"] or {}
        def joined_paths(key: str) -> str:
            return "; ".join(item.get("path", "") for item in combined_scope.get(key, []) if isinstance(item, dict))
        def joined_meta(field: str) -> str:
            values: list[str] = []
            for key in ("face_anchors", "outfit_anchors", "product_anchors", "scene_anchors", "style_anchors", "generic_references"):
                for item in combined_scope.get(key, []):
                    if isinstance(item, dict) and item.get(field) not in (None, ""):
                        values.append(f"{key}:{item.get(field)}")
            return "; ".join(values)
        values = [
            row["panel_index"],
            row["label"],
            row["image"],
            row["caption"],
            row["source_panel"],
            row["text_source"],
            row["source_visual"],
            row["story_beat"],
            row["story_text"],
            row["subtitle"],
            row["voiceover"],
            row["subtitle_voiceover"],
            row["sound_design"],
            row["binding_status"],
            row["shot_target"],
            row["prompt"],
            handoff.get("keyframe_role", ""),
            handoff.get("duration_sec", ""),
            handoff.get("camera_move", ""),
            handoff.get("transition_to_next", ""),
            handoff.get("motion_strength", ""),
            handoff.get("loop_safe", ""),
            joined_paths("face_anchors"),
            joined_paths("outfit_anchors"),
            joined_paths("product_anchors"),
            joined_paths("scene_anchors"),
            joined_paths("style_anchors"),
            joined_paths("generic_references"),
            joined_meta("weight"),
            joined_meta("priority"),
            joined_meta("crop"),
            joined_meta("focus"),
            joined_meta("lock"),
            first_frame.get("path", ""),
            last_frame.get("path", ""),
            combined_scope.get("panel_note", ""),
        ]
        escaped = ['"' + str(value).replace('"', '""') + '"' for value in values]
        csv_lines.append(",".join(escaped))
    (out_dir / "panels.csv").write_text("\n".join(csv_lines) + "\n", encoding="utf-8")

    groups: list[dict[str, Any]] = []
    for group_index, start in enumerate(range(0, len(panel_rows), group_size), start=1):
        group_panels = panel_rows[start : start + group_size]
        group_payload = {
            "group_index": group_index,
            "panel_indices": [row["panel_index"] for row in group_panels],
            "title": title,
            "subtitle": subtitle,
            "brief_context": context,
            "panels": group_panels,
        }
        groups.append(group_payload)
        panel_indices_text = ", ".join(f"{row['panel_index']:02d}" for row in group_panels)
        group_lines = [
            f"# Group {group_index:02d}",
            f"Panels: {panel_indices_text}",
            f"Title: {title}",
        ]
        if subtitle:
            group_lines.append(f"Subtitle: {subtitle}")
        group_lines.extend(
            [
                "",
                "## Global Lock",
                str(context.get("global_lock", "")),
                "",
                "## Panels",
            ]
        )
        for row in group_panels:
            handoff = row["video_handoff"]
            group_lines.extend(
                [
                    "",
                    f"### Panel {row['panel_index']:02d} - {row['label']}",
                    f"Image: {row['image']}",
                    f"Caption: {row['caption']}",
                    f"Source panel: {row['source_panel']}",
                    f"Text source: {row['text_source']}",
                    f"Source visual: {row['source_visual']}",
                    f"Story beat: {row['story_beat']}",
                    f"Story text: {row['story_text']}",
                    f"Subtitle: {row['subtitle']}",
                    f"Voiceover: {row['voiceover']}",
                    f"Subtitle/voiceover: {row['subtitle_voiceover']}",
                    f"Sound design: {row['sound_design']}",
                    f"Binding status: {row['binding_status']}",
                    f"Shot target: {row['shot_target']}",
                    f"Prompt: {row['prompt']}",
                    f"Keyframe role: {handoff.get('keyframe_role', '')}",
                    f"Duration: {handoff.get('duration_sec', '')}",
                    f"Camera move: {handoff.get('camera_move', '')}",
                    f"Transition: {handoff.get('transition_to_next', '')}",
                    f"Motion strength: {handoff.get('motion_strength', '')}",
                    f"Loop safe: {handoff.get('loop_safe', '')}",
                ]
            )
        (group_dir / f"group-{group_index:02d}.txt").write_text("\n".join(group_lines).strip() + "\n", encoding="utf-8")

    (out_dir / "groups.json").write_text(json.dumps(groups, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "video-handoff.json").write_text(
        json.dumps(
            [
                {
                    "panel_index": row["panel_index"],
                    "label": row["label"],
                    "image": row["image"],
                    "caption": row["caption"],
                    "source_panel": row["source_panel"],
                    "text_source": row["text_source"],
                    "source_visual": row["source_visual"],
                    "story_beat": row["story_beat"],
                    "story_text": row["story_text"],
                    "subtitle": row["subtitle"],
                    "voiceover": row["voiceover"],
                    "subtitle_voiceover": row["subtitle_voiceover"],
                    "sound_design": row["sound_design"],
                    "binding_status": row["binding_status"],
                    "shot_target": row["shot_target"],
                    "video_handoff": row["video_handoff"],
                    "combined_reference_scope": row["combined_reference_scope"],
                    "first_frame": row["first_frame"],
                    "last_frame": row["last_frame"],
                }
                for row in panel_rows
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def flatten_domestic_terms(lexicon: dict[str, Any]) -> list[dict[str, str]]:
    terms: list[dict[str, str]] = []
    for category in lexicon.get("categories", []):
        if not isinstance(category, dict):
            continue
        category_name = str(category.get("name", "uncategorized"))
        replacements = category.get("positive_replacements", {})
        if not isinstance(replacements, dict):
            replacements = {}
        for term in category.get("terms", []):
            term_text = str(term)
            if not term_text:
                continue
            terms.append(
                {
                    "term": term_text,
                    "category": category_name,
                    "replacement": str(replacements.get(term_text, "")),
                }
            )
    return terms


def iter_domestic_scan_files(paths: list[Path], exclude_names: set[str]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            candidates = sorted(item for item in path.rglob("*") if item.is_file())
        else:
            candidates = [path]
        for candidate in candidates:
            if candidate.name in exclude_names:
                continue
            if candidate.suffix.lower() not in DOMESTIC_SCAN_SUFFIXES:
                continue
            files.append(candidate)
    return files


def json_string_segments(value: Any, prefix: str = "$") -> list[tuple[str, str, int]]:
    if isinstance(value, str):
        return [(prefix, value, 1)]
    if isinstance(value, list):
        segments: list[tuple[str, str, int]] = []
        for index, item in enumerate(value):
            segments.extend(json_string_segments(item, f"{prefix}[{index}]"))
        return segments
    if isinstance(value, dict):
        segments = []
        for key, item in value.items():
            segments.extend(json_string_segments(item, f"{prefix}.{key}"))
        return segments
    return []


def prompt_segments_for_file(path: Path) -> list[tuple[str, str, int]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            return json_string_segments(json.loads(text))
        except json.JSONDecodeError:
            return [("body", text, 1)]
    if path.suffix.lower() == ".md":
        segments: list[tuple[str, str, int]] = []
        for index, match in enumerate(MARKDOWN_FENCE_RE.finditer(text), start=1):
            line = text[: match.start(1)].count("\n") + 1
            segments.append((f"code-block-{index}", match.group(1), line))
        if segments:
            return segments
    return [("body", text, 1)]


def scan_domestic_safety(
    paths: list[Path],
    lexicon_path: Path,
    exclude_names: list[str] | None,
    json_output: bool,
) -> None:
    if not lexicon_path.exists():
        raise SystemExit(f"Domestic safety lexicon not found: {lexicon_path}")
    lexicon = json.loads(lexicon_path.read_text(encoding="utf-8"))
    terms = flatten_domestic_terms(lexicon)
    excludes = set(DEFAULT_DOMESTIC_SCAN_EXCLUDE_NAMES)
    if exclude_names:
        excludes.update(exclude_names)

    files = iter_domestic_scan_files(paths, excludes)
    issues: list[dict[str, Any]] = []
    segment_count = 0
    for file_path in files:
        try:
            segments = prompt_segments_for_file(file_path)
        except UnicodeDecodeError:
            continue
        segment_count += len(segments)
        for segment_name, segment_text, base_line in segments:
            for term in terms:
                flags = re.IGNORECASE if term["term"].isascii() else 0
                for match in re.finditer(re.escape(term["term"]), segment_text, flags):
                    issues.append(
                        {
                            "path": str(file_path),
                            "line": base_line + segment_text[: match.start()].count("\n"),
                            "segment": segment_name,
                            "term": term["term"],
                            "category": term["category"],
                            "replacement": term["replacement"],
                        }
                    )

    result = {
        "ok": not issues,
        "files_scanned": len(files),
        "prompt_segments_scanned": segment_count,
        "issues": issues,
    }
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif issues:
        print("Domestic safety scan found terms to rewrite:")
        for issue in issues:
            replacement = f" -> {issue['replacement']}" if issue.get("replacement") else ""
            print(
                f"{issue['path']}:{issue['line']}: "
                f"[{issue['category']}] {issue['term']}{replacement}"
            )
    else:
        print(
            "OK: scanned "
            f"{len(files)} files and {segment_count} prompt bodies; "
            "no domestic sensitive terms or negative-prompt markers found."
        )

    if issues:
        raise SystemExit(1)


def main() -> None:
    args = parse_args()
    if args.command == "new-spec":
        new_spec(args.profile, args.language, args.out, args.title, args.subtitle)
    elif args.command == "apply-brief":
        apply_brief_to_spec(
            args.spec,
            args.out,
            args.brief,
            args.language,
            args.subject,
            args.product,
            args.scene,
            args.mood,
            args.platform,
            args.aspect,
            args.title,
            args.subtitle,
        )
    elif args.command == "inspect-brief":
        inspect_brief(
            args.profile,
            args.brief,
            args.language,
            args.subject,
            args.product,
            args.scene,
            args.mood,
            args.platform,
            args.aspect,
            args.out,
        )
    elif args.command == "attach-references":
        attach_references_to_spec(
            args.spec,
            args.out,
            args.panel,
            args.panel_note,
            args.protagonist_image,
            args.face_anchor,
            args.outfit_anchor,
            args.product_anchor,
            args.scene_anchor,
            args.style_anchor,
            args.reference_image,
            args.first_frame,
            args.last_frame,
            args.reference_weight,
            args.reference_priority,
            args.reference_crop,
            args.reference_focus,
            args.reference_lock,
        )
    elif args.command == "annotate-panel":
        annotate_panel(
            args.spec,
            args.out,
            args.panel,
            args.keyframe_role,
            args.duration_sec,
            args.camera_move,
            args.transition_to_next,
            args.motion_strength,
            args.loop_safe,
            args.shot_note,
            args.source_panel,
            args.text_source,
            args.source_visual,
            args.story_beat,
            args.story_text,
            args.subtitle,
            args.voiceover,
            args.subtitle_voiceover,
            args.sound_design,
            args.binding_status,
        )
    elif args.command == "render-sheet":
        render_sheet(args.spec, args.out)
    elif args.command == "export-markdown":
        export_markdown(args.spec, args.out)
    elif args.command == "export-prompts":
        export_prompts(args.spec, args.out_dir, args.group_size)
    elif args.command == "scan-domestic-safety":
        scan_domestic_safety(args.path, args.lexicon, args.exclude_name, args.json)
    else:  # pragma: no cover
        raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
