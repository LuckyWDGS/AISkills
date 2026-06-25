from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import time
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path


BASE = Path(r"D:\AISkills\SessionPicture\.subagent-retry-20260608-dynamic").resolve()
SCRIPT = Path(r"C:\Users\QY\.codex\skills\session-picture\scripts\picture_store.py").resolve()
RUN = BASE / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
PYTHON = sys.executable

INDEX_REL = Path(".codex/session/assets/session-picture-index.json")
LOCK_REL = Path(".codex/session/assets/session-picture.lock")


results: list[dict] = []


def assert_allowed(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(BASE)
    except ValueError as exc:
        raise RuntimeError(f"Refusing to write outside allowed base: {resolved}") from exc
    return resolved


def ensure_dir(path: Path) -> Path:
    path = assert_allowed(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def png_bytes(width: int = 1, height: int = 1, color: tuple[int, int, int] = (0, 0, 0)) -> bytes:
    raw = bytearray()
    for _ in range(height):
        raw.append(0)
        raw.extend(bytes(color) * width)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b"")


def write_png(path: Path, color: tuple[int, int, int] = (0, 0, 0), size: tuple[int, int] = (1, 1)) -> Path:
    path = assert_allowed(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png_bytes(size[0], size[1], color))
    return path


def write_text(path: Path, text: str) -> Path:
    path = assert_allowed(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def root(name: str) -> Path:
    return ensure_dir(RUN / "roots" / name)


def index_path(project_root: Path) -> Path:
    return project_root / INDEX_REL


def load_index(project_root: Path) -> dict:
    return json.loads(index_path(project_root).read_text(encoding="utf-8"))


def save_index(project_root: Path, data: dict) -> None:
    index_path(project_root).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def item_path(project_root: Path, item: dict) -> Path:
    return (project_root / item["local_path"]).resolve()


def cmd_args(*parts: str | Path) -> list[str]:
    return [PYTHON, str(SCRIPT), *[str(part) for part in parts]]


def compact_text(text: str, limit: int = 1800) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-limit // 2 :]
    return head + "\n...[truncated]...\n" + tail


def run(name: str, *parts: str | Path, cwd: Path | None = None, timeout: float = 30.0) -> subprocess.CompletedProcess:
    args = cmd_args(*parts)
    started = time.time()
    cp = subprocess.run(args, cwd=str(cwd or RUN), text=True, capture_output=True, timeout=timeout)
    entry = {
        "name": name,
        "command": args,
        "rc": cp.returncode,
        "duration_seconds": round(time.time() - started, 3),
        "stdout": compact_text(cp.stdout),
        "stderr": compact_text(cp.stderr),
    }
    try:
        entry["json"] = json.loads(cp.stdout)
    except Exception:
        pass
    results.append(entry)
    print(f"{name}: rc={cp.returncode}")
    return cp


def add_image(project_root: Path, source: Path, tag: str, extra: list[str] | None = None) -> dict:
    extra = extra or []
    cp = run(
        f"add:{tag}",
        "add",
        source,
        "--root",
        project_root,
        "--asset-type",
        "source-media",
        "--tag",
        tag,
        "--json",
        *extra,
    )
    if cp.returncode != 0:
        raise RuntimeError(f"add failed for {tag}: {cp.stdout} {cp.stderr}")
    data = json.loads(cp.stdout)
    return data[0]


def mark_old(item: dict, days: int = 120) -> None:
    old = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
    item["created_at"] = old
    item["last_seen_at"] = old
    item["last_used_at"] = old


def record_check(name: str, passed: bool, details: dict | None = None) -> None:
    results.append({"name": name, "check": True, "passed": bool(passed), "details": details or {}})
    print(f"{name}: {'PASS' if passed else 'FAIL'}")


def no_traceback(*texts: str) -> bool:
    return all("Traceback" not in text for text in texts)


def read_lock(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_lock(path: Path, payload: dict) -> None:
    assert_allowed(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def make_many_sources(source_dir: Path, count: int) -> Path:
    source_dir = ensure_dir(source_dir)
    existing = list(source_dir.glob("img-*.png"))
    if len(existing) >= count:
        return source_dir
    for i in range(count):
        color = (i % 256, (i // 3) % 256, (i // 17) % 256)
        write_png(source_dir / f"img-{i:04d}.png", color=color)
    return source_dir


def popen_add_many(name: str, project_root: Path, source_dir: Path, heartbeat_seconds: str = "0.1") -> dict:
    stdout_path = assert_allowed(RUN / f"{name}.stdout.log")
    stderr_path = assert_allowed(RUN / f"{name}.stderr.log")
    args = cmd_args(
        "--lock-heartbeat-seconds",
        heartbeat_seconds,
        "add",
        source_dir,
        "--root",
        project_root,
        "--asset-type",
        "source-media",
        "--tag",
        name,
    )
    started = time.time()
    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
        proc = subprocess.Popen(args, cwd=str(RUN), stdout=out, stderr=err, text=True)
        return {
            "name": name,
            "args": args,
            "proc": proc,
            "started": started,
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
        }


def finish_popen(entry: dict, timeout: float = 90.0) -> dict:
    proc: subprocess.Popen = entry["proc"]
    rc = proc.wait(timeout=timeout)
    stdout = entry["stdout_path"].read_text(encoding="utf-8", errors="replace")
    stderr = entry["stderr_path"].read_text(encoding="utf-8", errors="replace")
    result = {
        "name": entry["name"],
        "command": entry["args"],
        "rc": rc,
        "duration_seconds": round(time.time() - entry["started"], 3),
        "stdout_log": str(entry["stdout_path"]),
        "stderr_log": str(entry["stderr_path"]),
        "stdout": compact_text(stdout),
        "stderr": compact_text(stderr),
    }
    results.append(result)
    print(f"{entry['name']}: rc={rc}")
    return result


def test_core_workflow() -> None:
    project_root = root("core-workflow")
    src = write_png(RUN / "sources/core.png", color=(10, 20, 30))
    run("core:init", "init", "--root", project_root)
    item = add_image(project_root, src, "core")
    find_cp = run("core:find-json", "find", "core", "--root", project_root, "--json")
    show_cp = run("core:show-json", "show", item["id"], "--root", project_root, "--json")
    doctor_cp = run("core:doctor-json", "doctor", "--root", project_root, "--json")
    cleanup_cp = run("core:cleanup-dry-json", "cleanup", "--root", project_root, "--json", "--min-age-days", "0")
    show_json = json.loads(show_cp.stdout)
    doctor_json = json.loads(doctor_cp.stdout)
    cleanup_json = json.loads(cleanup_cp.stdout)
    record_check(
        "core workflow doctor/show/cleanup",
        find_cp.returncode == 0
        and show_cp.returncode == 0
        and show_json.get("trusted_path")
        and doctor_cp.returncode == 0
        and doctor_json.get("ok") is True
        and cleanup_cp.returncode == 0
        and cleanup_json.get("candidates") == [],
        {"id": item["id"], "trusted_path": show_json.get("trusted_path")},
    )


def test_find_verify_tamper_hash() -> None:
    project_root = root("tamper-hash")
    src = write_png(RUN / "sources/tamper-original.png", color=(40, 0, 0))
    item = add_image(project_root, src, "tamper-hash")
    stored = item_path(project_root, item)
    write_png(stored, color=(41, 0, 0))
    cp = run("tamper-hash:find-verify-json", "find", "tamper-hash", "--root", project_root, "--verify", "--json")
    data = json.loads(cp.stdout)
    first = data[0] if data else {}
    record_check(
        "find --verify tamper hash trusted_path null and rc=3",
        cp.returncode == 3
        and first.get("trusted_path") is None
        and first.get("verification") == "sha256 mismatch"
        and no_traceback(cp.stdout, cp.stderr),
        {"rc": cp.returncode, "trusted_path": first.get("trusted_path"), "verification": first.get("verification")},
    )


def test_cleanup_active_without_include_unused() -> None:
    project_root = root("cleanup-active")
    src = write_png(RUN / "sources/active-cleanup.png", color=(0, 50, 0))
    item = add_image(project_root, src, "active-cleanup")
    index = load_index(project_root)
    indexed = index["items"][0]
    mark_old(indexed)
    save_index(project_root, index)
    path = item_path(project_root, item)
    before_exists = path.exists()
    cp = run(
        "cleanup-active:statuses-active-apply-no-include-unused",
        "cleanup",
        "--root",
        project_root,
        "--statuses",
        "active",
        "--min-age-days",
        "0",
        "--apply",
        "--json",
    )
    after = load_index(project_root)["items"][0]
    data = json.loads(cp.stdout)
    record_check(
        "cleanup --statuses active --apply without --include-unused does not delete",
        cp.returncode == 0
        and data.get("candidates") == []
        and before_exists
        and path.exists()
        and after.get("status") == "active",
        {"rc": cp.returncode, "candidates": data.get("candidates"), "file_exists": path.exists(), "status": after.get("status")},
    )


def test_thread_only_update_failure() -> None:
    project_root = root("thread-only-update")
    cp = run(
        "thread-only:create-json",
        "thread-only",
        "--root",
        project_root,
        "--asset-type",
        "unclassified",
        "--tag",
        "thread-only",
        "--json",
    )
    item = json.loads(cp.stdout)[0]
    before = index_path(project_root).read_bytes()
    update_cp = run("thread-only:update-status-active-json", "update", item["id"], "--root", project_root, "--status", "active", "--json")
    after = index_path(project_root).read_bytes()
    err = json.loads(update_cp.stdout)
    record_check(
        "thread-only update --status active fails and leaves index unchanged",
        update_cp.returncode == 2
        and "Cannot change lifecycle storage" in err.get("error", "")
        and before == after
        and no_traceback(update_cp.stdout, update_cp.stderr),
        {"rc": update_cp.returncode, "error": err.get("error"), "index_unchanged": before == after},
    )


def test_self_supersede_failure() -> None:
    project_root = root("self-supersede")
    src = write_png(RUN / "sources/self-supersede.png", color=(0, 0, 60))
    item = add_image(project_root, src, "self-supersede")
    before = index_path(project_root).read_bytes()
    cp = run("self-supersede:json", "supersede", item["id"], item["id"], "--root", project_root, "--json")
    after = index_path(project_root).read_bytes()
    err = json.loads(cp.stdout)
    record_check(
        "self supersede fails and leaves index unchanged",
        cp.returncode == 2
        and "Cannot supersede an image with itself" in err.get("error", "")
        and before == after
        and no_traceback(cp.stdout, cp.stderr),
        {"rc": cp.returncode, "error": err.get("error"), "index_unchanged": before == after},
    )


def test_absolute_local_path_tamper_show_cleanup() -> None:
    project_root = root("absolute-local-path")
    src = write_png(RUN / "sources/absolute-source.png", color=(70, 0, 70))
    external = write_png(RUN / "external-sentinel.png", color=(1, 2, 3))
    item = add_image(project_root, src, "absolute-local-path")
    index = load_index(project_root)
    indexed = index["items"][0]
    indexed["local_path"] = str(external.resolve())
    indexed["status"] = "stale-delete-soon"
    mark_old(indexed)
    save_index(project_root, index)
    before_external = external.read_bytes()
    show_cp = run("absolute-local-path:show-json", "show", item["id"], "--root", project_root, "--json")
    cleanup_cp = run(
        "absolute-local-path:cleanup-apply-json",
        "cleanup",
        "--root",
        project_root,
        "--min-age-days",
        "0",
        "--apply",
        "--json",
    )
    show_data = json.loads(show_cp.stdout)
    cleanup_data = json.loads(cleanup_cp.stdout)
    record_check(
        "absolute local_path tamper: show/cleanup json no traceback and external file kept",
        show_cp.returncode == 3
        and cleanup_cp.returncode == 0
        and show_data.get("trusted_path") is None
        and show_data.get("resolved_path") is None
        and show_data.get("verification") == "local_path must be project-relative"
        and cleanup_data.get("candidates") == []
        and external.exists()
        and external.read_bytes() == before_external
        and no_traceback(show_cp.stdout, show_cp.stderr, cleanup_cp.stdout, cleanup_cp.stderr),
        {
            "show_rc": show_cp.returncode,
            "cleanup_rc": cleanup_cp.returncode,
            "verification": show_data.get("verification"),
            "external_exists": external.exists(),
            "cleanup_candidates": cleanup_data.get("candidates"),
        },
    )


def test_invalid_add_does_not_create_store() -> None:
    project_root = root("invalid-add")
    invalid = write_text(project_root / "not-an-image.txt", "not an image")
    session_dir = project_root / ".codex/session"
    cp = run("invalid-add:no-session-created", "add", invalid, "--root", project_root, "--json")
    data = json.loads(cp.stdout)
    record_check(
        "invalid add does not create .codex/session",
        cp.returncode == 2
        and "Source does not look like an image" in data.get("error", "")
        and not session_dir.exists()
        and no_traceback(cp.stdout, cp.stderr),
        {"rc": cp.returncode, "error": data.get("error"), "session_exists": session_dir.exists()},
    )


def test_heartbeat_refresh() -> None:
    project_root = root("heartbeat-refresh")
    source_dir = make_many_sources(RUN / "sources/heartbeat-many", 2500)
    run("heartbeat-refresh:init", "init", "--root", project_root)
    lock_path = project_root / LOCK_REL
    entry = popen_add_many("heartbeat-refresh-add", project_root, source_dir)
    observed: list[dict] = []
    changed = False
    token = None
    first_heartbeat = None
    deadline = time.time() + 75
    while time.time() < deadline:
        payload = read_lock(lock_path)
        if payload:
            observed.append({"t": round(time.time(), 3), "token": payload.get("token"), "heartbeat_at": payload.get("heartbeat_at")})
            token = token or payload.get("token")
            first_heartbeat = first_heartbeat or payload.get("heartbeat_at")
            if payload.get("token") == token and payload.get("heartbeat_at") != first_heartbeat:
                changed = True
        if entry["proc"].poll() is not None:
            break
        time.sleep(0.05)
    result = finish_popen(entry, timeout=90)
    record_check(
        "heartbeat payload refreshes while token stays stable",
        result["rc"] == 0 and changed and len({o.get("token") for o in observed if o.get("token")}) == 1 and not lock_path.exists(),
        {
            "rc": result["rc"],
            "samples": len(observed),
            "changed": changed,
            "unique_tokens": sorted({o.get("token") for o in observed if o.get("token")}),
            "first": observed[0] if observed else None,
            "last": observed[-1] if observed else None,
            "lock_exists_after": lock_path.exists(),
        },
    )


def test_foreign_token_not_released_and_stale_cleanup() -> None:
    project_root = root("foreign-token-stale-lock")
    source_dir = make_many_sources(RUN / "sources/foreign-token-many", 2500)
    run("foreign-token:init", "init", "--root", project_root)
    lock_path = project_root / LOCK_REL
    entry = popen_add_many("foreign-token-add", project_root, source_dir)
    foreign_payload = None
    deadline = time.time() + 75
    while time.time() < deadline:
        payload = read_lock(lock_path)
        if payload:
            foreign_payload = dict(payload)
            foreign_payload["token"] = "foreign-token-subagent"
            foreign_payload["heartbeat_at"] = datetime.now(timezone.utc).isoformat()
            write_lock(lock_path, foreign_payload)
            break
        if entry["proc"].poll() is not None:
            break
        time.sleep(0.05)
    result = finish_popen(entry, timeout=90)
    after_foreign = read_lock(lock_path)
    foreign_preserved = result["rc"] == 0 and after_foreign and after_foreign.get("token") == "foreign-token-subagent"

    stale_payload = {
        "token": "stale-token-subagent",
        "pid": 0,
        "created_at": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(),
        "heartbeat_at": (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(),
        "root": str(project_root),
    }
    write_lock(lock_path, stale_payload)
    stale_cp = run(
        "stale-lock:doctor-json",
        "--lock-timeout-seconds",
        "2",
        "doctor",
        "--root",
        project_root,
        "--json",
        timeout=45,
    )
    stale_data = json.loads(stale_cp.stdout)
    record_check(
        "foreign token is not released and stale lock is cleaned",
        bool(foreign_preserved)
        and stale_cp.returncode == 0
        and stale_data.get("ok") is True
        and not lock_path.exists()
        and no_traceback(stale_cp.stdout, stale_cp.stderr),
        {
            "foreign_add_rc": result["rc"],
            "foreign_preserved": bool(foreign_preserved),
            "foreign_lock_after": after_foreign,
            "stale_doctor_rc": stale_cp.returncode,
            "stale_lock_exists_after": lock_path.exists(),
        },
    )


def test_concurrent_add() -> None:
    project_root = root("concurrent-add")
    run("concurrent:init", "init", "--root", project_root)
    sources = [write_png(RUN / f"sources/concurrent-{i}.png", color=(90 + i, i * 10, 120)) for i in range(6)]
    procs = []
    for i, src in enumerate(sources):
        stdout_path = assert_allowed(RUN / f"concurrent-{i}.stdout.log")
        stderr_path = assert_allowed(RUN / f"concurrent-{i}.stderr.log")
        args = cmd_args(
            "--lock-timeout-seconds",
            "10",
            "add",
            src,
            "--root",
            project_root,
            "--asset-type",
            "source-media",
            "--tag",
            f"concurrent-{i}",
            "--json",
        )
        out = stdout_path.open("w", encoding="utf-8")
        err = stderr_path.open("w", encoding="utf-8")
        proc = subprocess.Popen(args, cwd=str(RUN), stdout=out, stderr=err, text=True)
        procs.append((i, proc, out, err, stdout_path, stderr_path, args))
    process_results = []
    for i, proc, out, err, stdout_path, stderr_path, args in procs:
        rc = proc.wait(timeout=30)
        out.close()
        err.close()
        process_results.append(
            {
                "i": i,
                "rc": rc,
                "stdout": compact_text(stdout_path.read_text(encoding="utf-8", errors="replace")),
                "stderr": compact_text(stderr_path.read_text(encoding="utf-8", errors="replace")),
                "stdout_log": str(stdout_path),
                "stderr_log": str(stderr_path),
                "command": args,
            }
        )
    results.append({"name": "concurrent-add:processes", "processes": process_results})
    doctor_cp = run("concurrent:doctor-json", "doctor", "--root", project_root, "--json")
    index = load_index(project_root)
    record_check(
        "concurrent add serializes cleanly",
        all(p["rc"] == 0 for p in process_results)
        and len(index["items"]) == len(sources)
        and doctor_cp.returncode == 0
        and json.loads(doctor_cp.stdout).get("ok") is True
        and all(no_traceback(p["stdout"], p["stderr"]) for p in process_results),
        {"rcs": [p["rc"] for p in process_results], "item_count": len(index["items"]), "doctor_rc": doctor_cp.returncode},
    )


def main() -> int:
    ensure_dir(RUN)
    ensure_dir(RUN / "sources")
    print(f"run_dir={RUN}")
    tests = [
        test_core_workflow,
        test_find_verify_tamper_hash,
        test_cleanup_active_without_include_unused,
        test_thread_only_update_failure,
        test_self_supersede_failure,
        test_absolute_local_path_tamper_show_cleanup,
        test_invalid_add_does_not_create_store,
        test_heartbeat_refresh,
        test_foreign_token_not_released_and_stale_cleanup,
        test_concurrent_add,
    ]
    failures = []
    for test in tests:
        try:
            test()
        except Exception as exc:
            failures.append({"test": test.__name__, "error": f"{type(exc).__name__}: {exc}"})
            results.append({"name": test.__name__, "exception": f"{type(exc).__name__}: {exc}"})
            print(f"{test.__name__}: EXCEPTION {type(exc).__name__}: {exc}")
    checks = [entry for entry in results if entry.get("check")]
    summary = {
        "run_dir": str(RUN),
        "script": str(SCRIPT),
        "checks_total": len(checks),
        "checks_passed": sum(1 for entry in checks if entry.get("passed")),
        "checks_failed": [entry for entry in checks if not entry.get("passed")],
        "exceptions": failures,
        "results": results,
    }
    (RUN / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (BASE / "latest-run.txt").write_text(str(RUN) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("run_dir", "checks_total", "checks_passed", "checks_failed", "exceptions")}, ensure_ascii=False, indent=2))
    return 0 if not failures and not summary["checks_failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
