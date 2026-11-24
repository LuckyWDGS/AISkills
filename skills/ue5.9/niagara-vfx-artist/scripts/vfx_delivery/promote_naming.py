from __future__ import annotations

from typing import Any


PROMOTE_POLICY_MANUAL_ROOT = "manual-root"
PROMOTE_POLICY_VFX_EFFECT = "vfx-effect"
PROMOTE_POLICY_STUDIO_PROJECT_FAMILY_EFFECT = "studio-project-family-effect"
PROMOTE_POLICY_CHOICES = (
    PROMOTE_POLICY_MANUAL_ROOT,
    PROMOTE_POLICY_VFX_EFFECT,
    PROMOTE_POLICY_STUDIO_PROJECT_FAMILY_EFFECT,
)


def asset_token(text: str) -> str:
    import re

    token = re.sub(r"[^0-9A-Za-z_]+", "_", text.strip()).strip("_")
    if not token:
        token = "Asset"
    if token[0].isdigit():
        token = f"A_{token}"
    return token


def _normalize_base(promote_base: str) -> str:
    base = str(promote_base or "/Game/VFX").rstrip("/")
    return base or "/Game/VFX"


def _segment(label: str, raw: str, fallback: str) -> dict[str, str]:
    raw_value = str(raw or "").strip() or fallback
    return {
        "label": label,
        "raw": raw_value,
        "token": asset_token(raw_value),
    }


def _join_root(base: str, segments: list[dict[str, str]]) -> str:
    return f"{base}/{'/'.join(item['token'] for item in segments)}"


def derive_formal_promote_root(
    *,
    promote_base: str,
    promote_policy: str,
    promote_group: str = "",
    promote_effect_name: str,
    promote_studio: str = "",
    promote_project_name: str = "",
    promote_effect_family: str = "",
) -> str:
    return resolve_promote_details(
        effect=promote_effect_name,
        explicit_root="",
        promote_policy=promote_policy,
        promote_base=promote_base,
        promote_group=promote_group,
        promote_effect_name=promote_effect_name,
        promote_studio=promote_studio,
        promote_project_name=promote_project_name,
        promote_effect_family=promote_effect_family,
    ).get("promote_root", "")


def resolve_promote_root(
    *,
    effect: str,
    explicit_root: str,
    promote_policy: str,
    promote_base: str,
    promote_group: str = "",
    promote_effect_name: str = "",
    promote_studio: str = "",
    promote_project_name: str = "",
    promote_effect_family: str = "",
) -> str:
    return resolve_promote_details(
        effect=effect,
        explicit_root=explicit_root,
        promote_policy=promote_policy,
        promote_base=promote_base,
        promote_group=promote_group,
        promote_effect_name=promote_effect_name,
        promote_studio=promote_studio,
        promote_project_name=promote_project_name,
        promote_effect_family=promote_effect_family,
    ).get("promote_root", "")


def resolve_promote_details(
    *,
    effect: str,
    explicit_root: str,
    promote_policy: str,
    promote_base: str,
    promote_group: str = "",
    promote_effect_name: str = "",
    promote_studio: str = "",
    promote_project_name: str = "",
    promote_effect_family: str = "",
) -> dict[str, Any]:
    requested_policy = promote_policy or PROMOTE_POLICY_VFX_EFFECT
    if explicit_root:
        return {
            "requested_policy": requested_policy,
            "effective_policy": PROMOTE_POLICY_MANUAL_ROOT,
            "template": "manual-root",
            "base": "",
            "promote_root": explicit_root.rstrip("/"),
            "used_explicit_root": True,
            "segments": [],
        }

    if requested_policy == PROMOTE_POLICY_MANUAL_ROOT:
        return {
            "requested_policy": requested_policy,
            "effective_policy": PROMOTE_POLICY_MANUAL_ROOT,
            "template": "manual-root",
            "base": _normalize_base(promote_base),
            "promote_root": "",
            "used_explicit_root": False,
            "segments": [],
        }

    base = _normalize_base(promote_base)
    effect_name = promote_effect_name or effect or "Effect"

    if requested_policy == PROMOTE_POLICY_VFX_EFFECT:
        segments = [
            _segment("Group", promote_group, "Shared"),
            _segment("EffectName", effect_name, "Effect"),
        ]
        template = "Base/Group/EffectName"
    elif requested_policy == PROMOTE_POLICY_STUDIO_PROJECT_FAMILY_EFFECT:
        segments = [
            _segment("Studio", promote_studio, "Studio"),
            _segment("Project", promote_project_name, "Project"),
            _segment("EffectFamily", promote_effect_family, "Shared"),
            _segment("EffectName", effect_name, "Effect"),
        ]
        template = "Base/Studio/Project/EffectFamily/EffectName"
    else:
        raise ValueError(f"Unknown promote policy: {requested_policy}")

    return {
        "requested_policy": requested_policy,
        "effective_policy": requested_policy,
        "template": template,
        "base": base,
        "promote_root": _join_root(base, segments),
        "used_explicit_root": False,
        "segments": segments,
    }
