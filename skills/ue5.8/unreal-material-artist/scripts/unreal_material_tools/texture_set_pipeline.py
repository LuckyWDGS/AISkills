from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .core import default_report_path, ensure_dir, resolve_root_context, save_json, slugify, utc_now_iso, write_text
from .texture_asset_report import IMAGE_EXTENSIONS, image_info, is_power_of_two, next_power_of_two


SLOT_ORDER = ("base_color", "normal", "rma", "opacity", "emissive")
SOURCE_CHANNEL_ORDER = ("roughness", "metallic", "ao")
PACKED_CONVENTIONS = {
    "RMA": {"R": "roughness", "G": "metallic", "B": "ao"},
    "ORM": {"R": "ao", "G": "roughness", "B": "metallic"},
    "MRA": {"R": "metallic", "G": "roughness", "B": "ao"},
}

SLOT_DEFS: dict[str, dict[str, Any]] = {
    "base_color": {
        "label": "BaseColor",
        "aliases": ("basecolor", "base_color", "albedo", "diffuse", "diff", "bc", "d"),
        "expected_suffixes": ("BaseColor", "BC", "Albedo", "Diffuse"),
        "file_role": "albedo",
        "import_role": "albedo",
        "flavor": "color",
        "required": True,
        "expected_import": {
            "srgb": True,
            "compression_settings": "TC_DEFAULT",
            "sampler_type": "Color",
            "notes": "Color/albedo art should usually be sampled as sRGB color.",
        },
    },
    "normal": {
        "label": "Normal",
        "aliases": ("normal", "nrm", "norm", "nor", "n"),
        "expected_suffixes": ("Normal", "N", "NRM"),
        "file_role": "normal",
        "import_role": "normal",
        "flavor": "data",
        "required": True,
        "expected_import": {
            "srgb": False,
            "compression_settings": "TC_NORMALMAP",
            "sampler_type": "Normal",
            "notes": "Normal maps should use normal compression and sRGB disabled.",
        },
    },
    "rma": {
        "label": "RMA/ORM Packed",
        "aliases": ("rma", "orm", "mra", "packed", "pack", "maskpack", "masks", "arm"),
        "expected_suffixes": ("RMA", "ORM", "MRA", "Packed", "Masks"),
        "file_role": "packed",
        "import_role": "packed",
        "flavor": "mask",
        "required": True,
        "expected_import": {
            "srgb": False,
            "compression_settings": "TC_MASKS",
            "sampler_type": "Masks",
            "notes": "Packed scalar data should use sRGB disabled and mask/data compression.",
        },
    },
    "opacity": {
        "label": "Opacity",
        "aliases": ("opacity", "alpha", "mask", "opacitymask", "cutout", "transparency"),
        "expected_suffixes": ("Opacity", "OpacityMask", "Alpha", "Mask"),
        "file_role": "mask",
        "import_role": "mask",
        "flavor": "mask",
        "required": False,
        "expected_import": {
            "srgb": False,
            "compression_settings": "TC_MASKS",
            "sampler_type": "Masks",
            "notes": "Opacity and cutout masks should be scalar data, not color textures.",
        },
    },
    "emissive": {
        "label": "Emissive",
        "aliases": ("emissive", "emission", "emit", "glow", "e"),
        "expected_suffixes": ("Emissive", "Emission", "E", "Glow"),
        "file_role": "albedo",
        "import_role": "emissive",
        "flavor": "color",
        "required": False,
        "expected_import": {
            "srgb": True,
            "compression_settings": "TC_DEFAULT",
            "sampler_type": "Color",
            "notes": "Emissive color art usually stays sRGB; mask-like emissive ramps should be documented separately.",
        },
    },
}

SOURCE_CHANNEL_DEFS: dict[str, dict[str, Any]] = {
    "roughness": {
        "aliases": ("roughness", "rough", "rgh"),
        "file_role": "mask",
        "expected_import": SLOT_DEFS["opacity"]["expected_import"],
    },
    "metallic": {
        "aliases": ("metallic", "metalness", "metal", "mtl"),
        "file_role": "mask",
        "expected_import": SLOT_DEFS["opacity"]["expected_import"],
    },
    "ao": {
        "aliases": ("ao", "occlusion", "ambientocclusion", "ambient_occlusion"),
        "file_role": "mask",
        "expected_import": SLOT_DEFS["opacity"]["expected_import"],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"JSON file does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Failed to read JSON file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return payload


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def collect_image_files(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            found.extend(item for item in path.rglob("*") if item.suffix.lower() in IMAGE_EXTENSIONS)
        elif path.exists() or path.suffix.lower() in IMAGE_EXTENSIONS:
            found.append(path)
    return sorted(found)


def _tokens(path: Path) -> set[str]:
    stem = path.stem.lower()
    parts = re.split(r"[^a-z0-9]+", stem)
    tokens = {part for part in parts if part}
    compact = re.sub(r"[^a-z0-9]+", "", stem)
    tokens.add(compact)
    return tokens


def _parts(path: Path) -> list[str]:
    return [part for part in re.split(r"[^a-z0-9]+", path.stem.lower()) if part]


def detect_slot(path: Path) -> tuple[str | None, int, str]:
    tokens = _tokens(path)
    parts = _parts(path)
    stem = path.stem.lower()
    best_slot: str | None = None
    best_score = 0
    best_alias = ""
    for slot, definition in {**SLOT_DEFS, **SOURCE_CHANNEL_DEFS}.items():
        for alias in definition["aliases"]:
            alias_lower = alias.lower()
            score = 0
            if alias_lower in tokens:
                score = 100 + len(alias_lower)
                if parts and parts[-1] == alias_lower:
                    score += 50
            elif len(alias_lower) > 2 and alias_lower in stem:
                score = 50 + len(alias_lower)
            if len(alias_lower) <= 2 and (not parts or parts[-1] != alias_lower):
                score = 0
            if score > best_score:
                best_slot = slot
                best_score = score
                best_alias = alias
    return best_slot, best_score, best_alias


def make_entry(file_path: str = "", asset_path: str = "", source: str = "", note: str = "") -> dict[str, Any]:
    return {
        "file_path": file_path,
        "asset_path": asset_path,
        "source": source,
        "note": note,
        "alternates": [],
    }


def _entry_from_spec(value: Any, source: str) -> dict[str, Any]:
    if isinstance(value, str):
        return make_entry(file_path=value, source=source)
    if isinstance(value, dict):
        return make_entry(
            file_path=str(value.get("file") or value.get("path") or value.get("file_path") or ""),
            asset_path=str(value.get("asset") or value.get("asset_path") or value.get("texture_path") or ""),
            source=source,
            note=str(value.get("note") or ""),
        )
    return make_entry(source=source)


def load_spec_entries(path: str | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    payload = load_json(Path(path))
    textures = payload.get("textures") or payload.get("texture_set") or payload.get("slots") or {}
    if not isinstance(textures, dict):
        raise SystemExit("Texture set spec must contain an object at `textures`, `texture_set`, or `slots`.")
    entries: dict[str, dict[str, Any]] = {}
    aliases = {
        "basecolor": "base_color",
        "base_color": "base_color",
        "albedo": "base_color",
        "normal": "normal",
        "rma": "rma",
        "orm": "rma",
        "packed": "rma",
        "opacity": "opacity",
        "opacity_mask": "opacity",
        "emissive": "emissive",
        "roughness": "roughness",
        "metallic": "metallic",
        "ao": "ao",
    }
    for key, value in textures.items():
        normalized = aliases.get(str(key).lower(), str(key).lower())
        if normalized in SLOT_DEFS or normalized in SOURCE_CHANNEL_DEFS:
            entries[normalized] = _entry_from_spec(value, f"spec:{path}")
    return entries


def apply_explicit_args(entries: dict[str, dict[str, Any]], args: argparse.Namespace) -> None:
    file_fields = {
        "base_color": args.base_color,
        "normal": args.normal,
        "rma": args.rma,
        "opacity": args.opacity,
        "emissive": args.emissive,
        "roughness": args.roughness,
        "metallic": args.metallic,
        "ao": args.ao,
    }
    asset_fields = {
        "base_color": args.base_color_asset,
        "normal": args.normal_asset,
        "rma": args.rma_asset,
        "opacity": args.opacity_asset,
        "emissive": args.emissive_asset,
        "roughness": args.roughness_asset,
        "metallic": args.metallic_asset,
        "ao": args.ao_asset,
    }
    for slot in (*SLOT_ORDER, *SOURCE_CHANNEL_ORDER):
        file_path = file_fields.get(slot)
        asset_path = asset_fields.get(slot)
        if file_path or asset_path:
            existing = entries.get(slot, make_entry(source="explicit"))
            entries[slot] = {
                **existing,
                "file_path": file_path or existing.get("file_path", ""),
                "asset_path": asset_path or existing.get("asset_path", ""),
                "source": "explicit",
            }


def scan_entries(entries: dict[str, dict[str, Any]], scan_paths: list[str]) -> dict[str, list[dict[str, Any]]]:
    detected: dict[str, list[dict[str, Any]]] = {}
    for path in collect_image_files(scan_paths):
        slot, score, alias = detect_slot(path)
        if not slot:
            detected.setdefault("unassigned", []).append({"file_path": str(path), "score": score, "alias": alias})
            continue
        row = {"file_path": str(path), "score": score, "alias": alias}
        detected.setdefault(slot, []).append(row)
        if slot not in entries or not entries[slot].get("file_path"):
            entries[slot] = make_entry(file_path=str(path), source="scan", note=f"matched alias `{alias}`")
        else:
            entries[slot].setdefault("alternates", []).append(row)
    return detected


def role_required(slot: str, args: argparse.Namespace) -> bool:
    if slot == "base_color" and args.no_require_base_color:
        return False
    if slot == "normal" and args.no_require_normal:
        return False
    if slot == "rma" and args.no_require_rma:
        return False
    if slot == "opacity" and args.require_opacity:
        return True
    if slot == "emissive" and args.require_emissive:
        return True
    return bool(SLOT_DEFS[slot]["required"])


def channel_stats(info: dict[str, Any]) -> dict[str, Any]:
    stats = info.get("stats") if isinstance(info.get("stats"), dict) else {}
    mins = stats.get("channel_min") or []
    maxs = stats.get("channel_max") or []
    means = stats.get("channel_mean") or []
    channels = {}
    for index, name in enumerate(("R", "G", "B", "A")):
        channels[name] = {
            "min": mins[index] if len(mins) > index else None,
            "max": maxs[index] if len(maxs) > index else None,
            "mean": means[index] if len(means) > index else None,
            "range": (maxs[index] - mins[index]) if len(mins) > index and len(maxs) > index else None,
        }
    return channels


def luminance_range(info: dict[str, Any]) -> float | None:
    channels = channel_stats(info)
    ranges = [channels[key]["range"] for key in ("R", "G", "B") if channels[key]["range"] is not None]
    if not ranges:
        return None
    return max(float(value) for value in ranges)


def compression_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def expected_suffix_ok(path: str, slot: str) -> bool:
    if not path:
        return True
    stem = Path(path).stem.lower()
    tokens = _tokens(Path(path))
    for suffix in SLOT_DEFS[slot]["expected_suffixes"]:
        lowered = suffix.lower()
        if lowered in tokens or lowered in stem:
            return True
    return False


def vfx_suffix_ok(path: str) -> bool:
    if not path:
        return True
    stem = Path(path).stem.lower()
    parts = _parts(Path(path))
    compact = re.sub(r"[^a-z0-9]+", "", stem)
    return bool((parts and parts[-1] == "vfx") or compact.endswith("vfx"))


def slot_findings(
    *,
    slot: str,
    entry: dict[str, Any],
    info: dict[str, Any],
    import_info: dict[str, Any] | None,
    convention: str,
    required: bool,
    max_dimension: int,
    require_vfx_suffix: bool = False,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(severity: str, rule: str, message: str, recommendation: str = "") -> None:
        findings.append({"severity": severity, "rule": rule, "message": message, "recommendation": recommendation})

    file_path = entry.get("file_path", "")
    asset_path = entry.get("asset_path", "")
    if required and not file_path and not asset_path:
        add("error", "missing_required_slot", f"Required texture slot `{slot}` is missing.")
        return findings
    if not file_path and not asset_path:
        return findings
    if file_path and not info.get("exists"):
        add("error", "missing_file", f"Texture file does not exist: {file_path}")
        return findings
    if entry.get("alternates"):
        add("warning", "duplicate_candidates", f"Multiple candidate files detected for `{slot}`; confirm the selected one is correct.")
    if file_path and not expected_suffix_ok(file_path, slot):
        add(
            "warning",
            "naming_suffix",
            f"`{Path(file_path).name}` does not use an expected {SLOT_DEFS[slot]['label']} suffix.",
            f"Prefer one of: {', '.join(SLOT_DEFS[slot]['expected_suffixes'])}.",
        )
    if file_path and require_vfx_suffix and not vfx_suffix_ok(file_path):
        add(
            "warning",
            "vfx_suffix",
            f"`{Path(file_path).name}` is used by a VFX/Unlit texture set but does not end with `VFX`.",
            "Prefer names like `T_FireFlipbook_VFX` or `T_SmokeOpacity_VFX` for Niagara-facing texture assets.",
        )
    width = info.get("width")
    height = info.get("height")
    if isinstance(width, int) and isinstance(height, int):
        if width > max_dimension or height > max_dimension:
            add("warning", "oversized", f"Texture exceeds max dimension {max_dimension}.")
        if slot != "emissive" and not (is_power_of_two(width) and is_power_of_two(height)):
            rec = f"Consider {next_power_of_two(width)}x{next_power_of_two(height)} unless this is intentional."
            add("warning", "non_power_of_two", "Texture is not power-of-two.", rec)
    channels = channel_stats(info)
    if slot == "normal" and info.get("exists"):
        blue_mean = channels.get("B", {}).get("mean")
        if blue_mean is not None and blue_mean < 120:
            add("warning", "normal_blue_channel", "Normal map blue channel mean looks low for a tangent-space normal.")
    if slot == "rma" and info.get("exists"):
        semantics = PACKED_CONVENTIONS[convention]
        ranges = [channels[key]["range"] for key in ("R", "G", "B") if channels[key]["range"] is not None]
        means = [channels[key]["mean"] for key in ("R", "G", "B") if channels[key]["mean"] is not None]
        if len(ranges) >= 3 and max(ranges) <= 2:
            add("info", "flat_packed_channels", "Packed RMA/ORM channels are almost flat; confirm this is intentional.")
        if len(means) >= 3 and max(means) - min(means) <= 2:
            add(
                "warning",
                "packed_looks_grayscale",
                "Packed texture RGB channels look nearly identical.",
                f"Expected {convention}: " + ", ".join(f"{key}={value}" for key, value in semantics.items()),
            )
    if slot == "opacity" and info.get("exists"):
        luma_range = luminance_range(info)
        alpha_range = channels.get("A", {}).get("range")
        if (luma_range is not None and luma_range <= 2) and (alpha_range is None or alpha_range <= 2):
            add("warning", "opacity_no_mask_signal", "Opacity texture appears to have little or no mask range.")
    if slot == "emissive" and info.get("exists"):
        if luminance_range(info) is not None and luminance_range(info) <= 2:
            add("info", "flat_emissive", "Emissive texture is nearly flat; confirm it is not meant to be a mask or scalar.")

    expected = SLOT_DEFS[slot]["expected_import"]
    if import_info:
        if "srgb" in import_info and bool(import_info.get("srgb")) != bool(expected["srgb"]):
            add("warning", "import_srgb", f"Imported sRGB is `{import_info.get('srgb')}`, expected `{expected['srgb']}`.")
        current_compression = import_info.get("compression_settings")
        if current_compression and compression_key(current_compression) != compression_key(expected["compression_settings"]):
            add(
                "warning",
                "import_compression",
                f"Imported compression is `{current_compression}`, expected `{expected['compression_settings']}`.",
            )
        for finding in import_info.get("findings") or []:
            if isinstance(finding, dict) and str(finding.get("severity") or "").lower() in {"error", "warning"}:
                add(
                    str(finding.get("severity") or "warning").lower(),
                    f"import_audit:{finding.get('rule')}",
                    str(finding.get("message") or ""),
                )

    return findings


def load_import_reports(paths: list[str]) -> dict[str, dict[str, Any]]:
    by_asset: dict[str, dict[str, Any]] = {}
    for raw in paths:
        payload = load_json(Path(raw))
        if payload.get("tool") not in {"texture_import_audit", "texture_import_fix", "texture_import_fix_batch"}:
            continue
        if payload.get("tool") == "texture_import_audit":
            for item in payload.get("textures") or []:
                if isinstance(item, dict) and item.get("asset_path"):
                    by_asset[str(item["asset_path"])] = item
        elif payload.get("tool") == "texture_import_fix":
            after = payload.get("after") if isinstance(payload.get("after"), dict) else {}
            asset_path = str(after.get("asset_path") or payload.get("texture_path") or "")
            if asset_path:
                by_asset[asset_path] = after
        elif payload.get("tool") == "texture_import_fix_batch":
            for item in payload.get("items") or []:
                if not isinstance(item, dict):
                    continue
                after = item.get("after") if isinstance(item.get("after"), dict) else {}
                asset_path = str(after.get("asset_path") or item.get("texture_path") or "")
                if asset_path:
                    by_asset[asset_path] = after
    return by_asset


def analyze_slot(
    slot: str,
    entry: dict[str, Any],
    import_reports: dict[str, dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    definition = SLOT_DEFS[slot]
    file_path = str(entry.get("file_path") or "")
    info = image_info(Path(file_path)) if file_path else {"exists": False}
    asset_path = str(entry.get("asset_path") or "")
    import_info = import_reports.get(asset_path) if asset_path else None
    required = role_required(slot, args)
    findings = slot_findings(
        slot=slot,
        entry=entry,
        info=info,
        import_info=import_info,
        convention=args.packed_convention,
        required=required,
        max_dimension=args.max_dimension,
        require_vfx_suffix=args.profile == "vfx-unlit",
    )
    return {
        "slot": slot,
        "label": definition["label"],
        "required": required,
        "file_path": file_path,
        "asset_path": asset_path,
        "source": entry.get("source", ""),
        "note": entry.get("note", ""),
        "alternates": entry.get("alternates") or [],
        "expected_import": definition["expected_import"],
        "file": info,
        "import_audit": import_info or {},
        "findings": findings,
    }


def analyze_source_channel(slot: str, entry: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    file_path = str(entry.get("file_path") or "")
    info = image_info(Path(file_path)) if file_path else {"exists": False}
    findings: list[dict[str, Any]] = []
    if file_path and not info.get("exists"):
        findings.append({"severity": "error", "rule": "missing_file", "message": f"Source channel file does not exist: {file_path}"})
    if file_path and luminance_range(info) is not None and luminance_range(info) <= 2:
        findings.append({"severity": "info", "rule": "flat_source_channel", "message": f"`{slot}` source channel is nearly flat; confirm this is intentional."})
    return {
        "slot": slot,
        "file_path": file_path,
        "asset_path": str(entry.get("asset_path") or ""),
        "source": entry.get("source", ""),
        "file": info,
        "expected_import": SOURCE_CHANNEL_DEFS[slot]["expected_import"],
        "findings": findings,
    }


def dimensions_key(slot_report: dict[str, Any]) -> tuple[int, int] | None:
    file_info = slot_report.get("file") or {}
    width = file_info.get("width")
    height = file_info.get("height")
    if isinstance(width, int) and isinstance(height, int):
        return width, height
    return None


def set_findings(slots: dict[str, dict[str, Any]], source_channels: dict[str, dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(severity: str, rule: str, message: str, recommendation: str = "") -> None:
        findings.append({"severity": severity, "rule": rule, "message": message, "recommendation": recommendation})

    present_required_dims = {
        slot: dimensions_key(report)
        for slot, report in slots.items()
        if report.get("required") and (report.get("file_path") or report.get("asset_path"))
    }
    present_required_dims = {slot: dims for slot, dims in present_required_dims.items() if dims}
    if len(set(present_required_dims.values())) > 1:
        add(
            "warning",
            "required_dimension_mismatch",
            f"Required texture slots do not share one resolution: {present_required_dims}",
            "Prefer matching BaseColor/Normal/RMA dimensions unless a deliberate memory optimization is documented.",
        )

    base_dims = dimensions_key(slots.get("base_color") or {})
    for slot in ("normal", "rma", "opacity", "emissive"):
        dims = dimensions_key(slots.get(slot) or {})
        if base_dims and dims and dims != base_dims:
            severity = "warning" if slot in {"normal", "rma"} else "info"
            add(severity, f"{slot}_size_differs_from_base_color", f"`{slot}` size {dims} differs from BaseColor size {base_dims}.")

    rma_present = bool(slots.get("rma", {}).get("file_path") or slots.get("rma", {}).get("asset_path"))
    channels_present = [slot for slot, report in source_channels.items() if report.get("file_path") or report.get("asset_path")]
    if not rma_present and channels_present:
        if all(slot in channels_present for slot in SOURCE_CHANNEL_ORDER):
            add(
                "warning",
                "rma_missing_but_packable",
                "RMA/ORM packed texture is missing, but Roughness/Metallic/AO source channels are present.",
                "Use --pack-rma-out or channel_packer.py to create the packed texture, then rerun the set audit.",
            )
        else:
            add("warning", "partial_rma_sources", f"Only partial packed-channel sources are present: {channels_present}.")

    if slots.get("opacity", {}).get("file_path") and slots.get("rma", {}).get("file_path"):
        add(
            "info",
            "opacity_can_pack_to_alpha",
            "Opacity is separate while RMA/ORM exists.",
            "If the material can consume alpha from the packed map, consider packing opacity into A to reduce one sample.",
        )

    return findings


def severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"errors": 0, "warnings": 0, "info": 0}
    for finding in findings:
        severity = str(finding.get("severity") or "info").lower()
        if severity == "error":
            counts["errors"] += 1
        elif severity == "warning":
            counts["warnings"] += 1
        else:
            counts["info"] += 1
    return counts


def build_import_fix_spec(report: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for slot, slot_report in (report.get("slots") or {}).items():
        asset_path = str(slot_report.get("asset_path") or "")
        if not asset_path:
            continue
        definition = SLOT_DEFS[slot]
        items.append(
            {
                "texture_path": asset_path,
                "role": definition["import_role"],
                "flavor": definition["flavor"],
                "slot": slot,
            }
        )
    return {
        "effect": report.get("effect") or "texture-set",
        "layer": report.get("layer") or "",
        "source_report": report.get("output_path") or "",
        "defaults": {
            "max_dimension": (report.get("options") or {}).get("max_dimension", 2048),
        },
        "items": items,
    }


def pack_rma(args: argparse.Namespace, entries: dict[str, dict[str, Any]], out_path: Path) -> dict[str, Any]:
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:
        return {"requested": True, "output_path": str(out_path), "error": f"Pillow is required for packing: {exc}"}

    convention = PACKED_CONVENTIONS[args.packed_convention]
    channel_to_source = {channel: role for channel, role in convention.items()}
    source_paths: dict[str, str] = {}
    for channel, role in channel_to_source.items():
        source_paths[channel] = str((entries.get(role) or {}).get("file_path") or "")
    if args.pack_opacity_alpha:
        source_paths["A"] = str((entries.get("opacity") or {}).get("file_path") or "")

    missing = [role for role in channel_to_source.values() if not (entries.get(role) or {}).get("file_path")]
    if missing:
        return {
            "requested": True,
            "output_path": str(out_path),
            "error": f"Missing source channels for packing: {', '.join(missing)}",
            "sources": source_paths,
        }

    first_path = Path(next(path for path in source_paths.values() if path))
    if not first_path.exists():
        return {"requested": True, "output_path": str(out_path), "error": f"Source file does not exist: {first_path}", "sources": source_paths}
    base = Image.open(first_path).convert("RGBA")
    target_size = base.size

    def load_luma(path_text: str, fill: int = 255) -> Any:
        if not path_text:
            return Image.new("L", target_size, fill)
        image = Image.open(path_text).convert("RGBA")
        if image.size != target_size:
            image = image.resize(target_size, Image.Resampling.LANCZOS)
        return image.convert("L")

    bands = [load_luma(source_paths.get(channel, ""), 255 if channel == "A" else 0) for channel in ("R", "G", "B", "A")]
    packed = Image.merge("RGBA", bands)
    ensure_dir(out_path.parent)
    packed.save(out_path)
    return {
        "requested": True,
        "output_path": str(out_path),
        "error": "",
        "convention": args.packed_convention,
        "channel_semantics": convention,
        "sources": source_paths,
        "width": target_size[0],
        "height": target_size[1],
    }


def build_audit(args: argparse.Namespace) -> tuple[dict[str, Any], Path, dict[str, Any] | None, Path | None]:
    ctx = resolve_root_context(args.root)
    entries = load_spec_entries(args.spec)
    scan_result = scan_entries(entries, args.scan)
    apply_explicit_args(entries, args)
    pack_report: dict[str, Any] = {}
    if args.pack_rma_out:
        pack_report = pack_rma(args, entries, Path(args.pack_rma_out))
        has_rma_file = bool((entries.get("rma") or {}).get("file_path"))
        if not pack_report.get("error") and not has_rma_file:
            entries["rma"] = make_entry(
                file_path=str(pack_report.get("output_path") or ""),
                source="pack_rma",
                note=f"generated from {args.packed_convention} source channels",
            )
    import_reports = load_import_reports(args.import_audit_report)

    slots = {
        slot: analyze_slot(slot, entries.get(slot, make_entry()), import_reports, args)
        for slot in SLOT_ORDER
    }
    source_channels = {
        slot: analyze_source_channel(slot, entries.get(slot, make_entry()), args)
        for slot in SOURCE_CHANNEL_ORDER
        if slot in entries
    }

    all_findings: list[dict[str, Any]] = []
    for slot_report in slots.values():
        for finding in slot_report.get("findings") or []:
            all_findings.append({"scope": slot_report["slot"], **finding})
    for channel_report in source_channels.values():
        for finding in channel_report.get("findings") or []:
            all_findings.append({"scope": channel_report["slot"], **finding})
    if args.profile == "vfx-unlit":
        for row in scan_result.get("unassigned") or []:
            file_path = str(row.get("file_path") or "")
            if file_path and not vfx_suffix_ok(file_path):
                all_findings.append(
                    {
                        "scope": "set",
                        "severity": "warning",
                        "rule": "vfx_suffix",
                        "message": f"`{Path(file_path).name}` is an unassigned VFX texture candidate but does not end with `VFX`.",
                        "recommendation": "Prefer names like `T_FireFlipbook_VFX` for Niagara/SubUV atlases and other VFX texture assets.",
                    }
                )
    all_findings.extend({"scope": "set", **finding} for finding in set_findings(slots, source_channels, args))
    if pack_report.get("error"):
        all_findings.append(
            {
                "scope": "pack_rma",
                "severity": "error",
                "rule": "pack_failed",
                "message": pack_report["error"],
                "recommendation": "Provide all source channels or remove --pack-rma-out.",
            }
        )

    counts = severity_counts(all_findings)
    effect = args.effect or "TextureSet"
    layer = args.layer or "Main"
    report = {
        "tool": "texture_set_pipeline",
        "version": 1,
        "generated_utc": utc_now_iso(),
        "effect": effect,
        "layer": layer,
        "profile": args.profile,
        "packed_convention": args.packed_convention,
        "packed_channel_semantics": PACKED_CONVENTIONS[args.packed_convention],
        "source": {
            "spec": args.spec or "",
            "scan": args.scan,
            "detected": scan_result,
            "import_audit_reports": args.import_audit_report,
        },
        "options": {
            "max_dimension": args.max_dimension,
            "require_base_color": role_required("base_color", args),
            "require_normal": role_required("normal", args),
            "require_rma": role_required("rma", args),
            "require_opacity": role_required("opacity", args),
            "require_emissive": role_required("emissive", args),
            "require_vfx_suffix": args.profile == "vfx-unlit",
        },
        "slots": slots,
        "source_channels": source_channels,
        "findings": all_findings,
        "fix_plan": {
            "import_fix_spec_path": "",
            "pack_rma": pack_report,
            "next_actions": [],
        },
        "gate": {
            "passed": counts["errors"] == 0,
            "ready_for_import": counts["errors"] == 0 and counts["warnings"] == 0,
            "counts": counts,
        },
    }

    stem = slugify(f"{effect}-{layer}")
    out = Path(args.out) if args.out else default_report_path(ctx, "texture-sets", stem, "texture-set-pipeline", ".json")
    report["output_path"] = str(out)

    next_actions: list[str] = []
    if any(finding["rule"] == "pack_failed" for finding in report["findings"]):
        next_actions.append("Fix the RMA packing inputs and rerun texture_set_pipeline.py.")
    if any(finding["rule"] == "missing_required_slot" for finding in report["findings"]):
        next_actions.append("Provide or generate the missing required texture slots, then rerun texture_set_pipeline.py.")
    if any(finding["rule"] == "rma_missing_but_packable" for finding in report["findings"]):
        next_actions.append("Pack Roughness/Metallic/AO into the configured packed convention and rerun the audit.")
    if any(str(finding["rule"]).startswith("import_") or str(finding["rule"]).startswith("import_audit:") for finding in report["findings"]):
        next_actions.append("Run texture_import_fix.py with the emitted batch spec, then rerun texture_import_audit.py.")
    if any(finding["rule"] == "required_dimension_mismatch" for finding in report["findings"]):
        next_actions.append("Resize or intentionally document mismatched texture resolutions before material hookup.")
    if not next_actions:
        next_actions.append("Texture set has no blocking errors; use the emitted import settings when bringing it into UE.")
    report["fix_plan"]["next_actions"] = next_actions

    fix_spec = build_import_fix_spec(report)
    fix_spec_path: Path | None = None
    if args.emit_import_fix_spec and fix_spec["items"]:
        fix_spec_path = out.with_name("texture-import-fix-batch-spec.json")
        report["fix_plan"]["import_fix_spec_path"] = str(fix_spec_path)
        fix_spec["source_report"] = str(out)
    return report, out, fix_spec if fix_spec_path else None, fix_spec_path


def render_markdown(report: dict[str, Any]) -> str:
    gate = report.get("gate") or {}
    lines = [
        f"# Texture Set Pipeline: {report.get('effect')} / {report.get('layer')}",
        "",
        f"- Passed: `{gate.get('passed')}`",
        f"- Ready for import: `{gate.get('ready_for_import')}`",
        f"- Errors: `{(gate.get('counts') or {}).get('errors', 0)}`",
        f"- Warnings: `{(gate.get('counts') or {}).get('warnings', 0)}`",
        f"- Packed convention: `{report.get('packed_convention')}`",
        f"- Import fix spec: `{(report.get('fix_plan') or {}).get('import_fix_spec_path') or 'not emitted'}`",
        "",
        "## Slots",
        "",
    ]
    for slot in SLOT_ORDER:
        item = (report.get("slots") or {}).get(slot) or {}
        file_info = item.get("file") or {}
        lines.append(
            f"- `{slot}` required=`{item.get('required')}` file=`{item.get('file_path') or 'missing'}` "
            f"asset=`{item.get('asset_path') or 'unset'}` size=`{file_info.get('width')}x{file_info.get('height')}` "
            f"findings=`{len(item.get('findings') or [])}`"
        )
    if report.get("source_channels"):
        lines.extend(["", "## Source Channels", ""])
        for slot, item in report["source_channels"].items():
            file_info = item.get("file") or {}
            lines.append(f"- `{slot}` file=`{item.get('file_path')}` size=`{file_info.get('width')}x{file_info.get('height')}`")

    pack = (report.get("fix_plan") or {}).get("pack_rma") or {}
    if pack:
        lines.extend(["", "## Packed Output", ""])
        if pack.get("error"):
            lines.append(f"- Error: {pack.get('error')}")
        else:
            lines.append(f"- Output: `{pack.get('output_path')}`")
            lines.append(f"- Convention: `{pack.get('convention')}`")

    lines.extend(["", "## Findings", ""])
    findings = report.get("findings") or []
    if findings:
        for finding in findings[:40]:
            lines.append(f"- [{finding.get('severity')}] `{finding.get('scope')}.{finding.get('rule')}` {finding.get('message')}")
            if finding.get("recommendation"):
                lines.append(f"  Recommendation: {finding.get('recommendation')}")
    else:
        lines.append("- No texture-set findings.")
    lines.extend(["", "## Next Actions", ""])
    for item in (report.get("fix_plan") or {}).get("next_actions") or []:
        lines.append(f"- {item}")
    return "\n".join(lines).rstrip() + "\n"


def command_audit(args: argparse.Namespace) -> int:
    report, out, fix_spec, fix_spec_path = build_audit(args)
    save_json(out, report)
    if fix_spec and fix_spec_path:
        save_json(fix_spec_path, fix_spec)
    if args.markdown:
        write_text(out.with_suffix(".md"), render_markdown(report))
    print(out)
    return 1 if args.strict and not report["gate"]["passed"] else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit and plan fixes for a full BaseColor/Normal/RMA/Opacity/Emissive texture set.")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Audit a texture set from explicit paths, a folder scan, or a JSON spec.")
    audit.add_argument("--root", default="auto")
    audit.add_argument("--effect")
    audit.add_argument("--layer")
    audit.add_argument("--profile", default="surface-pbr", choices=["surface-pbr", "masked-surface", "vfx-unlit", "custom"])
    audit.add_argument("--packed-convention", default="RMA", choices=sorted(PACKED_CONVENTIONS))
    audit.add_argument("--spec")
    audit.add_argument("--scan", action="append", default=[])
    audit.add_argument("--base-color")
    audit.add_argument("--normal")
    audit.add_argument("--rma")
    audit.add_argument("--opacity")
    audit.add_argument("--emissive")
    audit.add_argument("--roughness")
    audit.add_argument("--metallic")
    audit.add_argument("--ao")
    audit.add_argument("--base-color-asset")
    audit.add_argument("--normal-asset")
    audit.add_argument("--rma-asset")
    audit.add_argument("--opacity-asset")
    audit.add_argument("--emissive-asset")
    audit.add_argument("--roughness-asset")
    audit.add_argument("--metallic-asset")
    audit.add_argument("--ao-asset")
    audit.add_argument("--import-audit-report", action="append", default=[])
    audit.add_argument("--max-dimension", type=int, default=2048)
    audit.add_argument("--no-require-base-color", action="store_true")
    audit.add_argument("--no-require-normal", action="store_true")
    audit.add_argument("--no-require-rma", action="store_true")
    audit.add_argument("--require-opacity", action="store_true")
    audit.add_argument("--require-emissive", action="store_true")
    audit.add_argument("--emit-import-fix-spec", action="store_true")
    audit.add_argument("--pack-rma-out")
    audit.add_argument("--pack-opacity-alpha", action="store_true")
    audit.add_argument("--out")
    audit.add_argument("--markdown", action="store_true")
    audit.add_argument("--strict", action="store_true")
    audit.set_defaults(func=command_audit)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
