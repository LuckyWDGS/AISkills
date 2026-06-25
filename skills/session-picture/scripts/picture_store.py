#!/usr/bin/env python3
"""Durable image store for Codex session assets.

This script copies user-provided images into a project-local `.codex/session`
store, maintains a JSON index, and mirrors a compact summary into ASSETS.md or
DEBUG_SCREENSHOTS.md. It never reads the clipboard.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import struct
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = "session-picture-index-v1"
INDEX_REL = Path(".codex/session/assets/session-picture-index.json")
LOCK_REL = Path(".codex/session/assets/session-picture.lock")
ASSETS_MD_REL = Path(".codex/session/ASSETS.md")
DEBUG_MD_REL = Path(".codex/session/DEBUG_SCREENSHOTS.md")
HANDOFF_REL = Path(".codex/session/HANDOFF.md")
LOCK_STALE_SECONDS = 6 * 60 * 60
LOCK_HEARTBEAT_SECONDS = 60.0

ASSET_TYPES = {
    "design-reference",
    "bug-screenshot",
    "source-media",
    "generated-image",
    "unclassified",
}
STATUSES = {
    "active",
    "pinned",
    "superseded",
    "rejected",
    "missing",
    "thread-only",
    "stale-delete-soon",
    "integrity-failed",
    "deleted",
}
USER_SETTABLE_STATUSES = {
    "active",
    "pinned",
    "superseded",
    "rejected",
    "stale-delete-soon",
}
RETENTIONS = {
    "keep",
    "task-lifetime",
    "cleanup-after-verification",
    "auto-unused",
}
IMAGE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".avif",
}
EXT_BY_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/tiff": ".tif",
    "image/avif": ".avif",
}


class StoreError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def now_precise_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_days(value: str | None) -> float:
    parsed = parse_iso(value)
    if not parsed:
        return 10**9
    if not parsed.tzinfo:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 86400


def find_root(root_arg: str) -> Path:
    if root_arg != "auto":
        return Path(root_arg).resolve()
    cur = Path.cwd().resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / ".codex/session").exists():
            return candidate
    return cur


def rel_to_root(path: Path, root: Path) -> str:
    return os.path.relpath(path.resolve(), root.resolve()).replace("\\", "/")


def session_root(root: Path) -> Path:
    return (root / ".codex/session").resolve()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def checked_local_path(item: dict[str, Any], root: Path) -> tuple[Path | None, str | None]:
    local_path = item.get("local_path")
    if not local_path:
        return None, "no local_path"
    raw = Path(str(local_path))
    if raw.is_absolute():
        return None, "local_path must be project-relative"
    candidate = (root / raw).resolve()
    if not is_within(candidate, session_root(root)):
        return None, "local_path escapes .codex/session"
    return candidate, None


def resolve_local_path(item: dict[str, Any], root: Path) -> Path | None:
    path, error = checked_local_path(item, root)
    return None if error else path


def ensure_store(root: Path) -> None:
    (root / ".codex/session/assets").mkdir(parents=True, exist_ok=True)
    (root / ".codex/session/assets/active/session-picture").mkdir(parents=True, exist_ok=True)
    (root / ".codex/session/assets/rejected/session-picture").mkdir(parents=True, exist_ok=True)
    (root / ".codex/session/debug-screenshots/session-picture").mkdir(parents=True, exist_ok=True)
    for rel, title in (
        (ASSETS_MD_REL, "Assets"),
        (DEBUG_MD_REL, "Debug Screenshots"),
        (HANDOFF_REL, "Active Handoff"),
    ):
        target = root / rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# {title}\n", encoding="utf-8")
    index_path = root / INDEX_REL
    if not index_path.exists():
        write_index(root, {"schema": SCHEMA, "updated_at": now_iso(), "items": []})


def require_store(root: Path) -> None:
    index_path = root / INDEX_REL
    if not index_path.exists():
        raise StoreError(f"Store is not initialized at {root}. Run `picture_store.py init --root {root}` first.")


def load_index(root: Path, create: bool = False) -> dict[str, Any]:
    if create:
        ensure_store(root)
    else:
        require_store(root)
    index_path = root / INDEX_REL
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StoreError(f"Index JSON is invalid: {index_path}: {exc}") from exc
    if data.get("schema") != SCHEMA:
        raise StoreError(f"Unsupported index schema: {data.get('schema')!r}")
    data.setdefault("items", [])
    return data


def read_lock_token(lock_path: Path) -> str | None:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    token = payload.get("token")
    return str(token) if token else None


def read_lock_payload(lock_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def lock_heartbeat_age_seconds(lock_path: Path) -> float:
    payload = read_lock_payload(lock_path)
    if payload:
        heartbeat_at = parse_iso(str(payload.get("heartbeat_at") or ""))
        if heartbeat_at:
            if not heartbeat_at.tzinfo:
                heartbeat_at = heartbeat_at.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - heartbeat_at.astimezone(timezone.utc)).total_seconds()
    try:
        return time.time() - lock_path.stat().st_mtime
    except OSError:
        return 0.0


def write_lock_payload(lock_path: Path, root: Path, token: str) -> None:
    created_at = now_precise_iso()
    existing = read_lock_payload(lock_path)
    if existing and existing.get("token") == token and existing.get("created_at"):
        created_at = str(existing["created_at"])
    payload = {
        "token": token,
        "pid": os.getpid(),
        "created_at": created_at,
        "heartbeat_at": now_precise_iso(),
        "root": str(root),
    }
    tmp = lock_path.with_name(f"{lock_path.name}.{token}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(lock_path)


def release_lock(lock_path: Path, token: str) -> None:
    try:
        if read_lock_token(lock_path) == token:
            lock_path.unlink()
    except FileNotFoundError:
        pass


def start_lock_heartbeat(lock_path: Path, root: Path, token: str, interval_seconds: float) -> tuple[threading.Event, threading.Thread]:
    stop_event = threading.Event()
    interval = max(0.1, interval_seconds)

    def heartbeat() -> None:
        while not stop_event.wait(interval):
            try:
                if read_lock_token(lock_path) != token:
                    return
                write_lock_payload(lock_path, root, token)
            except OSError:
                return

    thread = threading.Thread(target=heartbeat, name="session-picture-lock-heartbeat", daemon=True)
    thread.start()
    return stop_event, thread


@contextmanager
def store_lock(
    root: Path,
    create: bool = False,
    timeout_seconds: float = 30.0,
    heartbeat_seconds: float = LOCK_HEARTBEAT_SECONDS,
):
    if heartbeat_seconds <= 0:
        raise StoreError("--lock-heartbeat-seconds must be positive")
    if heartbeat_seconds >= LOCK_STALE_SECONDS / 2:
        raise StoreError("--lock-heartbeat-seconds must be less than half the stale-lock threshold")
    lock_dir = (root / LOCK_REL).parent
    if not lock_dir.exists():
        if not create:
            raise StoreError(f"Session-picture store is not initialized: {root / INDEX_REL}")
        lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = root / LOCK_REL
    deadline = time.monotonic() + timeout_seconds
    acquired = False
    token = uuid.uuid4().hex
    heartbeat_stop: threading.Event | None = None
    heartbeat_thread: threading.Thread | None = None
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                payload = {
                    "token": token,
                    "pid": os.getpid(),
                    "created_at": now_precise_iso(),
                    "heartbeat_at": now_precise_iso(),
                    "root": str(root),
                }
                os.write(fd, (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            finally:
                os.close(fd)
            acquired = True
            heartbeat_stop, heartbeat_thread = start_lock_heartbeat(lock_path, root, token, heartbeat_seconds)
            break
        except FileExistsError:
            try:
                age = lock_heartbeat_age_seconds(lock_path)
                if age > LOCK_STALE_SECONDS:
                    lock_path.unlink()
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise StoreError(f"Timed out waiting for store lock: {lock_path}")
            time.sleep(0.1)
    try:
        yield
    finally:
        if acquired:
            if heartbeat_stop:
                heartbeat_stop.set()
            if heartbeat_thread:
                heartbeat_thread.join(timeout=1.0)
            release_lock(lock_path, token)


def write_index(root: Path, data: dict[str, Any]) -> None:
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    index_path = root / INDEX_REL
    index_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = index_path.with_suffix(index_path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(index_path)


def snapshot_store_files(root: Path) -> dict[Path, bytes | None]:
    snapshot: dict[Path, bytes | None] = {}
    for rel in (INDEX_REL, ASSETS_MD_REL, DEBUG_MD_REL):
        path = root / rel
        snapshot[path] = path.read_bytes() if path.exists() else None
    return snapshot


def restore_store_files(snapshot: dict[Path, bytes | None]) -> None:
    for path, data in snapshot.items():
        if data is None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)


def read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise StoreError(f"Cannot read source file: {path}: {exc}") from exc


def rollback_created_files(paths: list[Path], root: Path) -> None:
    for path in reversed(paths):
        try:
            resolved = path.resolve()
            if is_within(resolved, session_root(root)) and resolved.exists():
                resolved.unlink()
        except OSError:
            pass


def rollback_moves(moves: list[tuple[Path, Path]], root: Path) -> None:
    for original, moved in reversed(moves):
        try:
            original_resolved = original.resolve()
            moved_resolved = moved.resolve()
            if is_within(original_resolved, session_root(root)) and is_within(moved_resolved, session_root(root)) and moved_resolved.exists():
                original_resolved.parent.mkdir(parents=True, exist_ok=True)
                moved_resolved.replace(original_resolved)
        except OSError:
            pass


def rollback_deleted_files(deleted_files: list[tuple[Path, bytes]], root: Path) -> None:
    for path, data in reversed(deleted_files):
        try:
            resolved = path.resolve()
            if is_within(resolved, session_root(root)) and not resolved.exists():
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_bytes(data)
        except OSError:
            pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sniff_mime(data: bytes, source: Path | None = None) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"BM"):
        return "image/bmp"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if len(data) > 12 and data[4:8] == b"ftyp" and b"avif" in data[8:32]:
        return "image/avif"
    return "application/octet-stream"


def image_size(data: bytes) -> tuple[int | None, int | None]:
    try:
        if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
            return struct.unpack(">II", data[16:24])
        if data.startswith((b"GIF87a", b"GIF89a")) and len(data) >= 10:
            return struct.unpack("<HH", data[6:10])
        if data.startswith(b"BM") and len(data) >= 26:
            width, height = struct.unpack("<ii", data[18:26])
            return abs(width), abs(height)
        if data.startswith(b"\xff\xd8"):
            return jpeg_size(data)
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return webp_size(data)
    except Exception:
        return None, None
    return None, None


def jpeg_size(data: bytes) -> tuple[int | None, int | None]:
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        i += 2
        if marker in (0xD8, 0xD9):
            continue
        if i + 2 > len(data):
            break
        length = struct.unpack(">H", data[i : i + 2])[0]
        if length < 2:
            break
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        } and i + 7 < len(data):
            height, width = struct.unpack(">HH", data[i + 3 : i + 7])
            return width, height
        i += length
    return None, None


def webp_size(data: bytes) -> tuple[int | None, int | None]:
    if len(data) < 30:
        return None, None
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8 " and len(data) >= 30:
        if data[23:26] == b"\x9d\x01\x2a":
            width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
            height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
            return width, height
    if chunk == b"VP8L" and len(data) >= 25:
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    return None, None


def slug(value: str | None, fallback: str = "image") -> str:
    if not value:
        return fallback
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return cleaned[:48] or fallback


def split_tags(values: list[str] | None) -> list[str]:
    tags: list[str] = []
    for value in values or []:
        for part in value.split(","):
            tag = part.strip()
            if tag and tag not in tags:
                tags.append(tag)
    return tags


def merge_tags(existing: list[str], new_tags: list[str]) -> list[str]:
    merged = list(existing or [])
    for tag in new_tags:
        if tag not in merged:
            merged.append(tag)
    return merged


def merge_note(existing: str | None, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing}\n{note}"


def append_import_history(
    item: dict[str, Any],
    source_name: str,
    original_source: dict[str, str],
    args: argparse.Namespace,
    timestamp: str,
) -> None:
    history = item.setdefault("import_history", [])
    history.append(
        {
            "seen_at": timestamp,
            "source_name": source_name,
            "original_source": original_source,
            "task_id": args.task_id,
            "scope": args.scope,
            "caption": args.caption,
            "user_intent": args.user_intent,
            "tags": split_tags(args.tag),
        }
    )


def make_id(sha: str) -> str:
    return f"asset_{datetime.now().astimezone().strftime('%Y%m%d_%H%M%S_%f')}_{sha[:8]}"


def storage_dir(root: Path, asset_type: str, status: str) -> Path:
    if asset_type == "bug-screenshot":
        base = root / ".codex/session/debug-screenshots/session-picture"
    elif status in {"rejected", "superseded", "stale-delete-soon"}:
        base = root / ".codex/session/assets/rejected/session-picture"
    else:
        base = root / ".codex/session/assets/active/session-picture"
    stamp = datetime.now().astimezone().strftime("%Y/%m")
    return base / stamp


def unique_dest(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def move_item_to_current_storage(item: dict[str, Any], root: Path, moves: list[tuple[Path, Path]] | None = None) -> tuple[bool, str]:
    ok, reason = verify_item(item, root, mutate=True)
    if not ok:
        return False, reason
    current = resolve_local_path(item, root)
    if not current:
        return False, "no trusted local path"
    target_dir = storage_dir(root, item.get("asset_type", "unclassified"), item.get("status", "active"))
    target_dir.mkdir(parents=True, exist_ok=True)
    if current.parent.resolve() == target_dir.resolve():
        return True, "already in lifecycle directory"
    target = unique_dest(target_dir / current.name)
    current.replace(target)
    if moves is not None:
        moves.append((current, target))
    item["local_path"] = rel_to_root(target, root)
    ok, reason = verify_item(item, root, mutate=True)
    return ok, reason


def find_item(items: list[dict[str, Any]], key: str, root: Path | None = None) -> dict[str, Any] | None:
    key_norm = key.lower()
    for item in items:
        if item.get("id", "").lower() == key_norm:
            return item
    if len(key_norm) >= 12:
        id_matches = [item for item in items if item.get("id", "").lower().startswith(key_norm)]
        if len(id_matches) == 1:
            return id_matches[0]
        if len(id_matches) > 1:
            raise StoreError(f"Ambiguous id prefix {key!r}: {', '.join(i.get('id', '') for i in id_matches[:5])}")
    if len(key_norm) >= 8:
        sha_matches = [item for item in items if item.get("sha256", "").lower().startswith(key_norm)]
        if len(sha_matches) == 1:
            return sha_matches[0]
        if len(sha_matches) > 1:
            raise StoreError(f"Ambiguous sha prefix {key!r}: {', '.join(i.get('id', '') for i in sha_matches[:5])}")
    if root:
        try:
            resolved_key = Path(key).resolve()
        except OSError:
            resolved_key = None
        for item in items:
            path = resolve_local_path(item, root)
            if path and (str(path).lower() == key_norm or (resolved_key and path == resolved_key)):
                return item
    return None


def create_record(
    root: Path,
    index: dict[str, Any],
    data: bytes,
    source_name: str,
    original_source: dict[str, str],
    args: argparse.Namespace,
    created_paths: list[Path] | None = None,
) -> dict[str, Any]:
    if not data:
        raise StoreError(f"Source is empty: {source_name}")
    mime = sniff_mime(data, Path(source_name))
    if not mime.startswith("image/"):
        raise StoreError(f"Source does not look like an image ({mime}): {source_name}")
    sha = sha256_bytes(data)
    width, height = image_size(data)
    tags = split_tags(args.tag)
    existing = next((i for i in index["items"] if i.get("sha256") == sha and i.get("status") != "deleted"), None)
    timestamp = now_iso()
    if existing:
        ok, reason = verify_item(existing, root, mutate=True)
        if not ok and reason == "file missing":
            repaired_path = resolve_local_path(existing, root)
            if repaired_path:
                repaired_path.parent.mkdir(parents=True, exist_ok=True)
                repaired_path.write_bytes(data)
                if created_paths is not None:
                    created_paths.append(repaired_path)
                ok, reason = verify_item(existing, root, mutate=True)
                if ok:
                    existing["status"] = args.status or "active"
        if not ok:
            existing["notes"] = merge_note(
                existing.get("notes"),
                f"Duplicate SHA seen at {timestamp}, but previous record was not recoverable: {reason}",
            )
        if not ok:
            existing = None

    if existing:
        existing["last_seen_at"] = timestamp
        existing["last_verified_at"] = timestamp
        existing["tags"] = merge_tags(existing.get("tags", []), tags)
        append_import_history(existing, source_name, original_source, args, timestamp)
        for field in ("task_id", "scope", "caption", "user_intent"):
            value = getattr(args, field, None)
            if value and not existing.get(field):
                existing[field] = value
        if args.retention:
            existing["retention"] = args.retention
        if args.status:
            existing["status"] = args.status
        if args.pin:
            existing["status"] = "pinned"
            existing["retention"] = "keep"
        return existing

    status = args.status or ("pinned" if args.pin else "active")
    retention = args.retention or ("keep" if status == "pinned" else "task-lifetime")
    ext = EXT_BY_MIME.get(mime) or Path(source_name).suffix.lower()
    if ext not in IMAGE_EXTS:
        ext = ".img"
    item_id = make_id(sha)
    name_part = slug(args.scope or (tags[0] if tags else Path(source_name).stem))
    dest_dir = storage_dir(root, args.asset_type, status)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{datetime.now().astimezone().strftime('%Y%m%d')}-{name_part}-{sha[:8]}{ext}"
    suffix = 1
    while dest.exists():
        dest = dest_dir / f"{datetime.now().astimezone().strftime('%Y%m%d')}-{name_part}-{sha[:8]}-{suffix}{ext}"
        suffix += 1
    dest.write_bytes(data)
    if created_paths is not None:
        created_paths.append(dest)
    copied = read_bytes(dest)
    copied_sha = sha256_bytes(copied)
    if copied_sha != sha:
        raise StoreError(f"Copied file hash mismatch: {dest}")

    item = {
        "id": item_id,
        "asset_type": args.asset_type,
        "status": status,
        "retention": retention,
        "local_path": rel_to_root(dest, root),
        "original_source": original_source,
        "sha256": sha,
        "mime": mime,
        "bytes": len(data),
        "width": width,
        "height": height,
        "task_id": args.task_id,
        "scope": args.scope,
        "tags": tags,
        "caption": args.caption,
        "user_intent": args.user_intent,
        "created_at": timestamp,
        "last_seen_at": timestamp,
        "last_used_at": timestamp,
        "last_verified_at": timestamp,
        "supersedes": [],
        "superseded_by": None,
        "notes": args.note,
    }
    index["items"].append(item)
    return item


def verify_item(item: dict[str, Any], root: Path, mutate: bool = False) -> tuple[bool, str]:
    if item.get("status") == "deleted":
        return False, "deleted: file has been cleaned up"
    if item.get("status") == "thread-only":
        return False, "thread-only: no durable local path was captured"
    path, path_error = checked_local_path(item, root)
    if path_error:
        return False, path_error
    if not path.exists():
        if mutate and item.get("status") not in {"deleted", "thread-only"}:
            item["status"] = "missing"
            item["last_verified_at"] = now_iso()
        return False, "file missing"
    data = read_bytes(path)
    actual_sha = sha256_bytes(data)
    if actual_sha != item.get("sha256"):
        if mutate:
            item["status"] = "integrity-failed"
            item["last_verified_at"] = now_iso()
        return False, "sha256 mismatch"
    if mutate:
        item["last_verified_at"] = now_iso()
    return True, "ok"


def resolved_item(item: dict[str, Any], root: Path) -> dict[str, Any]:
    result = dict(item)
    path = resolve_local_path(item, root)
    result["resolved_path"] = str(path) if path else None
    return result


def indexed_result(item: dict[str, Any]) -> dict[str, Any]:
    result = dict(item)
    result.pop("resolved_path", None)
    return result


def trusted_result(item: dict[str, Any], root: Path, ok: bool, reason: str) -> dict[str, Any]:
    result = resolved_item(item, root)
    resolved = result.get("resolved_path")
    result.pop("resolved_path", None)
    result["verification"] = reason
    result["trusted_path"] = resolved if ok else None
    result["untrusted_path"] = None if ok else resolved
    return result


def print_items(items: list[dict[str, Any]], root: Path, as_json: bool, paths_verified: bool = False) -> None:
    if as_json:
        payload = [resolved_item(item, root) if paths_verified else indexed_result(item) for item in items]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if not items:
        print("No matching images.")
        return
    for item in items:
        if paths_verified:
            path = resolve_local_path(item, root)
            path_text = str(path) if path else "(no durable path)"
        else:
            path_text = item.get("local_path") or "(no durable path)"
        tags = ", ".join(item.get("tags") or [])
        dims = ""
        if item.get("width") and item.get("height"):
            dims = f" {item['width']}x{item['height']}"
        print(f"{item['id']} [{item.get('status')}/{item.get('asset_type')}]{dims}")
        print(f"  path: {path_text}")
        if tags:
            print(f"  tags: {tags}")
        if item.get("caption"):
            print(f"  caption: {item['caption']}")


def markdown_escape(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ").strip()
    text = text.replace("|", "\\|")
    return text[:120]


def render_section(items: list[dict[str, Any]], root: Path, debug: bool) -> str:
    title = "Session Picture Debug Registry" if debug else "Session Picture Asset Registry"
    filtered = [
        item
        for item in items
        if (item.get("asset_type") == "bug-screenshot") == debug and item.get("status") != "deleted"
    ]
    lines = [
        f"## {title}",
        "",
        f"Generated: {now_iso()}",
        "",
    ]
    if not filtered:
        lines.append("No managed entries.")
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            "| ID | Type | Status | Retention | Tags | Caption | Path | Last Used |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in sorted(filtered, key=lambda i: i.get("created_at", ""), reverse=True):
        path = item.get("local_path") or "(no durable path)"
        lines.append(
            "| {id} | {asset_type} | {status} | {retention} | {tags} | {caption} | {path} | {last_used} |".format(
                id=markdown_escape(item.get("id")),
                asset_type=markdown_escape(item.get("asset_type")),
                status=markdown_escape(item.get("status")),
                retention=markdown_escape(item.get("retention")),
                tags=markdown_escape(", ".join(item.get("tags") or [])),
                caption=markdown_escape(item.get("caption")),
                path=markdown_escape(path),
                last_used=markdown_escape(item.get("last_used_at")),
            )
        )
    return "\n".join(lines) + "\n"


def replace_managed_section(text: str, body: str, name: str) -> str:
    start = f"<!-- session-picture:{name}:start -->"
    end = f"<!-- session-picture:{name}:end -->"
    block = f"{start}\n{body}{end}\n"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end) + r"\n?", re.DOTALL)
    if pattern.search(text):
        return pattern.sub(lambda _match: block, text)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + "\n" + block


def sync_markdown(root: Path, index: dict[str, Any]) -> None:
    for rel, name, debug in (
        (ASSETS_MD_REL, "assets", False),
        (DEBUG_MD_REL, "debug", True),
    ):
        path = root / rel
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        body = render_section(index["items"], root, debug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(replace_managed_section(existing, body, name), encoding="utf-8")


def write_index_and_sync_markdown(root: Path, index: dict[str, Any], snapshot: dict[Path, bytes | None] | None = None) -> None:
    snapshots = snapshot if snapshot is not None else snapshot_store_files(root)
    try:
        write_index(root, index)
        sync_markdown(root, index)
    except Exception:
        restore_store_files(snapshots)
        raise


def command_init(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    ensure_store(root)
    index = load_index(root)
    sync_markdown(root, index)
    print(f"ready {root / INDEX_REL}")
    return 0


def command_add(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    prepared: list[tuple[Path, bytes]] = []
    for source in args.sources:
        source_path = Path(source).expanduser().resolve()
        if not source_path.exists():
            raise StoreError(f"Source does not exist: {source_path}")
        if source_path.is_dir():
            candidates = sorted(p for p in source_path.iterdir() if p.suffix.lower() in IMAGE_EXTS)
        else:
            candidates = [source_path]
        if not candidates:
            raise StoreError(f"No image files found in directory: {source_path}")
        for candidate in candidates:
            data = read_bytes(candidate)
            if not data:
                raise StoreError(f"Source is empty: {candidate}")
            mime = sniff_mime(data, candidate)
            if not mime.startswith("image/"):
                raise StoreError(f"Source does not look like an image ({mime}): {candidate}")
            prepared.append((candidate, data))
    index = load_index(root, create=True)
    snapshots = snapshot_store_files(root)
    added: list[dict[str, Any]] = []
    created_paths: list[Path] = []
    try:
        for candidate, data in prepared:
            item = create_record(
                root,
                index,
                data,
                str(candidate),
                {"kind": "local-path", "value": str(candidate)},
                args,
                created_paths,
            )
            added.append(item)
        write_index_and_sync_markdown(root, index, snapshots)
    except Exception:
        rollback_created_files(created_paths, root)
        restore_store_files(snapshots)
        raise
    print_items(added, root, args.json, paths_verified=True)
    return 0


def parse_data_url(text: str) -> tuple[str, bytes]:
    match = re.match(r"\s*data:([^;,]+)?(?:;[^,]*)?;base64,(.*)\s*", text, re.DOTALL)
    if not match:
        raise StoreError("Data URL must look like data:image/...;base64,...")
    mime = match.group(1) or "application/octet-stream"
    try:
        data = base64.b64decode(re.sub(r"\s+", "", match.group(2)), validate=True)
    except binascii.Error as exc:
        raise StoreError(f"Invalid base64 data URL: {exc}") from exc
    return mime, data


def prevalidate_add_sources(args: argparse.Namespace) -> None:
    for source in args.sources:
        source_path = Path(source).expanduser().resolve()
        if not source_path.exists():
            raise StoreError(f"Source does not exist: {source_path}")
        candidates = sorted(p for p in source_path.iterdir() if p.suffix.lower() in IMAGE_EXTS) if source_path.is_dir() else [source_path]
        if not candidates:
            raise StoreError(f"No image files found in directory: {source_path}")
        for candidate in candidates:
            data = read_bytes(candidate)
            if not data:
                raise StoreError(f"Source is empty: {candidate}")
            mime = sniff_mime(data, candidate)
            if not mime.startswith("image/"):
                raise StoreError(f"Source does not look like an image ({mime}): {candidate}")


def prevalidate_add_data_url(args: argparse.Namespace) -> None:
    source = Path(args.file).expanduser().resolve()
    text = source.read_text(encoding="utf-8")
    mime, _ = parse_data_url(text)
    if not mime.startswith("image/"):
        raise StoreError(f"Data URL is not an image: {mime}")


def command_add_data_url(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    source = Path(args.file).expanduser().resolve()
    text = source.read_text(encoding="utf-8")
    mime, data = parse_data_url(text)
    if not mime.startswith("image/"):
        raise StoreError(f"Data URL is not an image: {mime}")
    index = load_index(root, create=True)
    snapshots = snapshot_store_files(root)
    created_paths: list[Path] = []
    try:
        item = create_record(
            root,
            index,
            data,
            source.name,
            {"kind": "data-url-file", "value": str(source)},
            args,
            created_paths,
        )
        write_index_and_sync_markdown(root, index, snapshots)
    except Exception:
        rollback_created_files(created_paths, root)
        restore_store_files(snapshots)
        raise
    print_items([item], root, args.json, paths_verified=True)
    return 0


def command_thread_only(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    index = load_index(root, create=True)
    timestamp = now_iso()
    item = {
        "id": f"asset_{datetime.now().astimezone().strftime('%Y%m%d_%H%M%S_%f')}_thread",
        "asset_type": args.asset_type,
        "status": "thread-only",
        "retention": args.retention or "task-lifetime",
        "local_path": None,
        "original_source": {"kind": "chat-visible-no-path", "value": "No local path or image bytes exposed"},
        "sha256": None,
        "mime": None,
        "bytes": None,
        "width": None,
        "height": None,
        "task_id": args.task_id,
        "scope": args.scope,
        "tags": split_tags(args.tag),
        "caption": args.caption,
        "user_intent": args.user_intent,
        "created_at": timestamp,
        "last_seen_at": timestamp,
        "last_used_at": None,
        "last_verified_at": None,
        "supersedes": [],
        "superseded_by": None,
        "notes": args.note or "Visible to the model in this thread only; not recoverable in future sessions.",
    }
    index["items"].append(item)
    write_index_and_sync_markdown(root, index)
    print_items([item], root, args.json)
    return 0


def item_matches(item: dict[str, Any], query: str | None, args: argparse.Namespace) -> bool:
    if args.asset_type and item.get("asset_type") != args.asset_type:
        return False
    if args.status and item.get("status") != args.status:
        return False
    for tag in split_tags(args.tag):
        if tag not in (item.get("tags") or []):
            return False
    if not query:
        return True
    haystack = " ".join(
        str(value or "")
        for value in (
            item.get("id"),
            item.get("sha256"),
            item.get("task_id"),
            item.get("scope"),
            item.get("caption"),
            item.get("user_intent"),
            " ".join(item.get("tags") or []),
            item.get("local_path"),
        )
    ).lower()
    return all(term.lower() in haystack for term in query.split())


def command_find(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    index = load_index(root)
    matches = [item for item in index["items"] if item_matches(item, args.query, args)]
    verification_results: dict[str, tuple[bool, str]] = {}
    if args.verify:
        for item in matches:
            verification_results[item["id"]] = verify_item(item, root, mutate=True)
        write_index_and_sync_markdown(root, index)
    matches.sort(
        key=lambda i: (
            i.get("status") in {"active", "pinned"},
            i.get("status") == "pinned",
            i.get("last_used_at") or i.get("created_at") or "",
        ),
        reverse=True,
    )
    limited = matches[: args.limit]
    if args.verify:
        if args.json:
            verified = [
                trusted_result(item, root, *verification_results.get(item["id"], verify_item(item, root, mutate=False)))
                for item in limited
            ]
            print(json.dumps(verified, ensure_ascii=False, indent=2))
        else:
            if not limited:
                print("No matching images.")
            for item in limited:
                ok, reason = verification_results.get(item["id"], verify_item(item, root, mutate=False))
                if ok:
                    print_items([item], root, False, paths_verified=True)
                else:
                    result = trusted_result(item, root, ok, reason)
                    print(f"{item['id']} [{item.get('status')}/{item.get('asset_type')}]")
                    if result.get("untrusted_path"):
                        print(f"  untrusted_path: {result['untrusted_path']}")
                    else:
                        print("  path: (no trusted path)")
                print(f"  verification: {reason}")
        return 3 if any(not ok for ok, _ in verification_results.values()) else 0
    print_items(limited, root, args.json)
    return 0


def command_show(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    index = load_index(root)
    item = find_item(index["items"], args.key, root)
    if not item:
        raise StoreError(f"No image matches: {args.key}")
    ok, reason = verify_item(item, root, mutate=True)
    if ok and not args.no_touch:
        item["last_used_at"] = now_iso()
    write_index_and_sync_markdown(root, index)
    if args.json:
        result = trusted_result(item, root, ok, reason)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if ok:
            print_items([item], root, False, paths_verified=True)
        else:
            result = trusted_result(item, root, ok, reason)
            print(f"{item['id']} [{item.get('status')}/{item.get('asset_type')}]")
            if result.get("untrusted_path"):
                print(f"  untrusted_path: {result['untrusted_path']}")
            else:
                print("  path: (no trusted path)")
        print(f"  verification: {reason}")
    return 0 if ok else 3


def command_update(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    index = load_index(root)
    item = find_item(index["items"], args.key, root)
    if not item:
        raise StoreError(f"No image matches: {args.key}")
    lifecycle_change = bool(args.asset_type or args.status or args.pin or args.unpin)
    if lifecycle_change:
        if item.get("status") in {"deleted", "thread-only", "missing", "integrity-failed"}:
            raise StoreError(f"Cannot change lifecycle storage for non-recoverable item: {item['id']} status={item.get('status')}")
        ok, reason = verify_item(item, root, mutate=False)
        if not ok:
            raise StoreError(f"Cannot change lifecycle storage for unverified item: {item['id']} verification={reason}")
    snapshots = snapshot_store_files(root)
    moves: list[tuple[Path, Path]] = []
    try:
        if args.asset_type:
            item["asset_type"] = args.asset_type
        if args.status:
            item["status"] = args.status
        if args.retention:
            item["retention"] = args.retention
        if args.pin:
            item["status"] = "pinned"
            item["retention"] = "keep"
        if args.unpin and item.get("status") == "pinned":
            item["status"] = "active"
            if item.get("retention") == "keep":
                item["retention"] = "task-lifetime"
        for field in ("task_id", "scope", "caption", "user_intent", "notes"):
            value = getattr(args, field, None)
            if value is not None:
                item[field] = value
        item["tags"] = merge_tags(item.get("tags", []), split_tags(args.tag))
        item["last_seen_at"] = now_iso()
        if lifecycle_change:
            ok, reason = move_item_to_current_storage(item, root, moves)
            if not ok:
                raise StoreError(f"Cannot move item to lifecycle directory: {item['id']} verification={reason}")
        write_index_and_sync_markdown(root, index, snapshots)
    except Exception:
        rollback_moves(moves, root)
        restore_store_files(snapshots)
        raise
    print_items([item], root, args.json)
    return 0


def command_supersede(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    index = load_index(root)
    old = find_item(index["items"], args.old, root)
    new = find_item(index["items"], args.new, root)
    if not old:
        raise StoreError(f"No old image matches: {args.old}")
    if not new:
        raise StoreError(f"No new image matches: {args.new}")
    if old["id"] == new["id"]:
        raise StoreError("Cannot supersede an image with itself")
    if old.get("status") in {"deleted", "thread-only", "missing", "integrity-failed"}:
        raise StoreError(f"Old image is not a recoverable local asset: {old['id']} status={old.get('status')}")
    ok, reason = verify_item(old, root, mutate=False)
    if not ok:
        raise StoreError(f"Old image is not recoverable: {old['id']} verification={reason}")
    ok, reason = verify_item(new, root, mutate=True)
    if not ok:
        raise StoreError(f"New image is not recoverable: {new['id']} verification={reason}")
    snapshots = snapshot_store_files(root)
    moves: list[tuple[Path, Path]] = []
    try:
        old["status"] = "superseded"
        old["superseded_by"] = new["id"]
        old.setdefault("notes", "")
        new.setdefault("supersedes", [])
        if old["id"] not in new["supersedes"]:
            new["supersedes"].append(old["id"])
        new["status"] = "active"
        ok, reason = move_item_to_current_storage(old, root, moves)
        if not ok:
            raise StoreError(f"Cannot move superseded image: {old['id']} verification={reason}")
        ok, reason = move_item_to_current_storage(new, root, moves)
        if not ok:
            raise StoreError(f"Cannot confirm new active image: {new['id']} verification={reason}")
        timestamp = now_iso()
        old["last_seen_at"] = timestamp
        new["last_seen_at"] = timestamp
        write_index_and_sync_markdown(root, index, snapshots)
    except Exception:
        rollback_moves(moves, root)
        restore_store_files(snapshots)
        raise
    print_items([old, new], root, args.json, paths_verified=True)
    return 0


def handoff_text(root: Path) -> str:
    path = root / HANDOFF_REL
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def referenced_by_handoff(item: dict[str, Any], text: str, root: Path) -> bool:
    normalized_text = text.replace("\\", "/").lower()
    candidates = [item.get("id") or "", item.get("local_path") or ""]
    path = resolve_local_path(item, root)
    if path:
        candidates.append(str(path))
    for candidate in candidates:
        normalized = str(candidate).replace("\\", "/").lower()
        if normalized and normalized in normalized_text:
            return True
    return False


def cleanup_index_path_errors(index: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    for item in index["items"]:
        if item.get("status") in {"deleted", "thread-only"}:
            continue
        _, path_error = checked_local_path(item, root)
        if path_error:
            errors.append(f"{item.get('id', '(missing id)')}: {path_error}")
    return errors


def cleanup_candidates(index: dict[str, Any], root: Path, args: argparse.Namespace) -> tuple[list[dict[str, Any]], bool]:
    text = handoff_text(root)
    candidates: list[dict[str, Any]] = []
    dirty = False
    cleanup_statuses = {s.strip() for s in args.statuses.split(",") if s.strip()} if args.statuses else {"rejected", "superseded", "stale-delete-soon"}
    for item in index["items"]:
        status = item.get("status")
        retention = item.get("retention")
        if status == "deleted":
            if not args.purge_deleted_records:
                continue
            item_age = age_days(item.get("deleted_at") or item.get("last_used_at") or item.get("created_at"))
            if item_age >= args.min_age_days:
                candidates.append({"item": item, "reason": f"purge deleted record; age={item_age:.1f}d"})
            continue
        if retention == "keep" or status == "pinned":
            continue
        if status == "active" and not args.include_unused:
            continue
        if status == "thread-only" and not args.include_thread_only:
            continue
        if referenced_by_handoff(item, text, root):
            continue
        item_age = age_days(item.get("last_used_at") or item.get("created_at"))
        reason = None
        if status in cleanup_statuses and item_age >= args.min_age_days:
            reason = f"status={status}; age={item_age:.1f}d"
        elif args.include_thread_only and status == "thread-only" and item_age >= args.min_age_days:
            reason = f"thread-only record; age={item_age:.1f}d"
        elif (
            args.include_unused
            and status == "active"
            and retention in {"task-lifetime", "cleanup-after-verification", "auto-unused"}
            and item_age >= args.min_age_days
        ):
            reason = f"unused active item; retention={retention}; age={item_age:.1f}d"
        if not reason:
            continue
        if status == "thread-only":
            candidates.append({"item": item, "reason": reason})
            continue
        if status == "missing":
            path, path_error = checked_local_path(item, root)
            if path_error or not path.exists():
                candidates.append({"item": item, "reason": reason})
            else:
                ok, verify_reason = verify_item(item, root, mutate=False)
                if not ok:
                    item["status"] = "integrity-failed" if verify_reason == "sha256 mismatch" else "missing"
                    item["last_verified_at"] = now_iso()
                    dirty = True
            continue
        ok, verify_reason = verify_item(item, root, mutate=False)
        if not ok:
            item["status"] = "integrity-failed" if verify_reason == "sha256 mismatch" else "missing"
            item["last_verified_at"] = now_iso()
            dirty = True
            continue
        candidates.append({"item": item, "reason": reason})
    return candidates, dirty


def command_cleanup(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    index = load_index(root)
    path_errors = cleanup_index_path_errors(index, root)
    if path_errors:
        detail = "; ".join(path_errors[:5])
        more = f"; +{len(path_errors) - 5} more" if len(path_errors) > 5 else ""
        raise StoreError(f"Refusing cleanup because the index contains untrusted local_path entries: {detail}{more}")
    candidates, dirty = cleanup_candidates(index, root, args)
    output = []
    for candidate in candidates:
        item = candidate["item"]
        path = resolve_local_path(item, root)
        output.append(
            {
                "id": item.get("id"),
                "status": item.get("status"),
                "retention": item.get("retention"),
                "path": str(path) if path else None,
                "reason": candidate["reason"],
            }
        )
    if args.apply:
        snapshots = snapshot_store_files(root)
        deleted_files: list[tuple[Path, bytes]] = []
        purge_ids: set[str] = set()
        try:
            for candidate in candidates:
                item = candidate["item"]
                if args.purge_deleted_records and item.get("status") == "deleted":
                    purge_ids.add(item.get("id"))
                    continue
                path = resolve_local_path(item, root)
                if path and path.exists():
                    ok, verify_reason = verify_item(item, root, mutate=False)
                    if not ok:
                        item["status"] = "integrity-failed" if verify_reason == "sha256 mismatch" else "missing"
                        item["last_verified_at"] = now_iso()
                        item["cleanup_reason"] = f"cleanup skipped: {verify_reason}"
                        continue
                    deleted_files.append((path, path.read_bytes()))
                    path.unlink()
                item["status"] = "deleted"
                item["deleted_at"] = now_iso()
                item["cleanup_reason"] = candidate["reason"]
            if purge_ids:
                index["items"] = [item for item in index["items"] if item.get("id") not in purge_ids]
            write_index_and_sync_markdown(root, index, snapshots)
        except Exception:
            rollback_deleted_files(deleted_files, root)
            restore_store_files(snapshots)
            raise
    elif candidates or dirty:
        # Persist missing/integrity state changes discovered during candidate scan.
        write_index_and_sync_markdown(root, index)
    if args.json:
        print(json.dumps({"apply": args.apply, "candidates": output}, ensure_ascii=False, indent=2))
    else:
        print(f"{'Applying' if args.apply else 'Dry-run'} cleanup: {len(output)} candidate(s)")
        for entry in output:
            print(f"- {entry['id']}: {entry['reason']}")
            print(f"  path: {entry['path'] or '(no durable path)'}")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    index = load_index(root)
    issues: list[str] = []
    seen_ids: set[str] = set()
    seen_hashes: dict[str, str] = {}
    for item in index["items"]:
        item_id = item.get("id")
        if not item_id:
            issues.append("item without id")
        elif item_id in seen_ids:
            issues.append(f"duplicate id: {item_id}")
        else:
            seen_ids.add(item_id)
        sha = item.get("sha256")
        if sha and item.get("status") != "deleted":
            if sha in seen_hashes:
                issues.append(f"duplicate sha: {sha[:12]} ({seen_hashes[sha]}, {item_id})")
            seen_hashes[sha] = item_id or "unknown"
        if item.get("asset_type") not in ASSET_TYPES:
            issues.append(f"{item_id}: invalid asset_type {item.get('asset_type')!r}")
        if item.get("status") not in STATUSES:
            issues.append(f"{item_id}: invalid status {item.get('status')!r}")
        if item.get("retention") not in RETENTIONS:
            issues.append(f"{item_id}: invalid retention {item.get('retention')!r}")
        if item.get("status") not in {"deleted", "thread-only"}:
            ok, reason = verify_item(item, root, mutate=False)
            if not ok:
                issues.append(f"{item_id}: {reason}")
    if args.json:
        print(json.dumps({"ok": not issues, "issues": issues}, ensure_ascii=False, indent=2))
    else:
        if issues:
            print("Issues:")
            for issue in issues:
                print(f"- {issue}")
        else:
            print("OK: index and image files verified")
    return 1 if issues else 0


def add_common_metadata(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--asset-type", choices=sorted(ASSET_TYPES), default="unclassified")
    parser.add_argument("--status", choices=sorted(USER_SETTABLE_STATUSES))
    parser.add_argument("--retention", choices=sorted(RETENTIONS))
    parser.add_argument("--task-id")
    parser.add_argument("--scope")
    parser.add_argument("--tag", action="append", help="Tag; repeat or comma-separate")
    parser.add_argument("--caption")
    parser.add_argument("--user-intent")
    parser.add_argument("--note")
    parser.add_argument("--pin", action="store_true")
    parser.add_argument("--json", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Save, tag, find, verify, and prune session images.")
    parser.add_argument("--root", default="auto", help="Project root or 'auto' to walk up from cwd.")
    parser.add_argument("--lock-timeout-seconds", type=float, default=30.0, help="Seconds to wait for the store lock.")
    parser.add_argument(
        "--lock-heartbeat-seconds",
        type=float,
        default=LOCK_HEARTBEAT_SECONDS,
        help="Seconds between lock heartbeat refreshes while a command holds the store lock.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_root(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument(
            "--root",
            default=argparse.SUPPRESS,
            help="Project root or 'auto' to walk up from cwd.",
        )

    init = sub.add_parser("init", help="Create store/index and markdown summaries.")
    add_root(init)
    init.set_defaults(func=command_init, create_store=True)

    add = sub.add_parser("add", help="Import local image files or all images in a directory.")
    add_root(add)
    add.add_argument("sources", nargs="+")
    add_common_metadata(add)
    add.set_defaults(func=command_add, create_store=True, prelock_validate=prevalidate_add_sources)

    data_url = sub.add_parser("add-data-url", help="Import an image data URL from a text file.")
    add_root(data_url)
    data_url.add_argument("file")
    add_common_metadata(data_url)
    data_url.set_defaults(func=command_add_data_url, create_store=True, prelock_validate=prevalidate_add_data_url)

    thread_only = sub.add_parser("thread-only", help="Record a chat-visible image that has no durable path.")
    add_root(thread_only)
    add_common_metadata(thread_only)
    thread_only.set_defaults(func=command_thread_only, create_store=True)

    find = sub.add_parser("find", help="Find images by id, tag, caption, task, scope, or path.")
    add_root(find)
    find.add_argument("query", nargs="?")
    find.add_argument("--asset-type", choices=sorted(ASSET_TYPES))
    find.add_argument("--status", choices=sorted(STATUSES))
    find.add_argument("--tag", action="append")
    find.add_argument("--limit", type=int, default=20)
    find.add_argument("--verify", action="store_true")
    find.add_argument("--json", action="store_true")
    find.set_defaults(func=command_find, create_store=False)

    show = sub.add_parser("show", help="Show one image and verify its hash.")
    add_root(show)
    show.add_argument("key")
    show.add_argument("--no-touch", action="store_true")
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=command_show, create_store=False)

    update = sub.add_parser("update", help="Update labels, status, retention, or descriptive metadata.")
    add_root(update)
    update.add_argument("key")
    update.add_argument("--asset-type", choices=sorted(ASSET_TYPES))
    update.add_argument("--status", choices=sorted(USER_SETTABLE_STATUSES))
    update.add_argument("--retention", choices=sorted(RETENTIONS))
    update.add_argument("--task-id")
    update.add_argument("--scope")
    update.add_argument("--tag", action="append")
    update.add_argument("--caption")
    update.add_argument("--user-intent")
    update.add_argument("--notes")
    update.add_argument("--pin", action="store_true")
    update.add_argument("--unpin", action="store_true")
    update.add_argument("--json", action="store_true")
    update.set_defaults(func=command_update, create_store=False)

    supersede = sub.add_parser("supersede", help="Mark OLD as superseded by NEW.")
    add_root(supersede)
    supersede.add_argument("old")
    supersede.add_argument("new")
    supersede.add_argument("--json", action="store_true")
    supersede.set_defaults(func=command_supersede, create_store=False)

    cleanup = sub.add_parser("cleanup", help="Dry-run or apply safe cleanup.")
    add_root(cleanup)
    cleanup.add_argument("--min-age-days", type=int, default=90)
    cleanup.add_argument("--statuses", default="rejected,superseded,stale-delete-soon")
    cleanup.add_argument("--include-unused", action="store_true")
    cleanup.add_argument("--include-thread-only", action="store_true")
    cleanup.add_argument("--purge-deleted-records", action="store_true")
    cleanup.add_argument("--apply", action="store_true")
    cleanup.add_argument("--json", action="store_true")
    cleanup.set_defaults(func=command_cleanup, create_store=False)

    doctor = sub.add_parser("doctor", help="Verify index consistency and file integrity.")
    add_root(doctor)
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=command_doctor, create_store=False)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        prelock_validate = getattr(args, "prelock_validate", None)
        if prelock_validate:
            prelock_validate(args)
        root = find_root(args.root)
        with store_lock(
            root,
            create=getattr(args, "create_store", False),
            timeout_seconds=args.lock_timeout_seconds,
            heartbeat_seconds=args.lock_heartbeat_seconds,
        ):
            return args.func(args)
    except StoreError as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        else:
            print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
