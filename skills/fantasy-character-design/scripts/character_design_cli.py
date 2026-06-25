#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Pillow is required. Install it with `pip install pillow`.") from exc


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
PROFILE_VARIANTS = {
    "xianxia-goddess": {"zh": ASSETS / "xianxia-goddess-character-sheet-zh.json"},
    "xianxia-empress": {"zh": ASSETS / "xianxia-empress-character-sheet-zh.json"},
    "flower-spirit": {"zh": ASSETS / "flower-spirit-character-sheet-zh.json"},
    "starlight-deity": {"zh": ASSETS / "starlight-deity-character-sheet-zh.json"},
}
SUPPORTED_LANGUAGES = ("zh",)
REFERENCE_KEYS = ("face_anchors", "costume_anchors", "prop_anchors", "style_anchors", "generic_references")
REFERENCE_ROLE_DEFAULTS = {
    "face_anchors": {
        "weight": 1.0,
        "priority": 100,
        "crop": "face close-up / 3:4 portrait crop",
        "focus": "face identity, eye shape, hairline, makeup, expression",
        "lock": "hard-identity",
    },
    "costume_anchors": {
        "weight": 0.88,
        "priority": 82,
        "crop": "full-body costume or garment-detail crop",
        "focus": "silhouette, neckline, sleeves, train, jewelry, fabric layering",
        "lock": "hard-costume",
    },
    "prop_anchors": {
        "weight": 0.95,
        "priority": 90,
        "crop": "prop or magic-device detail crop",
        "focus": "weapon, magic circle, flower, orb, device shape and ornament",
        "lock": "hard-prop-detail",
    },
    "style_anchors": {
        "weight": 0.45,
        "priority": 35,
        "crop": "style/color/layout crop",
        "focus": "palette, lighting, rendering finish, board layout mood",
        "lock": "soft-style",
    },
    "generic_references": {
        "weight": 0.35,
        "priority": 20,
        "crop": "loose reference crop",
        "focus": "general inspiration only",
        "lock": "soft-inspiration",
    },
}
REFERENCE_CONFLICT_POLICY = (
    "冲突规则：先按 priority 处理，再按 weight 强弱处理；脸部身份不被服装/法器参考改写，"
    "服装锚点只锁廓形材质和配饰，法器锚点只锁道具局部，风格参考只影响色调、光线和版式。"
)

BRIEF_SPLIT_RE = re.compile(r"[，,、；;。|/\n]+")
NAME_KEYWORDS = ["璇玑女帝", "牡丹仙子", "星尘神女", "星尘女神", "玄幻神女", "神女", "女帝", "仙子", "花神", "圣女", "妖后"]
ARCHETYPE_KEYWORDS = {
    "女帝": "玄幻女帝",
    "神女": "星灵神女",
    "女神": "星灵女神",
    "仙子": "花神仙子",
    "花神": "花神仙子",
    "圣女": "仙门圣女",
    "妖后": "玄幻妖后",
    "剑修": "仙侠剑修",
}
THEME_KEYWORDS = ["唯美玄幻", "国风仙侠", "东方幻想", "暗色高级", "游戏角色设定", "角色设定板", "设定图", "神话", "花神", "星空", "星尘", "冰晶"]
IDENTITY_KEYWORDS = ["长发", "银白", "乌黑", "发髻", "眼神", "瞳", "脸", "妆", "气质", "冷艳", "温柔", "神性", "比例"]
COSTUME_KEYWORDS = ["长裙", "华服", "薄纱", "披帛", "高开衩", "刺绣", "胸甲", "首饰", "裙摆", "长袍", "袖", "鞋"]
MATERIAL_KEYWORDS = ["薄纱", "丝绸", "水晶", "玉石", "金属", "星云", "星尘", "花瓣", "牡丹", "冰晶", "金线", "透明"]
PROP_KEYWORDS = ["法器", "星盘", "法阵", "权杖", "剑", "花枝", "花神印记", "圆环", "宝珠", "扇", "发簪", "帝冠"]
PALETTE_KEYWORDS = ["红金", "银紫", "蓝紫", "银白", "深夜蓝", "星云紫", "牡丹红", "暖金", "月白", "青玉", "淡金", "冰晶蓝"]
NOISE_TERMS = ["角色设定图", "人物设定图", "角色设定板", "设定板", "设定图", "三视图", "转面图", "帮我", "做一个", "做一张", "生成"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create fantasy character design sheet specs and prompt packs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_spec = subparsers.add_parser("new-spec", help="Copy a starter character design spec.")
    new_spec.add_argument("--profile", choices=sorted(PROFILE_VARIANTS), required=True)
    new_spec.add_argument("--language", choices=SUPPORTED_LANGUAGES, default="zh")
    new_spec.add_argument("--out", required=True, type=Path)
    new_spec.add_argument("--title")
    new_spec.add_argument("--subtitle")

    inspect = subparsers.add_parser("inspect-brief", help="Infer character fields from a brief without editing files.")
    inspect.add_argument("--profile", choices=sorted(PROFILE_VARIANTS), default="starlight-deity")
    inspect.add_argument("--brief", required=True)
    inspect.add_argument("--out", type=Path)

    apply = subparsers.add_parser("apply-brief", help="Apply a brief to a character design spec.")
    apply.add_argument("--spec", required=True, type=Path)
    apply.add_argument("--out", required=True, type=Path)
    apply.add_argument("--brief", required=True)
    apply.add_argument("--name")
    apply.add_argument("--archetype")
    apply.add_argument("--visual-theme")
    apply.add_argument("--identity-lock")
    apply.add_argument("--costume-lock")
    apply.add_argument("--world")
    apply.add_argument("--title")
    apply.add_argument("--subtitle")

    refs = subparsers.add_parser("attach-references", help="Attach face, costume, prop, style, or generic references.")
    refs.add_argument("--spec", required=True, type=Path)
    refs.add_argument("--out", required=True, type=Path)
    refs.add_argument("--face-anchor", action="append", default=[])
    refs.add_argument("--costume-anchor", action="append", default=[])
    refs.add_argument("--prop-anchor", action="append", default=[])
    refs.add_argument("--style-anchor", action="append", default=[])
    refs.add_argument("--reference-image", action="append", default=[])
    refs.add_argument("--reference-weight", type=float, help="Override weight for references added by this command, 0.0-1.0.")
    refs.add_argument("--reference-priority", type=int, help="Override priority for references added by this command. Higher wins conflicts.")
    refs.add_argument("--reference-crop", help="Override crop guidance for references added by this command.")
    refs.add_argument("--reference-focus", help="Override focus guidance for references added by this command.")
    refs.add_argument("--reference-lock", help="Override lock strength such as hard-identity, hard-costume, hard-prop-detail, soft-style.")

    render = subparsers.add_parser("render-layout", help="Render a placeholder character design sheet.")
    render.add_argument("--spec", required=True, type=Path)
    render.add_argument("--out", required=True, type=Path)

    validate = subparsers.add_parser("validate-sheet", help="Validate required character design sheet coverage.")
    validate.add_argument("--spec", required=True, type=Path)
    validate.add_argument("--out", type=Path)

    export = subparsers.add_parser("export-prompts", help="Export full-board prompts, section prompts, and handoff files.")
    export.add_argument("--spec", required=True, type=Path)
    export.add_argument("--out-dir", required=True, type=Path)

    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def split_brief(text: str) -> list[str]:
    return [part.strip() for part in BRIEF_SPLIT_RE.split(text) if part.strip()]


def clean_noise(text: str) -> str:
    cleaned = text
    for term in NOISE_TERMS:
        cleaned = cleaned.replace(term, "")
    return cleaned.strip(" ：:，,;；。. ")


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = clean_noise(value)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def find_keywords(brief: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in brief]


def first_segment_with(segments: list[str], keywords: list[str]) -> str | None:
    for segment in segments:
        if any(keyword in segment for keyword in keywords):
            return clean_noise(segment)
    return None


def infer_context(template: dict[str, Any], brief: str) -> dict[str, Any]:
    character = dict(template.get("character", {}))
    segments = split_brief(brief)
    name = next((keyword for keyword in NAME_KEYWORDS if keyword in brief), character.get("name", "玄幻角色"))
    archetype = character.get("archetype", "玄幻角色")
    for keyword, value in ARCHETYPE_KEYWORDS.items():
        if keyword in brief:
            archetype = value
            break

    inferred_identity = first_segment_with(segments, IDENTITY_KEYWORDS)
    inferred_costume = first_segment_with(segments, COSTUME_KEYWORDS)
    default_identity = str(character.get("identity_lock", ""))
    default_costume = str(character.get("costume_lock", ""))
    identity = merge_inferred_lock(inferred_identity, default_identity)
    costume = merge_inferred_lock(inferred_costume, default_costume)
    theme_parts = unique(
        [
            segment
            for segment in segments
            if any(keyword in segment for keyword in THEME_KEYWORDS)
            and not any(name_keyword in segment for name_keyword in NAME_KEYWORDS)
        ]
    )
    visual_theme = "、".join(theme_parts[:2]) if theme_parts else character.get("visual_theme", "")
    materials = unique(find_keywords(brief, MATERIAL_KEYWORDS) + list(character.get("materials", [])))[:8]
    props = unique(find_keywords(brief, PROP_KEYWORDS) + list(character.get("props", [])))[:8]
    palette = unique(find_keywords(brief, PALETTE_KEYWORDS) + list(character.get("palette", [])))[:8]
    world = first_segment_with(segments, ["神殿", "仙宫", "花境", "星海", "祭坛", "庭院", "云海"]) or character.get("world", "")

    return {
        "brief": brief,
        "name": name,
        "archetype": archetype,
        "visual_theme": visual_theme,
        "identity_lock": identity,
        "costume_lock": costume,
        "materials": materials,
        "props": props,
        "palette": palette,
        "world": world,
        "avoid": character.get("avoid", []),
        "parsed_segments": segments,
    }


def merge_inferred_lock(inferred: str | None, default: str) -> str:
    if not inferred:
        return default
    if inferred in default:
        return default
    if default and len(inferred) <= 12:
        return f"{inferred}，{default}"
    return inferred


def extract_section_target(prompt: str) -> str:
    target = prompt.strip()
    if "分区目标：" in target:
        target = target.split("分区目标：", 1)[1].strip()
    if "画面内不要生成小字" in target:
        target = target.split("画面内不要生成小字", 1)[0].strip(" ，。")
    return target


def ensure_reference_inputs(spec: dict[str, Any]) -> dict[str, Any]:
    existing = spec.get("reference_inputs")
    normalized = {key: [] for key in REFERENCE_KEYS}
    if isinstance(existing, dict):
        for key in REFERENCE_KEYS:
            normalized[key] = normalize_reference_list(existing.get(key, []), key)
    spec["reference_inputs"] = normalized
    return normalized


def reference_defaults(role_key: str | None, role: str | None = None) -> dict[str, Any]:
    if role_key and role_key in REFERENCE_ROLE_DEFAULTS:
        return dict(REFERENCE_ROLE_DEFAULTS[role_key])
    role_text = role or ""
    if "face" in role_text:
        return dict(REFERENCE_ROLE_DEFAULTS["face_anchors"])
    if "costume" in role_text or "outfit" in role_text:
        return dict(REFERENCE_ROLE_DEFAULTS["costume_anchors"])
    if "prop" in role_text or "weapon" in role_text or "detail" in role_text:
        return dict(REFERENCE_ROLE_DEFAULTS["prop_anchors"])
    if "style" in role_text:
        return dict(REFERENCE_ROLE_DEFAULTS["style_anchors"])
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
    resolved = str(Path(path).expanduser().resolve())
    defaults = reference_defaults(role_key, role)
    return {
        "path": resolved,
        "role": role,
        "name": Path(resolved).name,
        "weight": clamp_weight(weight, defaults["weight"]),
        "priority": normalize_priority(priority, defaults["priority"]),
        "crop": crop or defaults["crop"],
        "focus": focus or defaults["focus"],
        "lock": lock or defaults["lock"],
    }


def normalize_reference_list(items: Any, role_key: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not item.get("path"):
            continue
        path = str(item["path"])
        if path in seen:
            continue
        seen.add(path)
        role = str(item.get("role", ""))
        defaults = reference_defaults(role_key, role)
        result.append(
            {
                "path": path,
                "role": role,
                "name": str(item.get("name", Path(path).name)),
                "weight": clamp_weight(item.get("weight"), defaults["weight"]),
                "priority": normalize_priority(item.get("priority"), defaults["priority"]),
                "crop": str(item.get("crop") or defaults["crop"]),
                "focus": str(item.get("focus") or defaults["focus"]),
                "lock": str(item.get("lock") or defaults["lock"]),
            }
        )
    return result


def validate_paths(paths: list[str]) -> list[str]:
    result: list[str] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"Reference image not found: {path}")
        result.append(str(path))
    return result


def merge_entries(existing: list[dict[str, Any]], additions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_path = {item["path"]: item for item in existing if isinstance(item, dict) and item.get("path")}
    for item in additions:
        by_path[item["path"]] = item
    return list(by_path.values())


def build_global_lock(spec: dict[str, Any]) -> str:
    character = spec.get("character", {})
    return (
        f"角色设定：{character.get('name', '')}，{character.get('archetype', '')}；"
        f"视觉风格：{character.get('visual_theme', '')}；"
        f"身份锁定：{character.get('identity_lock', '')}；"
        f"服装锁定：{character.get('costume_lock', '')}；"
        f"材质：{'、'.join(character.get('materials', []))}；"
        f"法器/符号：{'、'.join(character.get('props', []))}；"
        f"色彩：{'、'.join(character.get('palette', []))}；"
        f"世界：{character.get('world', '')}；"
        "保持同一角色、同一发型、同一服装廓形、同一法器语言和同一色彩体系。"
    )


def describe_reference_strategy(reference_inputs: dict[str, Any]) -> str:
    labels = {
        "face_anchors": "脸部锚点",
        "costume_anchors": "服装锚点",
        "prop_anchors": "法器/道具锚点",
        "style_anchors": "风格锚点",
        "generic_references": "辅助参考",
    }
    parts: list[str] = []
    for key in REFERENCE_KEYS:
        entries = reference_inputs.get(key, [])
        if not isinstance(entries, list) or not entries:
            continue
        top = sorted(entries, key=reference_rank, reverse=True)[0]
        parts.append(
            f"{labels[key]}{len(entries)}张(最高P{top.get('priority')}/W{top.get('weight')}, 裁剪={top.get('crop')}, 关注={top.get('focus')}, 锁定={top.get('lock')})"
        )
    if not parts:
        return ""
    return f"参考权重与裁剪策略：{'；'.join(parts)}。{REFERENCE_CONFLICT_POLICY}"


def flatten_reference_entries(reference_inputs: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for key in REFERENCE_KEYS:
        for item in reference_inputs.get(key, []):
            if not isinstance(item, dict):
                continue
            entries.append(
                {
                    "anchor_group": key,
                    "path": item.get("path", ""),
                    "role": item.get("role", ""),
                    "name": item.get("name", ""),
                    "weight": item.get("weight", ""),
                    "priority": item.get("priority", ""),
                    "crop": item.get("crop", ""),
                    "focus": item.get("focus", ""),
                    "lock": item.get("lock", ""),
                }
            )
    return entries


def joined_reference_field(entries: list[dict[str, Any]], field: str) -> str:
    values: list[str] = []
    for item in entries:
        value = item.get(field)
        if value not in (None, ""):
            values.append(f"{item.get('anchor_group', '')}:{value}")
    return "; ".join(values)


def reference_csv_summary(reference_inputs: dict[str, Any]) -> dict[str, str]:
    entries = flatten_reference_entries(reference_inputs)
    return {
        "reference_paths": joined_reference_field(entries, "path"),
        "reference_weights": joined_reference_field(entries, "weight"),
        "reference_priorities": joined_reference_field(entries, "priority"),
        "reference_crops": joined_reference_field(entries, "crop"),
        "reference_focuses": joined_reference_field(entries, "focus"),
        "reference_locks": joined_reference_field(entries, "lock"),
    }


def refresh_prompts(spec: dict[str, Any]) -> None:
    global_lock = build_global_lock(spec)
    reference_strategy = describe_reference_strategy(ensure_reference_inputs(spec))
    for section in spec.get("sections", []):
        target = extract_section_target(str(section.get("shot_target") or section.get("prompt", "")))
        section["shot_target"] = target
        parts = [global_lock, reference_strategy, f"分区目标：{target}", "画面内不要生成小字，中文标签由后期排版添加。"]
        section["prompt"] = " ".join(part for part in parts if part)
    spec["global_prompt"] = build_full_board_prompt(spec)


def build_full_board_prompt(spec: dict[str, Any]) -> str:
    character = spec.get("character", {})
    avoid = "、".join(character.get("avoid", []))
    sections = "、".join(section.get("label", "") for section in spec.get("sections", []))
    reference_strategy = describe_reference_strategy(ensure_reference_inputs(spec))
    return (
        "生成一张竖版高级玄幻角色设定板，画面内不要生成小字，文字后期排版添加。"
        f"角色：{character.get('name', '')}，{character.get('archetype', '')}。"
        f"身份锁定：{character.get('identity_lock', '')}。"
        f"服装锁定：{character.get('costume_lock', '')}。"
        f"材质：{'、'.join(character.get('materials', []))}。"
        f"法器/符号：{'、'.join(character.get('props', []))}。"
        f"色彩：{'、'.join(character.get('palette', []))}。"
        f"世界观：{character.get('world', '')}。"
        f"版式包含：{sections}。"
        f"风格：{character.get('visual_theme', '')}，游戏美术设定稿，暗色高级长图，细节丰富，角色一致。"
        f"{reference_strategy}"
        f"避免：{avoid}。"
    )


def new_spec(profile: str, language: str, out: Path, title: str | None, subtitle: str | None) -> None:
    payload = load_json(PROFILE_VARIANTS[profile][language])
    if title:
        payload["title"] = title
    if subtitle:
        payload["subtitle"] = subtitle
    ensure_reference_inputs(payload)
    refresh_prompts(payload)
    save_json(out, payload)


def inspect_brief(profile: str, brief: str, out: Path | None) -> None:
    template = load_json(PROFILE_VARIANTS[profile]["zh"])
    payload = {
        "profile_id": profile,
        "language": "zh",
        "inferred_context": infer_context(template, brief),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def apply_brief(
    spec_path: Path,
    out: Path,
    brief: str,
    name: str | None,
    archetype: str | None,
    visual_theme: str | None,
    identity_lock: str | None,
    costume_lock: str | None,
    world: str | None,
    title: str | None,
    subtitle: str | None,
) -> None:
    spec = load_json(spec_path)
    context = infer_context(spec, brief)
    character = spec.setdefault("character", {})
    character["name"] = name or context["name"]
    character["archetype"] = archetype or context["archetype"]
    character["visual_theme"] = visual_theme or context["visual_theme"]
    character["identity_lock"] = identity_lock or context["identity_lock"]
    character["costume_lock"] = costume_lock or context["costume_lock"]
    character["materials"] = context["materials"]
    character["props"] = context["props"]
    character["palette"] = context["palette"]
    character["world"] = world or context["world"]
    character["brief"] = brief
    spec["title"] = title or f"{character['name']}角色设定板"
    spec["subtitle"] = subtitle or "主立绘 / 三视图 / 脸部眼睛 / 服装材质 / 法器色卡"
    ensure_reference_inputs(spec)
    refresh_prompts(spec)
    save_json(out, spec)


def attach_references(
    spec_path: Path,
    out: Path,
    face: list[str],
    costume: list[str],
    prop: list[str],
    style: list[str],
    generic: list[str],
    reference_weight: float | None,
    reference_priority: int | None,
    reference_crop: str | None,
    reference_focus: str | None,
    reference_lock: str | None,
) -> None:
    spec = load_json(spec_path)
    refs = ensure_reference_inputs(spec)
    metadata = {
        "weight": reference_weight,
        "priority": reference_priority,
        "crop": reference_crop,
        "focus": reference_focus,
        "lock": reference_lock,
    }
    additions = {
        "face_anchors": [asset_entry(path, "face-anchor", "face_anchors", **metadata) for path in validate_paths(face)],
        "costume_anchors": [asset_entry(path, "costume-anchor", "costume_anchors", **metadata) for path in validate_paths(costume)],
        "prop_anchors": [asset_entry(path, "prop-anchor", "prop_anchors", **metadata) for path in validate_paths(prop)],
        "style_anchors": [asset_entry(path, "style-anchor", "style_anchors", **metadata) for path in validate_paths(style)],
        "generic_references": [asset_entry(path, "generic-reference", "generic_references", **metadata) for path in validate_paths(generic)],
    }
    for key, entries in additions.items():
        refs[key] = merge_entries(refs.get(key, []), entries)
    refresh_prompts(spec)
    save_json(out, spec)


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/arialbd.ttf"])
    candidates.extend(["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/arial.ttf"])
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        trial = current + char
        if current and text_width(draw, trial, font) > width:
            lines.append(current)
            current = char
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def fit_image(path: str, size: tuple[int, int]) -> Image.Image | None:
    if not path:
        return None
    image_path = Path(path)
    if not image_path.exists():
        return None
    with Image.open(image_path) as image:
        return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)


def draw_panel(
    sheet: Image.Image,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    section: dict[str, Any],
    fonts: dict[str, ImageFont.ImageFont],
    colors: dict[str, str],
) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=22, fill=colors["panel_fill"], outline=colors["panel_border"], width=2)
    label = str(section.get("label", ""))
    caption = str(section.get("caption", ""))
    image = fit_image(str(section.get("image", "")), (x1 - x0 - 24, y1 - y0 - 92))
    if image:
        sheet.paste(image, (x0 + 12, y0 + 12))
    else:
        placeholder = str(section.get("shot_target", section.get("prompt", "")))
        placeholder = extract_section_target(placeholder)
        lines = wrap_text(draw, placeholder, fonts["small"], x1 - x0 - 42)[:7]
        draw.rounded_rectangle((x0 + 12, y0 + 12, x1 - 12, y1 - 92), radius=16, fill=colors["placeholder_fill"])
        draw.multiline_text((x0 + 26, y0 + 28), "\n".join(lines), font=fonts["small"], fill=colors["muted"], spacing=5)
    draw.text((x0 + 18, y1 - 76), label, font=fonts["label"], fill=colors["text"])
    cap_lines = wrap_text(draw, caption, fonts["small"], x1 - x0 - 36)[:2]
    draw.multiline_text((x0 + 18, y1 - 42), "\n".join(cap_lines), font=fonts["small"], fill=colors["muted"], spacing=4)


def layout_boxes(spec: dict[str, Any]) -> dict[str, tuple[int, int, int, int]]:
    width = int(spec.get("canvas", {}).get("width", 1440))
    margin = 54
    gap = 18
    header = 166
    hero_w = 555
    right_x = margin + hero_w + gap
    right_w = width - right_x - margin
    third_w = int((right_w - 2 * gap) / 3)
    boxes: dict[str, tuple[int, int, int, int]] = {
        "hero_full_body": (margin, header, margin + hero_w, 1600),
        "turnaround_front": (right_x, header, right_x + third_w, 730),
        "turnaround_side": (right_x + third_w + gap, header, right_x + 2 * third_w + gap, 730),
        "turnaround_back": (right_x + 2 * (third_w + gap), header, right_x + 3 * third_w + 2 * gap, 730),
    }
    detail_ids = [section.get("id") for section in spec.get("sections", []) if section.get("id") not in boxes]
    detail_top = 760
    detail_h = 350
    detail_w = int((right_w - gap) / 2)
    for index, section_id in enumerate(detail_ids[:6]):
        row = index // 2
        col = index % 2
        x0 = right_x + col * (detail_w + gap)
        y0 = detail_top + row * (detail_h + gap)
        boxes[str(section_id)] = (x0, y0, x0 + detail_w, y0 + detail_h)
    bottom_top = 1630
    bottom_w = int((width - 2 * margin - 2 * gap) / 3)
    for index, section_id in enumerate(detail_ids[6:9]):
        x0 = margin + index * (bottom_w + gap)
        boxes[str(section_id)] = (x0, bottom_top, x0 + bottom_w, 2020)
    return boxes


def render_layout(spec_path: Path, out: Path) -> None:
    spec = load_json(spec_path)
    refresh_prompts(spec)
    canvas = spec.get("canvas", {})
    theme = spec.get("theme", {})
    width = int(canvas.get("width", 1440))
    height = int(canvas.get("height", 2560))
    colors = {
        "background": str(canvas.get("background", "#101018")),
        "panel_fill": str(theme.get("panel_fill", "#171a28")),
        "panel_border": str(theme.get("panel_border", "#596070")),
        "accent": str(theme.get("accent", "#c6c9ff")),
        "text": str(theme.get("text", "#f4f4ff")),
        "muted": str(theme.get("muted", "#a5abc1")),
        "placeholder_fill": str(theme.get("placeholder_fill", "#1d2438")),
    }
    fonts = {
        "title": load_font(48, bold=True),
        "subtitle": load_font(23),
        "label": load_font(24, bold=True),
        "small": load_font(18),
    }
    sheet = Image.new("RGB", (width, height), colors["background"])
    draw = ImageDraw.Draw(sheet)
    draw.text((54, 46), str(spec.get("title", "Character Design Sheet")), font=fonts["title"], fill=colors["text"])
    draw.text((54, 108), str(spec.get("subtitle", "")), font=fonts["subtitle"], fill=colors["muted"])
    boxes = layout_boxes(spec)
    for section in spec.get("sections", []):
        section_id = str(section.get("id", ""))
        if section_id in boxes:
            draw_panel(sheet, draw, boxes[section_id], section, fonts, colors)
    character = spec.get("character", {})
    info_box = (54, 2050, width - 54, height - 70)
    draw.rounded_rectangle(info_box, radius=24, fill=colors["panel_fill"], outline=colors["panel_border"], width=2)
    info_lines = [
        f"角色：{character.get('name', '')} / {character.get('archetype', '')}",
        f"身份锁定：{character.get('identity_lock', '')}",
        f"服装锁定：{character.get('costume_lock', '')}",
        f"材质：{'、'.join(character.get('materials', []))}",
        f"法器：{'、'.join(character.get('props', []))}",
        f"色彩：{'、'.join(character.get('palette', []))}",
    ]
    draw.multiline_text((78, 2080), "\n".join(info_lines), font=fonts["small"], fill=colors["muted"], spacing=10)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)


def validate_sheet(spec_path: Path, out: Path | None) -> None:
    spec = load_json(spec_path)
    reference_inputs = ensure_reference_inputs(spec)
    reference_entries = flatten_reference_entries(reference_inputs)
    required_reference_fields = ("path", "role", "weight", "priority", "crop", "focus", "lock")
    roles = {section.get("role") for section in spec.get("sections", [])}
    ids = {section.get("id") for section in spec.get("sections", [])}
    required_ids = {
        "hero_full_body",
        "turnaround_front",
        "turnaround_side",
        "turnaround_back",
        "face_closeup",
        "eye_detail",
        "costume_detail",
        "prop_detail",
        "palette",
    }
    missing = sorted(required_ids - ids)
    character = spec.get("character", {})
    field_missing = [
        field
        for field in ("name", "archetype", "visual_theme", "identity_lock", "costume_lock", "materials", "props", "palette", "avoid")
        if not character.get(field)
    ]
    payload = {
        "valid": not missing and not field_missing,
        "missing_sections": missing,
        "missing_character_fields": field_missing,
        "roles": sorted(str(role) for role in roles if role),
        "section_count": len(spec.get("sections", [])),
        "reference_entry_count": len(reference_entries),
        "reference_metadata_complete": (
            all(all(entry.get(field) not in (None, "") for field in required_reference_fields) for entry in reference_entries)
            if reference_entries
            else None
        ),
        "reference_strategy": describe_reference_strategy(reference_inputs),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    if not payload["valid"]:
        raise SystemExit(1)


def export_prompts(spec_path: Path, out_dir: Path) -> None:
    spec = load_json(spec_path)
    reference_inputs = ensure_reference_inputs(spec)
    refresh_prompts(spec)
    reference_strategy = describe_reference_strategy(reference_inputs)
    reference_entries = flatten_reference_entries(reference_inputs)
    reference_summary = reference_csv_summary(reference_inputs)
    out_dir.mkdir(parents=True, exist_ok=True)
    sections_dir = out_dir / "section-prompts"
    sections_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "full-board-prompt.txt").write_text(spec.get("global_prompt", "") + "\n", encoding="utf-8")
    rows: list[dict[str, Any]] = []
    for section in spec.get("sections", []):
        row = {
            "id": section.get("id", ""),
            "label": section.get("label", ""),
            "role": section.get("role", ""),
            "caption": section.get("caption", ""),
            "prompt": section.get("prompt", ""),
            "image": section.get("image", ""),
            "reference_strategy": reference_strategy,
            "reference_inputs": reference_inputs,
            "reference_entries": reference_entries,
        }
        rows.append(row)
        (sections_dir / f"{row['id']}.txt").write_text(row["prompt"] + "\n", encoding="utf-8")

    (out_dir / "sections.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    with (out_dir / "sections.csv").open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "id",
            "label",
            "role",
            "caption",
            "prompt",
            "image",
            "reference_strategy",
            "reference_paths",
            "reference_weights",
            "reference_priorities",
            "reference_crops",
            "reference_focuses",
            "reference_locks",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            csv_row = {key: row.get(key, "") for key in fieldnames}
            csv_row.update(reference_summary)
            writer.writerow(csv_row)

    character = spec.get("character", {})
    handoff = {
        "character_name": character.get("name", ""),
        "identity_lock": character.get("identity_lock", ""),
        "costume_lock": character.get("costume_lock", ""),
        "materials": character.get("materials", []),
        "props": character.get("props", []),
        "palette": character.get("palette", []),
        "world": character.get("world", ""),
        "avoid": character.get("avoid", []),
        "reference_inputs": spec.get("reference_inputs", {}),
        "reference_strategy": describe_reference_strategy(spec.get("reference_inputs", {})),
        "storyboard_global_lock": build_global_lock(spec),
    }
    (out_dir / "storyboard-handoff.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    save_json(out_dir / "character-design-spec.json", spec)


def main() -> None:
    args = parse_args()
    if args.command == "new-spec":
        new_spec(args.profile, args.language, args.out, args.title, args.subtitle)
    elif args.command == "inspect-brief":
        inspect_brief(args.profile, args.brief, args.out)
    elif args.command == "apply-brief":
        apply_brief(
            args.spec,
            args.out,
            args.brief,
            args.name,
            args.archetype,
            args.visual_theme,
            args.identity_lock,
            args.costume_lock,
            args.world,
            args.title,
            args.subtitle,
        )
    elif args.command == "attach-references":
        attach_references(
            args.spec,
            args.out,
            args.face_anchor,
            args.costume_anchor,
            args.prop_anchor,
            args.style_anchor,
            args.reference_image,
            args.reference_weight,
            args.reference_priority,
            args.reference_crop,
            args.reference_focus,
            args.reference_lock,
        )
    elif args.command == "render-layout":
        render_layout(args.spec, args.out)
    elif args.command == "validate-sheet":
        validate_sheet(args.spec, args.out)
    elif args.command == "export-prompts":
        export_prompts(args.spec, args.out_dir)


if __name__ == "__main__":
    main()
