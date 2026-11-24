from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import ensure_dir, load_json, save_json, slugify, utc_now_iso


def category_root(ctx, category: str) -> Path:
    return ensure_dir(ctx.vfx_root / category)


def effect_record_path(ctx, category: str, effect: str, suffix: str = ".json") -> Path:
    return category_root(ctx, category) / f"{slugify(effect)}{suffix}"


def effect_folder(ctx, category: str, effect: str) -> Path:
    return ensure_dir(category_root(ctx, category) / slugify(effect))


def load_effect_record(ctx, category: str, effect: str, default_payload: dict[str, Any]) -> dict[str, Any]:
    return load_json(effect_record_path(ctx, category, effect), default_payload)


def save_effect_record(ctx, category: str, effect: str, payload: dict[str, Any]) -> Path:
    payload["updated_at"] = utc_now_iso()
    path = effect_record_path(ctx, category, effect)
    save_json(path, payload)
    return path


def acceptance_default(effect: str) -> dict[str, Any]:
    return {
        "version": 1,
        "effect_name": effect,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "anchor_lock": {
            "entry_id": "",
            "updated_at": "",
            "notes": "",
            "implementation_scope": "",
            "scope_confirmed": False,
            "authority": "",
            "clarity_score": 0,
            "cached_path": "",
            "revision": 0,
        },
        "reviews": [],
    }


def evidence_default(effect: str) -> dict[str, Any]:
    return {
        "version": 1,
        "effect_name": effect,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "suggestions": [],
        "attachments": [],
    }


def approvals_default(effect: str) -> dict[str, Any]:
    return {
        "version": 1,
        "effect_name": effect,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "reviews": [],
    }


def effect_preview_approvals_default(effect: str) -> dict[str, Any]:
    return {
        "version": 1,
        "effect_name": effect,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "reviews": [],
    }


def asset_plan_default(effect: str) -> dict[str, Any]:
    return {
        "version": 1,
        "effect_name": effect,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "platform": "",
        "naming": {},
        "budgets": {},
        "assets": {},
        "notes": "",
    }


def integration_default(effect: str) -> dict[str, Any]:
    return {
        "version": 1,
        "effect_name": effect,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "owner": "",
        "attachment_mode": "",
        "source_space": "",
        "sockets": [],
        "notifies": [],
        "user_parameters": [],
        "runtime_contract": [],
        "notes": "",
    }


def learning_default(effect: str) -> dict[str, Any]:
    return {
        "version": 1,
        "effect_name": effect,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "auto_summary": {},
        "success_rules": [],
        "failure_rules": [],
        "reuse_rules": [],
        "manual_lessons": [],
    }


def control_schema_default(effect: str) -> dict[str, Any]:
    return {
        "version": 1,
        "tool": "effect_control_schema",
        "effect_name": effect,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "system_path": "",
        "component_path": "",
        "material_paths": [],
        "controls": [],
        "groups": [],
        "notes": [],
        "sources": {},
    }


def control_presets_default(effect: str) -> dict[str, Any]:
    return {
        "version": 1,
        "tool": "control_preset",
        "effect_name": effect,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "presets": [],
    }
