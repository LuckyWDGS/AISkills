from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VFX_DIR_NAME = "vfx-delivery"


@dataclass(slots=True)
class RootContext:
    project_root: Path
    session_root: Path
    vfx_root: Path
    skill_root: Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def skill_root() -> Path:
    return Path(__file__).resolve().parents[2]


def slugify(text: str) -> str:
    compact = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "-", text.strip())
    compact = re.sub(r"-{2,}", "-", compact).strip("-._")
    return compact or "unnamed"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_project_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    markers = (
        lambda p: (p / ".codex" / "session").exists(),
        lambda p: any(p.glob("*.uproject")),
        lambda p: (p / ".git").exists(),
    )
    for candidate in (start, *start.parents):
        if any(check(candidate) for check in markers):
            return candidate
    return start


def resolve_root_context(root: str | Path | None = None) -> RootContext:
    if root is None or str(root).lower() == "auto":
        project_root = resolve_project_root()
    else:
        project_root = Path(root).expanduser().resolve()
    session_root = ensure_dir(project_root / ".codex" / "session")
    vfx_root = ensure_dir(session_root / VFX_DIR_NAME)
    return RootContext(
        project_root=project_root,
        session_root=session_root,
        vfx_root=vfx_root,
        skill_root=skill_root(),
    )


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def default_report_path(ctx: RootContext, category: str, effect: str, stem: str, suffix: str) -> Path:
    return ctx.vfx_root / category / slugify(effect) / f"{slugify(stem)}{suffix}"


def set_dotted_field(target: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cursor: dict[str, Any] = target
    for key in parts[:-1]:
        existing = cursor.get(key)
        if not isinstance(existing, dict):
            existing = {}
            cursor[key] = existing
        cursor = existing
    cursor[parts[-1]] = value


def read_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    rows: list[Any] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows
