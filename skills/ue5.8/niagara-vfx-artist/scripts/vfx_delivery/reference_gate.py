from __future__ import annotations

from pathlib import Path
from typing import Any

from .effect_state import acceptance_default, load_effect_record


def load_acceptance_payload(ctx, effect: str) -> dict[str, Any]:
    return load_effect_record(ctx, "reference-acceptance", effect, acceptance_default(effect))


def load_anchor_lock(ctx, effect: str) -> dict[str, Any]:
    return load_acceptance_payload(ctx, effect).get("anchor_lock", {})


def is_anchor_changed(previous_lock: dict[str, Any], new_entry_id: str, new_scope: str) -> bool:
    prev_entry_id = str(previous_lock.get("entry_id", "") or "")
    prev_scope = str(previous_lock.get("implementation_scope", "") or "")
    return prev_entry_id != new_entry_id or prev_scope.strip() != new_scope.strip()


def assert_anchor_ready(ctx, effect: str, require_entry_id: str = "", require_scope: str = "") -> dict[str, Any]:
    lock = load_anchor_lock(ctx, effect)
    entry_id = str(lock.get("entry_id", "") or "")
    if not entry_id:
        raise SystemExit("Reference gate failed: no locked anchor.")
    if not bool(lock.get("scope_confirmed", False)):
        raise SystemExit("Reference gate failed: locked anchor scope is not confirmed.")
    scope = str(lock.get("implementation_scope", "") or "").strip()
    if not scope:
        raise SystemExit("Reference gate failed: locked anchor is missing implementation scope.")
    cached_path = str(lock.get("cached_path", "") or "")
    if not cached_path or not Path(cached_path).exists():
        raise SystemExit("Reference gate failed: locked anchor has no durable local cached file.")
    if require_entry_id and entry_id != require_entry_id:
        raise SystemExit(f"Reference gate failed: locked anchor `{entry_id}` does not match required `{require_entry_id}`.")
    if require_scope and scope != require_scope.strip():
        raise SystemExit(f"Reference gate failed: locked scope `{scope}` does not match required `{require_scope}`.")
    return lock
