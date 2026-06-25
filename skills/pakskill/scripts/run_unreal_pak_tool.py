#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_powershell(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def emit_json(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    print(text)


def load_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def resolve_path(raw_path: str | None, *, base_dir: Path) -> Path | None:
    if not raw_path:
        return None

    path = Path(str(raw_path).replace("/", "\\")).expanduser()
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def resolve_packaging_paths(config_path: Path, config: dict) -> tuple[Path, Path, Path, Path]:
    tool_dir = config_path.parent.resolve()

    project_file = resolve_path(config.get("project"), base_dir=tool_dir)
    if project_file is None:
        raise ValueError("Config is missing the 'project' path.")

    project_root = project_file.parent.resolve()
    output_dir = resolve_path(config.get("output"), base_dir=project_root) or (project_root / "Pak")
    tool_exe = tool_dir / "UnrealPakTool.exe"
    return project_root, tool_dir, output_dir.resolve(), tool_exe.resolve()


def find_neighbor_project_file(config_path: Path) -> Path | None:
    candidate_root = config_path.parent.parent.resolve()
    if not candidate_root.exists():
        return None

    project_files = sorted(candidate_root.glob("*.uproject"))
    if len(project_files) == 1:
        return project_files[0].resolve()
    return None


def preflight_package_action(config_path: Path, config: dict, project_root: Path, output_dir: Path) -> dict | None:
    tool_dir = config_path.parent.resolve()
    configured_paths: dict[str, str | None] = {}
    suggested_paths: dict[str, str] = {}
    errors: list[str] = []
    warnings: list[str] = []

    project_file = resolve_path(config.get("project"), base_dir=tool_dir)
    configured_paths["project"] = str(project_file) if project_file else None
    if project_file is None:
        errors.append("Config is missing the 'project' path.")
    elif not project_file.exists():
        errors.append(f"Configured project file not found: {project_file}")
    elif not project_file.is_file():
        errors.append(f"Configured project path is not a file: {project_file}")

    configured_output = resolve_path(config.get("output"), base_dir=project_root) or (project_root / "Pak")
    configured_paths["output"] = str(configured_output.resolve())
    if not configured_output.exists():
        warnings.append(f"Configured output directory does not exist yet: {configured_output}")

    for field_name, label in (
        ("engine", "Configured UnrealEditor-Cmd executable"),
        ("pak_path", "Configured UnrealPak executable"),
    ):
        field_path = resolve_path(config.get(field_name), base_dir=tool_dir)
        configured_paths[field_name] = str(field_path) if field_path else None
        if field_path is None:
            errors.append(f"Config is missing the '{field_name}' path.")
        elif not field_path.exists():
            errors.append(f"{label} not found: {field_path}")
        elif not field_path.is_file():
            errors.append(f"{label} is not a file: {field_path}")

    inferred_project_file = find_neighbor_project_file(config_path)
    if inferred_project_file is not None:
        suggested_paths["project"] = str(inferred_project_file)
        suggested_paths["output"] = str((inferred_project_file.parent / "Pak").resolve())

    if errors:
        return {
            "ok": False,
            "action": "package",
            "error": "Package preflight failed.",
            "config": str(config_path),
            "tool_dir": str(tool_dir),
            "project_root": str(project_root),
            "output_dir": str(output_dir),
            "configured_paths": configured_paths,
            "suggested_paths": suggested_paths,
            "errors": errors,
            "warnings": warnings,
        }

    return None


def normalize_device_target_path(target_path: str) -> str:
    normalized = target_path.replace("\\", "/").strip()
    if normalized.startswith("/"):
        return normalized
    if normalized.startswith("sdcard/"):
        return f"/{normalized}"
    return f"/sdcard/{normalized}"


def read_install_target_path(tool_dir: Path) -> str:
    install_path_file = tool_dir / "pak_install_path.txt"
    if not install_path_file.exists():
        raise ValueError(f"Install path file not found: {install_path_file}")

    raw_text = install_path_file.read_text(encoding="utf-8", errors="replace").strip()
    if not raw_text:
        raise ValueError(f"Install path file is empty: {install_path_file}")

    first_line = raw_text.splitlines()[0].strip()
    if not first_line:
        raise ValueError(f"Install path file is empty: {install_path_file}")

    return normalize_device_target_path(first_line)


def resolve_adb_path(tool_dir: Path) -> Path:
    adb_path = tool_dir / "platform-tools" / "ADB" / "adb.exe"
    if not adb_path.exists():
        raise ValueError(f"adb not found: {adb_path}")
    return adb_path.resolve()


def list_adb_devices(adb_path: Path) -> dict:
    result = subprocess.run(
        [str(adb_path), "devices", "-l"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    devices = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("List of devices attached"):
            continue

        parts = line.split()
        if not parts:
            continue

        serial = parts[0]
        state = parts[1] if len(parts) > 1 else ""
        extra = {}
        for token in parts[2:]:
            if ":" in token:
                key, value = token.split(":", 1)
                extra[key] = value

        devices.append(
            {
                "serial": serial,
                "state": state,
                "model": extra.get("model"),
                "device": extra.get("device"),
                "transport_id": extra.get("transport_id"),
                "raw": line,
            }
        )

    return {
        "ok": result.returncode == 0,
        "return_code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "devices": devices,
    }


def resolve_target_device(device_listing: dict, requested_device_id: str | None) -> tuple[dict | None, str | None]:
    if requested_device_id:
        selected_device = next(
            (device for device in device_listing["devices"] if device["serial"] == requested_device_id),
            None,
        )
        if selected_device is not None:
            return selected_device, requested_device_id
        return None, None

    online_devices = [device for device in device_listing["devices"] if device.get("state") == "device"]
    if len(online_devices) == 1:
        selected_device = online_devices[0]
        return selected_device, selected_device["serial"]

    return None, None


def derive_target_name(config_path: Path, config: dict, override: str | None) -> str:
    if override:
        return override

    selected_items = config.get("selected_items") or []
    if selected_items:
        first_item = str(selected_items[0]).replace("/", "\\")
        if first_item.lower().endswith(".umap"):
            parts = [part for part in first_item.split("\\") if part]
            if len(parts) >= 2:
                return parts[-2]
            return Path(first_item).stem
        return Path(first_item).name

    return config_path.stem


def derive_pak_name_from_selected_item(selected_item: str) -> str:
    normalized = str(selected_item).replace("/", "\\")
    if normalized.lower().endswith(".umap"):
        parts = [part for part in normalized.split("\\") if part]
        if len(parts) >= 2:
            return parts[-2]
        return Path(normalized).stem
    return Path(normalized).name


def expected_pak_names(config_path: Path, config: dict, target_name: str) -> list[str]:
    selected_items = config.get("selected_items") or []
    if not selected_items:
        return [target_name or config_path.stem]

    names = []
    for item in selected_items:
        name = derive_pak_name_from_selected_item(str(item))
        if name and name not in names:
            names.append(name)
    return names or [target_name or config_path.stem]


def verify_output_pak_files(output_dir: Path, pak_names: list[str], package_started_at: float | None = None) -> dict:
    resolved_output_dir = output_dir.resolve()
    files = []
    all_ok = True

    for pak_name in pak_names:
        pak_path = (resolved_output_dir / f"{pak_name}.pak").resolve()
        exists = pak_path.exists()
        under_output_dir = pak_path == resolved_output_dir or resolved_output_dir in pak_path.parents
        stat = pak_path.stat() if exists else None
        fresh_enough = None
        if stat is not None and package_started_at is not None:
            fresh_enough = stat.st_mtime >= package_started_at - 2

        file_ok = exists and under_output_dir and (fresh_enough is not False)
        all_ok = all_ok and file_ok
        files.append(
            {
                "ok": file_ok,
                "pak_name": pak_name,
                "path": str(pak_path),
                "expected_parent": str(resolved_output_dir),
                "exists": exists,
                "under_output_dir": under_output_dir,
                "size": stat.st_size if stat is not None else None,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds") if stat is not None else None,
                "fresh_enough": fresh_enough,
            }
        )

    return {
        "ok": all_ok,
        "output_dir": str(resolved_output_dir),
        "expected_pak_names": pak_names,
        "files": files,
    }


def stop_existing_processes() -> list[dict]:
    command = (
        "Get-Process | Where-Object { "
        "$_.ProcessName -like 'UnrealPakTool*' -or "
        "$_.ProcessName -like 'SimpleUnrealPakTool*' -or "
        "$_.ProcessName -like 'UnrealEditor-Cmd*' -or "
        "$_.ProcessName -like 'UnrealPak*' "
        "} | Select-Object ProcessName,Id"
    )
    result = run_powershell(command)
    stopped = []
    if result.returncode != 0:
        return stopped

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    for line in lines:
        if line.startswith("ProcessName") or line.startswith("---"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[-1].isdigit():
            pid = int(parts[-1])
            name = " ".join(parts[:-1])
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            stopped.append({"name": name, "pid": pid})
    return stopped


def extract_warning_block(log_text: str) -> str:
    patterns = [
        r"检测到以下目录中的资产版本已更新并且在此次打包中未被包含：(.+?)(?:为了确保|(?:\r?\n)\s*=+|$)",
        r"妫€娴嬪埌浠ヤ笅鐩綍涓殑璧勪骇鐗堟湰宸叉洿鏂板苟涓斿湪姝ゆ鎵撳寘涓湭琚寘鍚細(.+?)(?:涓轰簡纭繚|(?:\r?\n)\s*=+|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, log_text, re.S)
        if match:
            return match.group(1)
    return ""


def parse_dependency_dirs(log_text: str) -> list[str]:
    warning_block = extract_warning_block(log_text)
    if not warning_block:
        return []

    matches = re.findall(r"(?:[A-Za-z0-9_\-]+/){1,6}[A-Za-z0-9_\-]+", warning_block)
    seen = []
    for match in matches:
        if match not in seen:
            seen.append(match)
    return seen


def parse_final_status(log_text: str) -> str | None:
    patterns = [
        r"\[任务结束\]\s*最终状态[:：]?\s*(.+?)\s*\(退出码[:：]?\s*\d+\)",
        r"\[浠诲姟缁撴潫\]\s*鏈€缁堢姸鎬?[::：]?\s*(.+?)\s*\(閫€鍑虹爜[::：]?\s*\d+\)",
    ]
    for pattern in patterns:
        match = re.search(pattern, log_text, re.S)
        if match:
            return " ".join(match.group(1).split())
    return None


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_device_storage_summary(target_path: str, pak_paths: list[Path], verification: dict | None = None) -> dict:
    remote_paths = []
    if verification:
        remote_paths = [
            str(file_info.get("remote_path"))
            for file_info in verification.get("files", [])
            if file_info.get("remote_path")
        ]

    if not remote_paths:
        remote_paths = [target_path.rstrip("/") + "/" + pak_path.name for pak_path in pak_paths]

    return {
        "directory": target_path,
        "pak_paths": remote_paths,
    }


def verify_remote_pak_files(adb_path: Path, pak_paths: list[Path], target_path: str, device_id: str) -> dict:
    verified_files = []
    all_ok = True
    warnings = []

    for pak_path in pak_paths:
        local_stat = pak_path.stat()
        local_size = local_stat.st_size
        local_sha1 = sha1_file(pak_path)
        remote_path = target_path.rstrip("/") + "/" + pak_path.name
        quoted_remote_path = shell_quote(remote_path)

        stat_command = f"stat -c '%s|%Y' {quoted_remote_path}"
        stat_result = subprocess.run(
            [str(adb_path), "-s", device_id, "shell", stat_command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        remote_size = None
        remote_modified = None
        stat_stdout = stat_result.stdout.strip()
        if stat_result.returncode == 0 and stat_stdout:
            stat_parts = stat_stdout.splitlines()[0].split("|", 1)
            try:
                remote_size = int(stat_parts[0])
            except (IndexError, ValueError):
                remote_size = None
            if len(stat_parts) > 1:
                try:
                    remote_modified = int(stat_parts[1])
                except ValueError:
                    remote_modified = None

        sha1_command = f"sha1sum {quoted_remote_path}"
        sha1_result = subprocess.run(
            [str(adb_path), "-s", device_id, "shell", sha1_command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        remote_sha1 = None
        sha1_stdout = sha1_result.stdout.strip()
        if sha1_result.returncode == 0 and sha1_stdout:
            remote_sha1 = sha1_stdout.split()[0].lower()

        size_match = remote_size == local_size
        sha1_match = remote_sha1 == local_sha1
        file_ok = stat_result.returncode == 0 and size_match and sha1_result.returncode == 0 and sha1_match
        all_ok = all_ok and file_ok

        if sha1_result.returncode != 0:
            warnings.append(f"Remote sha1sum failed for {remote_path}: {sha1_result.stderr.strip()}")

        verified_files.append(
            {
                "ok": file_ok,
                "local_path": str(pak_path),
                "remote_path": remote_path,
                "local_size": local_size,
                "remote_size": remote_size,
                "size_match": size_match,
                "local_sha1": local_sha1,
                "remote_sha1": remote_sha1,
                "sha1_match": sha1_match,
                "local_modified": int(local_stat.st_mtime),
                "remote_modified": remote_modified,
                "stat_command": stat_command,
                "stat_return_code": stat_result.returncode,
                "stat_stdout": stat_result.stdout.strip(),
                "stat_stderr": stat_result.stderr.strip(),
                "sha1_command": sha1_command,
                "sha1_return_code": sha1_result.returncode,
                "sha1_stdout": sha1_result.stdout.strip(),
                "sha1_stderr": sha1_result.stderr.strip(),
            }
        )

    return {
        "ok": all_ok,
        "method": "size_and_sha1",
        "files": verified_files,
        "warnings": warnings,
    }


def install_pak_files(adb_path: Path, pak_paths: list[Path], target_path: str, device_id: str) -> dict:
    quoted_target_path = shell_quote(target_path)
    prepare_command = f"if [ -f {quoted_target_path} ]; then rm -f {quoted_target_path}; fi; mkdir -p {quoted_target_path}"
    prepare_result = subprocess.run(
        [str(adb_path), "-s", device_id, "shell", prepare_command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if prepare_result.returncode != 0:
        return {
            "ok": False,
            "action": "install",
            "device_id": device_id,
            "target_path": target_path,
            "device_storage": build_device_storage_summary(target_path, pak_paths),
            "pak_paths": [str(path) for path in pak_paths],
            "prepare_command": prepare_command,
            "prepare_return_code": prepare_result.returncode,
            "prepare_stdout": prepare_result.stdout.strip(),
            "prepare_stderr": prepare_result.stderr.strip(),
            "return_code": prepare_result.returncode,
            "stdout": "",
            "stderr": prepare_result.stderr.strip(),
        }

    push_target_path = target_path.rstrip("/") + "/"
    result = subprocess.run(
        [str(adb_path), "-s", device_id, "push", *[str(path) for path in pak_paths], push_target_path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    verification = verify_remote_pak_files(adb_path, pak_paths, target_path, device_id)
    install_ok = result.returncode == 0 and verification["ok"]
    return {
        "ok": install_ok,
        "action": "install",
        "device_id": device_id,
        "target_path": target_path,
        "push_target_path": push_target_path,
        "device_storage": build_device_storage_summary(target_path, pak_paths, verification),
        "pak_paths": [str(path) for path in pak_paths],
        "prepare_command": prepare_command,
        "prepare_return_code": prepare_result.returncode,
        "prepare_stdout": prepare_result.stdout.strip(),
        "prepare_stderr": prepare_result.stderr.strip(),
        "return_code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "verification": verification,
    }


def delete_pak_files(adb_path: Path, target_path: str, device_id: str) -> dict:
    commands = [
        f"find {target_path} -mindepth 1 -delete",
        f"rm -rf {target_path}/*",
    ]
    result = None
    attempted_commands = []
    for shell_command in commands:
        attempted_commands.append(shell_command)
        current_result = subprocess.run(
            [str(adb_path), "-s", device_id, "shell", shell_command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        result = current_result
        stderr = current_result.stderr.strip()
        if current_result.returncode == 0 or not stderr or "No such file" in stderr:
            break

    assert result is not None
    stderr = result.stderr.strip()
    stdout = result.stdout.strip()
    success = result.returncode == 0 or not stderr or "No such file" in stderr
    return {
        "ok": success,
        "action": "clean",
        "device_id": device_id,
        "target_path": target_path,
        "device_storage": {
            "directory": target_path,
        },
        "delete_scope": "all files and subdirectories under target_path",
        "adb_shell_commands": attempted_commands,
        "return_code": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


def maybe_auto_install_after_package(
    tool_dir: Path,
    output_dir: Path,
    config_path: Path,
    target_name: str,
    requested_device_id: str | None,
    install_path_override: str | None,
) -> tuple[dict, int]:
    pak_path = (output_dir / f"{target_name}.pak").resolve()
    base_payload = {
        "enabled": True,
        "mode": "auto_after_package",
        "config": str(config_path),
        "target_name": target_name,
        "pak_paths": [str(pak_path)],
        "requested_device_id": requested_device_id,
    }

    try:
        adb_path = resolve_adb_path(tool_dir)
        install_target_path = (
            normalize_device_target_path(install_path_override)
            if install_path_override
            else read_install_target_path(tool_dir)
        )
    except ValueError as exc:
        return (
            {
                **base_payload,
                "attempted": False,
                "skipped": True,
                "ok": None,
                "reason": str(exc),
            },
            0,
        )

    device_listing = list_adb_devices(adb_path)
    context_payload = {
        **base_payload,
        "adb_path": str(adb_path),
        "target_path": install_target_path,
        "device_storage": build_device_storage_summary(install_target_path, [pak_path]),
        "connected_devices": device_listing["devices"],
        "adb_devices_stdout": device_listing["stdout"],
    }

    if not device_listing["ok"]:
        return (
            {
                **context_payload,
                "attempted": False,
                "skipped": True,
                "ok": None,
                "reason": "Failed to query adb devices. Skipping auto-install.",
                "adb_devices_stderr": device_listing["stderr"],
                "adb_devices_return_code": device_listing["return_code"],
            },
            0,
        )

    online_devices = [device for device in device_listing["devices"] if device.get("state") == "device"]
    selected_device, resolved_device_id = resolve_target_device(device_listing, requested_device_id)

    if requested_device_id and resolved_device_id is None:
        return (
            {
                **context_payload,
                "attempted": False,
                "skipped": False,
                "ok": False,
                "error": f"Requested device id was not found or not online: {requested_device_id}",
            },
            2,
        )

    if not online_devices:
        return (
            {
                **context_payload,
                "attempted": False,
                "skipped": True,
                "ok": None,
                "reason": "No online device detected. Skipping auto-install.",
            },
            0,
        )

    if requested_device_id is None and len(online_devices) > 1:
        return (
            {
                **context_payload,
                "attempted": False,
                "skipped": True,
                "ok": None,
                "reason": "Multiple online devices detected. Skipping auto-install. Pass --device-id to target one device.",
            },
            0,
        )

    assert resolved_device_id is not None
    install_payload = install_pak_files(adb_path, [pak_path], install_target_path, resolved_device_id)
    install_payload.update(
        {
            **context_payload,
            "attempted": True,
            "skipped": False,
            "selected_device": selected_device,
        }
    )
    return install_payload, (0 if install_payload["ok"] else 2)


def run_package_action(
    config_path: Path,
    config: dict,
    project_root: Path,
    tool_dir: Path,
    output_dir: Path,
    tool_exe: Path,
    target_name: str,
    stop_existing: bool,
) -> tuple[dict, int]:
    expected_pak = output_dir / f"{target_name}.pak"
    pak_names = expected_pak_names(config_path, config, target_name)

    stopped = []
    if stop_existing:
        stopped = stop_existing_processes()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = tool_dir / f"pak_{target_name.lower()}_{timestamp}.log"
    package_started_at = datetime.now().timestamp()

    try:
        result = subprocess.run(
            [
                str(tool_exe),
                "--cli",
                "--start",
                "--config",
                str(config_path),
                "--log",
                str(log_path),
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        payload = {
            "ok": False,
            "action": "package",
            "project_root": str(project_root),
            "tool_dir": str(tool_dir),
            "output_dir": str(output_dir),
            "resolved_output_dir": str(output_dir.resolve()),
            "config": str(config_path),
            "target_name": target_name,
            "log_path": str(log_path),
            "processes_stopped": stopped,
            "error": f"Failed to launch UnrealPakTool: {exc}",
            "pak": None,
            "missing_updated_dependency_dirs": [],
            "stdout": "",
            "stderr": "",
        }
        return payload, 1

    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    dependencies = parse_dependency_dirs(log_text)
    final_status = parse_final_status(log_text)
    output_verification = verify_output_pak_files(output_dir, pak_names, package_started_at)

    pak_exists = expected_pak.exists()
    pak_info = None
    if pak_exists:
        stat = expected_pak.stat()
        pak_info = {
            "path": str(expected_pak),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        }

    payload = {
        "ok": pak_exists,
        "action": "package",
        "project_root": str(project_root),
        "tool_dir": str(tool_dir),
        "output_dir": str(output_dir),
        "resolved_output_dir": str(output_dir.resolve()),
        "config": str(config_path),
        "target_name": target_name,
        "log_path": str(log_path),
        "processes_stopped": stopped,
        "return_code": result.returncode,
        "final_status": final_status,
        "pak": pak_info,
        "output_verification": output_verification,
        "missing_updated_dependency_dirs": dependencies,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    payload["ok"] = pak_exists and output_verification["ok"]
    return payload, (0 if payload["ok"] else 2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run UnrealPakTool packaging helper.")
    parser.add_argument("--config", required=True, help="Path to UnrealPakTool config json.")
    parser.add_argument("--target-name", help="Expected pak base name, for example S01.")
    parser.add_argument(
        "--action",
        choices=["package", "install", "clean"],
        default="package",
        help="Action to run: package, install built pak(s), or clean installed pak(s). Package auto-installs after success when exactly one online device is available.",
    )
    parser.add_argument(
        "--stop-existing",
        action="store_true",
        help="Stop existing UnrealPakTool/UnrealEditor/UnrealPak processes before running.",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate package prerequisites and exit without launching UnrealPakTool.",
    )
    parser.add_argument(
        "--device-id",
        help="ADB device id. Optional when exactly one online device is connected. Also used by package auto-install when provided.",
    )
    parser.add_argument(
        "--pak",
        dest="pak_paths",
        action="append",
        help="Explicit pak path to install. Can be passed multiple times. Defaults to the pak derived from config.",
    )
    parser.add_argument(
        "--install-path",
        help="Override target install path on device. Defaults to UnrealPakTool/pak_install_path.txt. Also used by package auto-install.",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    if not config_path.exists():
        emit_json({"ok": False, "error": f"Config not found: {config_path}"})
        return 1

    config = load_config(config_path)
    try:
        project_root, tool_dir, output_dir, tool_exe = resolve_packaging_paths(config_path, config)
    except ValueError as exc:
        emit_json({"ok": False, "error": str(exc), "config": str(config_path)})
        return 1

    if not tool_exe.exists():
        emit_json({"ok": False, "error": f"Tool not found: {tool_exe}", "config": str(config_path)})
        return 1

    target_name = derive_target_name(config_path, config, args.target_name)

    if args.action == "package":
        preflight_failure = preflight_package_action(config_path, config, project_root, output_dir)
        if preflight_failure is not None:
            emit_json(preflight_failure)
            return 1
        if args.preflight_only:
            preflight_pak_names = expected_pak_names(config_path, config, target_name)
            resolved_output_dir = output_dir.resolve()
            emit_json(
                {
                    "ok": True,
                    "action": "package",
                    "preflight_only": True,
                    "config": str(config_path),
                    "tool_dir": str(tool_dir),
                    "project_root": str(project_root),
                    "output_dir": str(output_dir),
                    "resolved_output_dir": str(resolved_output_dir),
                    "expected_output_paths": [str((resolved_output_dir / f"{name}.pak").resolve()) for name in preflight_pak_names],
                    "target_name": target_name,
                }
            )
            return 0
        payload, exit_code = run_package_action(
            config_path,
            config,
            project_root,
            tool_dir,
            output_dir,
            tool_exe,
            target_name,
            args.stop_existing,
        )
        payload["package_ok"] = payload["ok"]
        if payload["ok"]:
            auto_install_payload, auto_install_exit_code = maybe_auto_install_after_package(
                tool_dir,
                output_dir,
                config_path,
                target_name,
                args.device_id,
                args.install_path,
            )
            payload["auto_install"] = auto_install_payload
            if auto_install_exit_code != 0:
                payload["ok"] = False
                exit_code = auto_install_exit_code
        emit_json(payload)
        return exit_code

    try:
        adb_path = resolve_adb_path(tool_dir)
        install_target_path = normalize_device_target_path(args.install_path) if args.install_path else read_install_target_path(tool_dir)
    except ValueError as exc:
        emit_json(
            {
                "ok": False,
                "action": args.action,
                "error": str(exc),
                "config": str(config_path),
            }
        )
        return 1

    device_listing = list_adb_devices(adb_path)
    selected_device, resolved_device_id = resolve_target_device(device_listing, args.device_id)

    if resolved_device_id is None:
        emit_json(
            {
                "ok": False,
                "action": args.action,
                "error": "No target device could be resolved. Connect exactly one online device or pass --device-id.",
                "config": str(config_path),
                "connected_devices": device_listing["devices"],
                "adb_devices_stdout": device_listing["stdout"],
            }
        )
        return 1

    if args.action == "clean":
        payload = delete_pak_files(adb_path, install_target_path, resolved_device_id)
        payload.update(
            {
                "project_root": str(project_root),
                "tool_dir": str(tool_dir),
                "output_dir": str(output_dir),
                "config": str(config_path),
                "target_name": target_name,
                "adb_path": str(adb_path),
                "connected_devices": device_listing["devices"],
                "adb_devices_stdout": device_listing["stdout"],
                "selected_device": selected_device,
            }
        )
        emit_json(payload)
        return 0 if payload["ok"] else 2

    pak_candidates = [Path(path).resolve() for path in (args.pak_paths or [])]
    if not pak_candidates:
        pak_candidates = [output_dir / f"{target_name}.pak"]

    missing_paks = [str(path) for path in pak_candidates if not path.exists()]
    if missing_paks:
        emit_json(
            {
                "ok": False,
                "action": "install",
                "error": "Pak file not found.",
                "missing_paks": missing_paks,
                "config": str(config_path),
                "target_name": target_name,
                "connected_devices": device_listing["devices"],
                "adb_devices_stdout": device_listing["stdout"],
                "selected_device": selected_device,
            }
        )
        return 1

    payload = install_pak_files(adb_path, pak_candidates, install_target_path, resolved_device_id)
    payload.update(
        {
            "project_root": str(project_root),
            "tool_dir": str(tool_dir),
            "output_dir": str(output_dir),
            "config": str(config_path),
            "target_name": target_name,
            "adb_path": str(adb_path),
            "connected_devices": device_listing["devices"],
            "adb_devices_stdout": device_listing["stdout"],
            "selected_device": selected_device,
        }
    )
    emit_json(payload)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
