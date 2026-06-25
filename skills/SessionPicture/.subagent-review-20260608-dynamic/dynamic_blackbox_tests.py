import base64
import binascii
import json
import os
import shutil
import subprocess
import sys
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path


SCRIPT = Path(r"C:\Users\QY\.codex\skills\session-picture\scripts\picture_store.py")
REVIEW_ROOT = Path(r"D:\AISkills\SessionPicture\.subagent-review-20260608-dynamic")
RUN_ROOT = REVIEW_ROOT / ("run-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
PYTHON = sys.executable

COMMANDS = []
RESULTS = []


def ensure_within_review(path: Path) -> Path:
    resolved = path.resolve()
    review = REVIEW_ROOT.resolve()
    if not str(resolved).lower().startswith(str(review).lower() + os.sep.lower()) and resolved != review:
        raise RuntimeError(f"path escapes review root: {resolved}")
    return resolved


def write_text(path: Path, text: str) -> None:
    ensure_within_review(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_bytes(path: Path, data: bytes) -> None:
    ensure_within_review(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def remove_path(path: Path) -> None:
    ensure_within_review(path)
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def make_root(name: str) -> Path:
    root = ensure_within_review(RUN_ROOT / name)
    root.mkdir(parents=True, exist_ok=True)
    return root


def png_bytes(rgb=(255, 0, 0), size=(1, 1)) -> bytes:
    width, height = size
    row = b"\x00" + bytes(rgb) * width
    raw = row * height

    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = binascii.crc32(kind + payload) & 0xFFFFFFFF
        return len(payload).to_bytes(4, "big") + kind + payload + crc.to_bytes(4, "big")

    ihdr = (
        width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
    )
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def write_png(path: Path, rgb=(255, 0, 0), size=(1, 1)) -> None:
    write_bytes(path, png_bytes(rgb, size))


def command_name(args):
    parts = []
    for part in args:
        if part.startswith("--lock-"):
            continue
        parts.append(part)
    return parts[0] if parts else "unknown"


def run_pic(args, name=None, cwd=None, timeout=30):
    if name is None:
        name = f"{len(COMMANDS) + 1:03d}-{command_name(args)}"
    cmd = [PYTHON, str(SCRIPT)] + [str(a) for a in args]
    start = time.monotonic()
    proc = subprocess.run(cmd, cwd=str(cwd or RUN_ROOT), text=True, capture_output=True, timeout=timeout)
    elapsed = time.monotonic() - start
    entry = {
        "name": name,
        "cmd": cmd,
        "cwd": str(cwd or RUN_ROOT),
        "returncode": proc.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    COMMANDS.append(entry)
    log_dir = RUN_ROOT / "command-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:80]
    write_text(log_dir / f"{safe}.json", json.dumps(entry, ensure_ascii=False, indent=2))
    return proc


def parse_json_output(proc):
    text = proc.stdout.strip()
    if not text:
        return None
    return json.loads(text)


def idx_path(root: Path) -> Path:
    return root / ".codex" / "session" / "assets" / "session-picture-index.json"


def lock_path(root: Path) -> Path:
    return root / ".codex" / "session" / "assets" / "session-picture.lock"


def session_dir(root: Path) -> Path:
    return root / ".codex" / "session"


def load_index(root: Path):
    return json.loads(idx_path(root).read_text(encoding="utf-8"))


def save_index(root: Path, data):
    write_text(idx_path(root), json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def items(root: Path):
    return load_index(root).get("items", [])


def abs_local(root: Path, item) -> Path:
    return root / item["local_path"]


def result(name, ok, details=None):
    RESULTS.append({"name": name, "ok": bool(ok), "details": details or {}})


def expect(name, condition, details=None):
    result(name, condition, details)
    return condition


def command_excerpt(proc):
    out = proc.stdout.strip().replace("\r\n", "\n")
    err = proc.stderr.strip().replace("\r\n", "\n")
    return {
        "returncode": proc.returncode,
        "stdout_head": out[:800],
        "stderr_head": err[:800],
    }


def basic_workflow():
    root = make_root("basic-workflow")
    inputs = root / "_inputs"
    write_png(inputs / "red.png", (255, 0, 0))
    write_png(inputs / "blue.png", (0, 0, 255))
    write_png(inputs / "yellow.png", (255, 255, 0))
    data_url = "data:image/png;base64," + base64.b64encode(png_bytes((0, 255, 0))).decode("ascii")
    write_text(inputs / "green.dataurl.txt", data_url)

    p_init = run_pic(["init", "--root", root], "basic-init")
    p_add = run_pic([
        "add", inputs / "red.png", "--root", root, "--asset-type", "source-media",
        "--tag", "alpha", "--caption", "Red local import", "--json"
    ], "basic-add")
    red = parse_json_output(p_add)[0]

    p_find = run_pic(["find", "alpha", "--root", root, "--verify", "--json"], "basic-find-verify")
    p_show = run_pic(["show", red["id"], "--root", root, "--json"], "basic-show")
    show_data = parse_json_output(p_show)
    p_update = run_pic([
        "update", red["id"], "--root", root, "--tag", "alpha,reviewed",
        "--caption", "Updated red caption", "--json"
    ], "basic-update")

    p_add_blue = run_pic([
        "add", inputs / "blue.png", "--root", root, "--asset-type", "source-media",
        "--tag", "successor", "--json"
    ], "basic-add-blue")
    blue = parse_json_output(p_add_blue)[0]

    p_sup = run_pic(["supersede", red["id"], blue["id"], "--root", root, "--json"], "basic-supersede")

    p_data = run_pic([
        "add-data-url", inputs / "green.dataurl.txt", "--root", root,
        "--asset-type", "generated-image", "--tag", "data-url", "--json"
    ], "basic-add-data-url")

    p_thread = run_pic([
        "thread-only", "--root", root, "--asset-type", "unclassified",
        "--tag", "pathless", "--caption", "Visible only in thread", "--json"
    ], "basic-thread-only")

    p_cleanup_add = run_pic([
        "add", inputs / "yellow.png", "--root", root, "--asset-type", "bug-screenshot",
        "--tag", "cleanup-target", "--json"
    ], "basic-add-cleanup-target")
    cleanup_item = parse_json_output(p_cleanup_add)[0]
    cleanup_path = abs_local(root, cleanup_item)
    p_update_cleanup = run_pic([
        "update", cleanup_item["id"], "--root", root, "--status", "stale-delete-soon", "--json"
    ], "basic-update-cleanup-target")
    p_cleanup_dry = run_pic([
        "cleanup", "--root", root, "--min-age-days", "0", "--statuses", "stale-delete-soon", "--json"
    ], "basic-cleanup-dry")
    p_cleanup_apply = run_pic([
        "cleanup", "--root", root, "--min-age-days", "0", "--statuses", "stale-delete-soon", "--apply", "--json"
    ], "basic-cleanup-apply")
    p_doctor = run_pic(["doctor", "--root", root, "--json"], "basic-doctor")

    idx = load_index(root)
    id_map = {i["id"]: i for i in idx["items"]}
    expect("basic: init/add/find/show/update/supersede/add-data-url/thread-only/cleanup/doctor return codes",
           all(p.returncode == 0 for p in [
               p_init, p_add, p_find, p_show, p_update, p_add_blue, p_sup, p_data,
               p_thread, p_cleanup_add, p_update_cleanup, p_cleanup_dry, p_cleanup_apply, p_doctor
           ]),
           {
               "commands": {
                   "init": command_excerpt(p_init),
                   "add": command_excerpt(p_add),
                   "find": command_excerpt(p_find),
                   "show": command_excerpt(p_show),
                   "update": command_excerpt(p_update),
                   "supersede": command_excerpt(p_sup),
                   "add-data-url": command_excerpt(p_data),
                   "thread-only": command_excerpt(p_thread),
                   "cleanup-apply": command_excerpt(p_cleanup_apply),
                   "doctor": command_excerpt(p_doctor),
               }
           })
    expect("basic: show returned a trusted path",
           p_show.returncode == 0 and show_data.get("verification") == "ok" and bool(show_data.get("trusted_path")),
           show_data)
    expect("basic: update changed caption/tag",
           id_map[red["id"]]["caption"] == "Updated red caption" and "reviewed" in id_map[red["id"]]["tags"],
           id_map[red["id"]])
    expect("basic: supersede linked old and new records",
           id_map[red["id"]]["status"] == "superseded" and id_map[red["id"]]["superseded_by"] == blue["id"] and red["id"] in id_map[blue["id"]]["supersedes"],
           {"old": id_map[red["id"]], "new": id_map[blue["id"]]})
    thread_item_raw = parse_json_output(p_thread)
    thread_item = thread_item_raw[0] if isinstance(thread_item_raw, list) else thread_item_raw
    expect("basic: thread-only has no durable local path",
           thread_item.get("status") == "thread-only" and not thread_item.get("local_path"),
           thread_item)
    expect("basic: cleanup apply removed stale-delete-soon file and marked record deleted",
           not cleanup_path.exists() and id_map[cleanup_item["id"]]["status"] == "deleted",
           {"cleanup_path_exists": cleanup_path.exists(), "item": id_map[cleanup_item["id"]]})


def fresh_root_readonly():
    root = make_root("fresh-root-readonly")
    commands = {
        "doctor": ["doctor", "--root", root],
        "find": ["find", "anything", "--root", root],
        "show": ["show", "asset_missing", "--root", root],
        "update": ["update", "asset_missing", "--root", root, "--tag", "x"],
        "supersede": ["supersede", "asset_a", "asset_b", "--root", root],
        "cleanup": ["cleanup", "--root", root],
    }
    excerpts = {}
    for name, args in commands.items():
        proc = run_pic(args, f"fresh-{name}")
        excerpts[name] = command_excerpt(proc)
    expect("fresh-root: read-only commands fail and do not initialize .codex",
           all(v["returncode"] != 0 for v in excerpts.values()) and not (root / ".codex").exists(),
           excerpts | {"codex_exists": (root / ".codex").exists()})


def batch_add_rollback():
    root = make_root("batch-rollback")
    inputs = root / "_inputs"
    write_png(inputs / "valid.png", (1, 2, 3))
    write_text(inputs / "invalid.txt", "not an image\n")
    p_init = run_pic(["init", "--root", root], "rollback-init")
    p_add = run_pic([
        "add", inputs / "valid.png", inputs / "invalid.txt", "--root", root,
        "--asset-type", "source-media", "--json"
    ], "rollback-add-valid-plus-invalid")
    active_dir = root / ".codex" / "session" / "assets" / "active" / "session-picture"
    copied = list(active_dir.rglob("*")) if active_dir.exists() else []
    current_items = items(root)
    expect("batch-add rollback: mixed valid/invalid batch fails with no copied files and no index items",
           p_init.returncode == 0 and p_add.returncode != 0 and len(current_items) == 0 and not any(p.is_file() for p in copied),
           {"add": command_excerpt(p_add), "item_count": len(current_items), "copied_files": [str(p) for p in copied if p.is_file()]})


def path_escape():
    root = make_root("path-escape")
    inputs = root / "_inputs"
    write_png(inputs / "safe.png", (5, 6, 7))
    escape_target = root / "escape-target.png"
    write_png(escape_target, (8, 9, 10))
    run_pic(["init", "--root", root], "escape-init")
    p_add = run_pic(["add", inputs / "safe.png", "--root", root, "--asset-type", "source-media", "--json"], "escape-add")
    item = parse_json_output(p_add)[0]
    idx = load_index(root)
    idx["items"][0]["local_path"] = str(escape_target)
    idx["items"][0]["status"] = "stale-delete-soon"
    save_index(root, idx)
    p_show = run_pic(["show", item["id"], "--root", root, "--json"], "escape-show")
    p_cleanup = run_pic([
        "cleanup", "--root", root, "--min-age-days", "0", "--statuses", "stale-delete-soon", "--apply", "--json"
    ], "escape-cleanup-apply")
    p_doctor = run_pic(["doctor", "--root", root, "--json"], "escape-doctor")
    expect("path-escape: tampered absolute local_path is not trusted and outside file is not deleted",
           p_show.returncode != 0 and p_doctor.returncode != 0 and escape_target.exists(),
           {"show": command_excerpt(p_show), "cleanup": command_excerpt(p_cleanup), "doctor": command_excerpt(p_doctor), "escape_target_exists": escape_target.exists()})


def tamper_hash_cleanup():
    root = make_root("tamper-hash")
    inputs = root / "_inputs"
    write_png(inputs / "original.png", (9, 0, 0))
    run_pic(["init", "--root", root], "tamper-init")
    p_add = run_pic(["add", inputs / "original.png", "--root", root, "--asset-type", "source-media", "--json"], "tamper-add")
    item = parse_json_output(p_add)[0]
    run_pic(["update", item["id"], "--root", root, "--status", "stale-delete-soon", "--json"], "tamper-mark-stale")
    item = {i["id"]: i for i in items(root)}[item["id"]]
    stored = abs_local(root, item)
    write_png(stored, (0, 9, 0))
    p_show = run_pic(["show", item["id"], "--root", root, "--json"], "tamper-show")
    p_cleanup = run_pic([
        "cleanup", "--root", root, "--min-age-days", "0", "--statuses", "stale-delete-soon", "--apply", "--json"
    ], "tamper-cleanup-apply")
    after = {i["id"]: i for i in items(root)}[item["id"]]
    expect("tamper-hash: show fails and cleanup preserves mismatched file as integrity-failed",
           p_show.returncode != 0 and stored.exists() and after["status"] == "integrity-failed",
           {"show": command_excerpt(p_show), "cleanup": command_excerpt(p_cleanup), "stored_exists": stored.exists(), "item": after})


def missing_readd():
    root = make_root("missing-readd")
    inputs = root / "_inputs"
    write_png(inputs / "same.png", (1, 9, 1))
    run_pic(["init", "--root", root], "missing-init")
    p_add = run_pic(["add", inputs / "same.png", "--root", root, "--asset-type", "source-media", "--tag", "same", "--json"], "missing-add")
    item = parse_json_output(p_add)[0]
    stored = abs_local(root, item)
    remove_path(stored)
    p_show_missing = run_pic(["show", item["id"], "--root", root, "--json"], "missing-show-after-delete")
    p_readd = run_pic(["add", inputs / "same.png", "--root", root, "--asset-type", "source-media", "--tag", "same", "--json"], "missing-readd-same-source")
    all_items = items(root)
    active_same_sha = [i for i in all_items if i["sha256"] == item["sha256"] and i["status"] == "active"]
    expect("missing re-add: deleted stored copy is repaired instead of duplicated",
           p_show_missing.returncode != 0 and p_readd.returncode == 0 and len(all_items) == 1 and len(active_same_sha) == 1 and abs_local(root, active_same_sha[0]).exists(),
           {"show_missing": command_excerpt(p_show_missing), "readd": command_excerpt(p_readd), "items": all_items})


def handoff_protection():
    root = make_root("handoff-protection")
    inputs = root / "_inputs"
    write_png(inputs / "keep.png", (2, 2, 8))
    run_pic(["init", "--root", root], "handoff-init")
    p_add = run_pic(["add", inputs / "keep.png", "--root", root, "--asset-type", "source-media", "--json"], "handoff-add")
    item = parse_json_output(p_add)[0]
    run_pic(["update", item["id"], "--root", root, "--status", "stale-delete-soon", "--json"], "handoff-mark-stale")
    item = {i["id"]: i for i in items(root)}[item["id"]]
    stored = abs_local(root, item)
    write_text(root / ".codex" / "session" / "HANDOFF.md", f"# Handoff\n\nKeep referenced asset {item['id']} at {item['local_path']}.\n")
    p_cleanup = run_pic([
        "cleanup", "--root", root, "--min-age-days", "0", "--statuses", "stale-delete-soon", "--apply", "--json"
    ], "handoff-cleanup-apply")
    after = {i["id"]: i for i in items(root)}[item["id"]]
    expect("handoff protection: cleanup does not delete stale item referenced by HANDOFF.md",
           p_cleanup.returncode == 0 and stored.exists() and after["status"] == "stale-delete-soon",
           {"cleanup": command_excerpt(p_cleanup), "stored_exists": stored.exists(), "item": after})


def lock_tests():
    root = make_root("locks")
    inputs = root / "_inputs"
    write_png(inputs / "one.png", (3, 3, 3))
    run_pic(["init", "--root", root], "lock-init")

    lp = lock_path(root)
    now = datetime.now(timezone.utc).isoformat()
    write_text(lp, json.dumps({"token": "foreign-token", "owner": "manual-test", "heartbeat_at": now}, indent=2))
    p_foreign = run_pic(["--lock-timeout-seconds", "1", "doctor", "--root", root, "--json"], "lock-foreign-timeout", timeout=5)
    foreign_still = lp.exists() and "foreign-token" in lp.read_text(encoding="utf-8")
    expect("lock: foreign active token is not released by waiting command timeout",
           p_foreign.returncode != 0 and foreign_still,
           {"doctor": command_excerpt(p_foreign), "lock_exists": lp.exists(), "lock_text": lp.read_text(encoding="utf-8") if lp.exists() else None})
    remove_path(lp)

    stale_time = time.time() - (7 * 60 * 60)
    write_text(lp, json.dumps({"token": "stale-token", "owner": "manual-test-without-heartbeat"}, indent=2))
    os.utime(lp, (stale_time, stale_time))
    p_stale = run_pic(["doctor", "--root", root, "--json"], "lock-stale-cleared", timeout=10)
    expect("lock: stale no-heartbeat lock older than six hours is cleared",
           p_stale.returncode == 0 and not lp.exists(),
           {"doctor": command_excerpt(p_stale), "lock_exists_after": lp.exists()})

    write_text(lp, json.dumps({"token": "wait-token", "owner": "manual-wait", "heartbeat_at": datetime.now(timezone.utc).isoformat()}, indent=2))
    wait_cmd = [PYTHON, str(SCRIPT), "--lock-timeout-seconds", "5", "doctor", "--root", str(root), "--json"]
    start = time.monotonic()
    waiter = subprocess.Popen(wait_cmd, cwd=str(RUN_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(1.4)
    remove_path(lp)
    out, err = waiter.communicate(timeout=10)
    elapsed = time.monotonic() - start
    COMMANDS.append({
        "name": "lock-wait-external-release",
        "cmd": wait_cmd,
        "cwd": str(RUN_ROOT),
        "returncode": waiter.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "stdout": out,
        "stderr": err,
    })
    write_text(RUN_ROOT / "command-logs" / "lock-wait-external-release.json", json.dumps(COMMANDS[-1], ensure_ascii=False, indent=2))
    expect("lock: command waits for active lock and proceeds after lock is released",
           waiter.returncode == 0 and elapsed >= 1.0,
           {"returncode": waiter.returncode, "elapsed_seconds": round(elapsed, 3), "stdout_head": out[:800], "stderr_head": err[:800]})

    heartbeat_root = make_root("heartbeat-concurrency")
    hb_inputs = heartbeat_root / "_inputs" / "many"
    hb_inputs.mkdir(parents=True, exist_ok=True)
    image_count = 1200
    for i in range(image_count):
        write_png(hb_inputs / f"img-{i:04d}.png", (i % 251, (i * 3) % 251, (i * 7) % 251))
    run_pic(["init", "--root", heartbeat_root], "heartbeat-init")
    hb_lp = lock_path(heartbeat_root)
    add_cmd = [
        PYTHON, str(SCRIPT), "--lock-heartbeat-seconds", "1",
        "add", str(hb_inputs), "--root", str(heartbeat_root),
        "--asset-type", "generated-image", "--tag", "heartbeat"
    ]
    add_proc = subprocess.Popen(add_cmd, cwd=str(RUN_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    mtimes = []
    lock_seen = False
    waiter_proc = None
    waiter_start = None
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline and add_proc.poll() is None:
        if hb_lp.exists():
            lock_seen = True
            mtimes.append(hb_lp.stat().st_mtime_ns)
            if waiter_proc is None:
                waiter_cmd = [PYTHON, str(SCRIPT), "--lock-timeout-seconds", "180", "doctor", "--root", str(heartbeat_root), "--json"]
                waiter_start = time.monotonic()
                waiter_proc = subprocess.Popen(waiter_cmd, cwd=str(RUN_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(0.2)
    add_out, add_err = add_proc.communicate(timeout=120)
    if waiter_proc is not None:
        wait_out, wait_err = waiter_proc.communicate(timeout=120)
        waiter_elapsed = time.monotonic() - waiter_start
        waiter_rc = waiter_proc.returncode
    else:
        wait_out = wait_err = ""
        waiter_elapsed = 0
        waiter_rc = None
    COMMANDS.append({
        "name": "heartbeat-long-add",
        "cmd": add_cmd,
        "cwd": str(RUN_ROOT),
        "returncode": add_proc.returncode,
        "elapsed_seconds": None,
        "stdout": add_out[:2000],
        "stderr": add_err[:2000],
        "stdout_truncated": len(add_out) > 2000,
        "stderr_truncated": len(add_err) > 2000,
    })
    write_text(RUN_ROOT / "command-logs" / "heartbeat-long-add.json", json.dumps(COMMANDS[-1], ensure_ascii=False, indent=2))
    COMMANDS.append({
        "name": "heartbeat-concurrent-doctor",
        "cmd": [PYTHON, str(SCRIPT), "--lock-timeout-seconds", "180", "doctor", "--root", str(heartbeat_root), "--json"],
        "cwd": str(RUN_ROOT),
        "returncode": waiter_rc,
        "elapsed_seconds": round(waiter_elapsed, 3),
        "stdout": wait_out[:2000],
        "stderr": wait_err[:2000],
        "stdout_truncated": len(wait_out) > 2000,
        "stderr_truncated": len(wait_err) > 2000,
    })
    write_text(RUN_ROOT / "command-logs" / "heartbeat-concurrent-doctor.json", json.dumps(COMMANDS[-1], ensure_ascii=False, indent=2))
    distinct_mtimes = len(set(mtimes))
    expect("lock: heartbeat refreshes while long add holds lock",
           add_proc.returncode == 0 and lock_seen and distinct_mtimes >= 2 and not hb_lp.exists(),
           {"add_returncode": add_proc.returncode, "lock_seen": lock_seen, "distinct_mtimes": distinct_mtimes, "samples": len(mtimes), "lock_exists_after": hb_lp.exists(), "image_count": image_count})
    expect("concurrency: doctor waits behind long add and succeeds",
           waiter_rc == 0 and waiter_elapsed >= 0.5,
           {"doctor_returncode": waiter_rc, "doctor_elapsed_seconds": round(waiter_elapsed, 3), "stdout_head": wait_out[:800], "stderr_head": wait_err[:800]})


def write_report():
    summary = {
        "script": str(SCRIPT),
        "review_root": str(REVIEW_ROOT),
        "run_root": str(RUN_ROOT),
        "started_at": datetime.now().astimezone().isoformat(),
        "results": RESULTS,
        "commands": [
            {k: v for k, v in c.items() if k not in {"stdout", "stderr"}}
            for c in COMMANDS
        ],
        "pass_count": sum(1 for r in RESULTS if r["ok"]),
        "fail_count": sum(1 for r in RESULTS if not r["ok"]),
    }
    write_text(RUN_ROOT / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
    lines = [
        "# Dynamic Black-Box Test Report",
        "",
        f"- Script: `{SCRIPT}`",
        f"- Run root: `{RUN_ROOT}`",
        f"- Commands run: {len(COMMANDS)}",
        f"- Checks passed: {summary['pass_count']}",
        f"- Checks failed: {summary['fail_count']}",
        "",
        "## Checks",
        "",
    ]
    for r in RESULTS:
        lines.append(f"- {'PASS' if r['ok'] else 'FAIL'}: {r['name']}")
    lines.extend(["", "## Command Index", ""])
    for c in COMMANDS:
        cmd = " ".join(f'"{x}"' if " " in x else x for x in c["cmd"])
        lines.append(f"- `{c['name']}` rc={c['returncode']} elapsed={c.get('elapsed_seconds')}: `{cmd}`")
    write_text(RUN_ROOT / "REPORT.md", "\n".join(lines) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main():
    ensure_within_review(RUN_ROOT)
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    if not SCRIPT.exists():
        raise SystemExit(f"target script missing: {SCRIPT}")
    basic_workflow()
    fresh_root_readonly()
    batch_add_rollback()
    path_escape()
    tamper_hash_cleanup()
    missing_readd()
    handoff_protection()
    lock_tests()
    write_report()
    failures = [r for r in RESULTS if not r["ok"]]
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
