from __future__ import annotations

from typing import Any


EFFECT_TYPE_CONTRACTS: dict[str, dict[str, Any]] = {
    "trail": {
        "label": "Ribbon / sword-air / wing echo trail",
        "required_renderers": ["Ribbon"],
        "require_attribute_reader_data_flow": False,
        "require_bounds": True,
        "forbid_test_emitters": True,
        "expected_roles": ["trail-receiver"],
        "visual_required": ["silhouette", "trail_direction", "dynamic_rhythm"],
    },
    "trail-attribute-reader": {
        "label": "Ribbon trail driven by Attribute Reader source/receiver flow",
        "required_renderers": ["Ribbon"],
        "require_attribute_reader_data_flow": True,
        "require_bounds": True,
        "forbid_test_emitters": True,
        "expected_roles": ["source", "attribute-reader-receiver", "trail-receiver"],
        "visual_required": ["silhouette", "trail_direction", "echo_spacing", "dynamic_rhythm"],
    },
    "fire": {
        "label": "Layered torch / flame effect",
        "required_renderers": ["Sprite"],
        "require_attribute_reader_data_flow": False,
        "require_bounds": True,
        "forbid_test_emitters": True,
        "expected_roles": ["generic", "receiver"],
        "visual_required": ["silhouette", "brightness", "density", "dynamic_rhythm"],
    },
    "explosion": {
        "label": "Burst / impact explosion",
        "required_renderers": ["Sprite"],
        "require_attribute_reader_data_flow": False,
        "require_bounds": True,
        "forbid_test_emitters": True,
        "expected_roles": ["generic", "receiver"],
        "visual_required": ["silhouette", "brightness", "density", "dynamic_rhythm"],
    },
    "shield": {
        "label": "Shield / aura / protective shell",
        "required_renderers": ["Mesh"],
        "require_attribute_reader_data_flow": False,
        "require_bounds": True,
        "forbid_test_emitters": True,
        "expected_roles": ["generic"],
        "visual_required": ["silhouette", "brightness", "width"],
    },
}


def effect_type_names() -> tuple[str, ...]:
    return tuple(sorted(EFFECT_TYPE_CONTRACTS))


def effect_type_contract(name: str) -> dict[str, Any]:
    clean = str(name or "").strip()
    if not clean:
        return {}
    try:
        return dict(EFFECT_TYPE_CONTRACTS[clean])
    except KeyError as exc:
        raise ValueError(f"Unknown effect type contract `{clean}`. Known: {', '.join(effect_type_names())}") from exc
