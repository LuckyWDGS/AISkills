#!/usr/bin/env python3
"""Keep a local release ledger. This tool never uploads or proves publication.

Successful platform states need evidence starting with ``UI:`` or ``界面证据：``.
The text is an operator's record, not independent verification by this script.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit
import uuid


STATES = {
    "prepared", "staged", "authorized", "submitting", "submission_unknown",
    "under_review", "published", "scheduled", "rejected",
}
DEDUP_STATES = STATES - {"rejected"}
PLATFORM_STATES = {"under_review", "published", "scheduled"}
SUBMITTED_STATES = {
    "submitting", "submission_unknown", "under_review", "scheduled", "published",
}
TRANSITIONS = {
    "prepared": {"staged", "authorized", "rejected"},
    "staged": {"authorized", "rejected"},
    "authorized": {"staged", "submitting", "rejected"},
    "submitting": {
        "submission_unknown", "under_review", "published", "scheduled", "rejected",
    },
    "submission_unknown": {"under_review", "published", "scheduled", "rejected"},
    "under_review": {"under_review", "published", "scheduled", "rejected"},
    "scheduled": {"scheduled", "under_review", "published", "rejected"},
    "published": set(),
    "rejected": set(),
}


class LedgerError(Exception):
    def __init__(self, code: str, message: str, **details: object) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def absolute_path(value: str, label: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise LedgerError("absolute_path_required", f"{label} 必须使用绝对路径。")
    return path.resolve()


def nonempty(value: str | None, label: str) -> str:
    text = (value or "").strip()
    if not text:
        raise LedgerError("empty_value", f"{label} 不能为空。")
    return text


def file_hash(path: Path) -> str:
    if not path.is_file():
        raise LedgerError("file_missing", f"文件不存在或不是普通文件：{path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_info(path: Path) -> dict:
    if not path.is_file():
        raise LedgerError("file_missing", f"文案包不存在：{path}")
    # Hash exactly the bytes parsed, including whitespace and encoding changes.
    raw = path.read_bytes()
    try:
        package = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise LedgerError("invalid_package", "文案包必须是 UTF-8 JSON。") from exc
    if not isinstance(package, dict) or not package:
        raise LedgerError("invalid_package", "文案包必须是非空 JSON 对象。")
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}


def new_ledger() -> dict:
    now = utc_now()
    return {"schema_version": 1, "created_at": now, "updated_at": now, "releases": []}


def read_ledger(path: Path, *, allow_missing: bool = False) -> dict:
    if not path.exists():
        if allow_missing:
            return new_ledger()
        raise LedgerError("ledger_missing", f"账本不存在：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise LedgerError("invalid_ledger", "账本不是有效的 UTF-8 JSON；未修改文件。") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise LedgerError("invalid_ledger", "账本 schema_version 必须为 1；未修改文件。")
    releases = data.get("releases")
    if not isinstance(releases, list):
        raise LedgerError("invalid_ledger", "账本 releases 必须为列表。")
    seen = set()
    for item in releases:
        valid = (
            isinstance(item, dict)
            and isinstance(item.get("release_id"), str)
            and bool(item["release_id"])
            and isinstance(item.get("account_id"), str)
            and bool(item["account_id"])
            and item.get("kind") in {"video", "image"}
            and item.get("state") in STATES
            and isinstance(item.get("package"), dict)
            and isinstance(item.get("media"), list)
            and bool(item["media"])
            and isinstance(item.get("history"), list)
        )
        if not valid:
            raise LedgerError("invalid_ledger", "账本包含格式错误的发布记录。")
        for asset in [item["package"], *item["media"]]:
            if (
                not isinstance(asset, dict)
                or not isinstance(asset.get("path"), str)
                or not isinstance(asset.get("sha256"), str)
                or len(asset["sha256"]) != 64
                or any(char not in "0123456789abcdef" for char in asset["sha256"])
            ):
                raise LedgerError("invalid_ledger", "账本包含格式错误的素材指纹。")
        if item["release_id"] in seen:
            raise LedgerError("invalid_ledger", "账本包含重复 release_id。")
        seen.add(item["release_id"])
    return data


@contextmanager
def exclusive_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    try:
        descriptor = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise LedgerError(
            "ledger_locked", "账本有排他锁，立即退出；不要重试提交。确认占用进程结束后人工检查锁文件。",
            lock_path=str(lock),
        ) from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "created_at": utc_now()}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        lock.unlink()


def atomic_write(path: Path, data: dict) -> None:
    data["updated_at"] = utc_now()
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def ui_evidence(text: str) -> bool:
    prefixes = ("UI:", "UI：", "UI证据:", "UI证据：", "界面证据:", "界面证据：")
    return any(text.startswith(prefix) and bool(text[len(prefix):].strip()) for prefix in prefixes)


def work_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = nonempty(value, "work-url")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise LedgerError("invalid_work_url", "work-url 必须是无账号密码的 HTTP(S) 作品 URL。")
    return value


def verify_registered_files(release: dict) -> dict:
    changed = []
    for label, asset in [("package", release["package"]), *[("media", x) for x in release["media"]]]:
        try:
            current = file_hash(Path(asset["path"]))
        except LedgerError:
            changed.append({"kind": label, "path": asset["path"], "reason": "missing"})
            continue
        if current != asset["sha256"]:
            changed.append({"kind": label, "path": asset["path"], "reason": "sha256_changed"})
    if changed:
        raise LedgerError(
            "registered_files_changed",
            "已登记媒体或文案包发生变化，禁止进入 submitting；保留旧记录，人工重新审阅并登记新包。",
            changed=changed,
        )
    return {"verified_at": utc_now(), "media_and_package_sha256_match": True}


def register(args: argparse.Namespace, path: Path) -> dict:
    account = nonempty(args.account, "account")
    package_path = absolute_path(args.package, "package")
    if path == package_path:
        raise LedgerError("input_output_collision", "账本路径不能与文案包路径相同。")
    package = package_info(package_path)
    media = []
    for value in args.media:
        media_path = Path(value).expanduser().resolve()
        if path == media_path:
            raise LedgerError("input_output_collision", "账本路径不能与媒体路径相同。")
        media.append({"path": str(media_path), "sha256": file_hash(media_path)})
    ordered_hashes = [item["sha256"] for item in media]
    with exclusive_lock(path):
        ledger = read_ledger(path, allow_missing=True)
        duplicates = [
            item for item in ledger["releases"]
            if item["account_id"] == account
            and item["state"] in DEDUP_STATES
            and [asset["sha256"] for asset in item["media"]] == ordered_hashes
        ]
        if duplicates:
            existing = duplicates[0]
            raise LedgerError(
                "duplicate_media",
                "同账号及相同顺序媒体已登记，请复用既有 release_id；改标题或文案不能绕过重复发布保护。"
                "未提交记录若需换包，先人工记录 rejected 原因，再登记；提交结果未知先只读核验。",
                existing_release_id=existing["release_id"], existing_state=existing["state"],
            )
        now = utc_now()
        release = {
            "release_id": "release-" + uuid.uuid4().hex,
            "account_id": account, "kind": args.kind,
            "state": "prepared", "created_at": now, "updated_at": now,
            "package": package, "media": media,
            "history": [{
                "timestamp": now, "from_state": None, "to_state": "prepared",
                "evidence": "Local registration only; no upload or publication performed.",
            }],
        }
        ledger["releases"].append(release)
        atomic_write(path, ledger)
    return {"ok": True, "ledger": str(path), "release": release}


def transition(args: argparse.Namespace, path: Path) -> dict:
    evidence = nonempty(args.evidence, "evidence（authorized 时必须记录人类对该包的授权摘要）")
    supplied_url = work_url(args.work_url)
    supplied_id = nonempty(args.work_id, "work-id") if args.work_id is not None else None
    with exclusive_lock(path):
        ledger = read_ledger(path)
        release = next((item for item in ledger["releases"] if item["release_id"] == args.release_id), None)
        if release is None:
            raise LedgerError("release_missing", "未找到该 release_id。")
        old = release["state"]
        target = args.state
        if target not in TRANSITIONS[old]:
            raise LedgerError(
                "invalid_transition",
                f"禁止 {old} → {target}。submitting 只能从 authorized 进入；提交未知禁止重新提交，先只读核验。",
                allowed_states=sorted(TRANSITIONS[old]),
            )
        if supplied_id and release.get("work_id") and supplied_id != release["work_id"]:
            raise LedgerError("work_identity_changed", "work-id 与该发布记录已有作品身份冲突。")
        effective_id = supplied_id or release.get("work_id")
        effective_url = supplied_url or release.get("work_url")
        if target in PLATFORM_STATES:
            if not ui_evidence(evidence):
                raise LedgerError("ui_evidence_required", "审核/发布/定时状态必须以 UI: 或 界面证据：开头，记录实际界面结果。")
            if not effective_id and not effective_url:
                raise LedgerError("work_identity_required", "审核/发布/定时状态必须提供 work-id 或 work-url，或沿用已记录身份。")
        if target == "rejected" and old in SUBMITTED_STATES and not ui_evidence(evidence):
            raise LedgerError("ui_evidence_required", "已进入提交流程的 rejected 必须记录明确 UI 拒绝/失败证据；未知不能当作拒绝。")
        verification = verify_registered_files(release) if target == "submitting" else None
        now = utc_now()
        event = {
            "timestamp": now, "from_state": old, "to_state": target,
            "evidence": evidence,
        }
        if target == "authorized":
            event["human_authorization_summary"] = evidence
        if target in PLATFORM_STATES or (target == "rejected" and old in SUBMITTED_STATES):
            event["evidence_source"] = "operator_recorded_ui; not independently verified by this tool"
        if verification:
            event["file_verification"] = verification
        if effective_id:
            release["work_id"] = effective_id
            event["work_id"] = effective_id
        if effective_url:
            release["work_url"] = effective_url
            event["work_url"] = effective_url
        release["state"] = target
        release["updated_at"] = now
        release["history"].append(event)
        atomic_write(path, ledger)
    return {"ok": True, "ledger": str(path), "release": release}


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    register_cli = commands.add_parser("register", help="登记媒体与完整 JSON 文案包；不上传")
    register_cli.add_argument("--ledger", required=True, help="账本绝对路径")
    register_cli.add_argument("--account", required=True, help="稳定账号 ID")
    register_cli.add_argument("--kind", required=True, choices=("video", "image"))
    register_cli.add_argument("--media", required=True, nargs="+", help="媒体文件，顺序即发布顺序")
    register_cli.add_argument("--package", required=True, help="非空 UTF-8 JSON 文案包绝对路径")
    transition_cli = commands.add_parser("transition", help="记录状态及证据；不会执行平台操作")
    transition_cli.add_argument("--ledger", required=True)
    transition_cli.add_argument("--release-id", required=True)
    transition_cli.add_argument("--state", required=True, choices=sorted(STATES - {"prepared"}))
    transition_cli.add_argument("--evidence", required=True)
    transition_cli.add_argument("--work-url")
    transition_cli.add_argument("--work-id")
    list_cli = commands.add_parser("list", help="只读列出完整记录和历史")
    list_cli.add_argument("--ledger", required=True)
    return cli


def main() -> int:
    args = parser().parse_args()
    try:
        path = absolute_path(args.ledger, "ledger")
        if args.command == "register":
            result = register(args, path)
        elif args.command == "transition":
            result = transition(args, path)
        else:
            result = {"ok": True, "ledger": str(path), **read_ledger(path)}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except LedgerError as exc:
        print(json.dumps({"ok": False, "error": exc.code, "message": exc.message, **exc.details}, ensure_ascii=False), file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": "local_io_error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
