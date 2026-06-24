from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def home_dir() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or home_dir() / ".codex")


def cm_image_gen_script_path() -> Path:
    return codex_home() / "skills" / "cm-imagegen" / "scripts" / "cm_image_gen.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute or coordinate a flipbook frame plan one phase at a time with anchor approval checkpoints.")
    sub = parser.add_subparsers(dest="command", required=True)

    status_parser = sub.add_parser("status")
    status_parser.add_argument("plan_path")
    status_parser.add_argument("--state-path", default="")
    status_parser.add_argument("--json", action="store_true")

    run_parser = sub.add_parser("run")
    run_parser.add_argument("plan_path")
    run_parser.add_argument("--state-path", default="")
    run_parser.add_argument("--provider", default=None, choices=("system-imagegen", "cm-imagegen"))
    run_parser.add_argument("--phase", type=int, help="Optional 1-based phase number to target.")
    run_parser.add_argument("--through-all-phases", action="store_true")
    run_parser.add_argument("--auto-approve-anchors", action="store_true")
    run_parser.add_argument("--reference-mode", choices=("anchor", "chain"), default="chain")
    run_parser.add_argument("--fill-mode", choices=("prefer-edit", "generate-only", "edit-only"), default="prefer-edit")
    run_parser.add_argument("--allow-generate-fallback", dest="allow_generate_fallback", action="store_true")
    run_parser.add_argument("--no-generate-fallback", dest="allow_generate_fallback", action="store_false")
    run_parser.set_defaults(allow_generate_fallback=True)
    run_parser.add_argument("--timeout", type=int, default=600)
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--json", action="store_true")

    import_parser = sub.add_parser("import-frame")
    import_parser.add_argument("plan_path")
    import_parser.add_argument("--state-path", default="")
    import_parser.add_argument("--frame", required=True, type=int)
    import_parser.add_argument("--path", required=True)
    import_parser.add_argument("--approve-anchor", action="store_true")
    import_parser.add_argument("--json", action="store_true")

    approve_parser = sub.add_parser("approve-anchor")
    approve_parser.add_argument("plan_path")
    approve_parser.add_argument("--state-path", default="")
    approve_parser.add_argument("--phase", required=True, type=int, help="1-based phase number.")
    approve_parser.add_argument("--path", default="", help="Optional approved anchor image path override.")
    approve_parser.add_argument("--json", action="store_true")

    reject_parser = sub.add_parser("reject-anchor")
    reject_parser.add_argument("plan_path")
    reject_parser.add_argument("--state-path", default="")
    reject_parser.add_argument("--phase", required=True, type=int, help="1-based phase number.")
    reject_parser.add_argument("--reason", default="", help="Optional rejection reason.")
    reject_parser.add_argument("--json", action="store_true")

    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_state_path(plan_path: Path, state_path: str) -> Path:
    if state_path:
        return Path(state_path).expanduser().resolve()
    return plan_path.parent / "batch-run-state.json"


def frame_key(frame_index: int) -> str:
    return str(frame_index)


def default_provider_mode(plan: dict, requested_provider: str | None) -> str:
    if requested_provider:
        return requested_provider
    return str(plan.get("default_provider_mode") or "system-imagegen")


def build_initial_state(plan_path: Path, plan: dict) -> dict:
    return {
        "tool": "flipbook_batch_runner",
        "frame_plan_path": str(plan_path),
        "spec_path": plan.get("spec_path"),
        "default_provider_mode": str(plan.get("default_provider_mode") or "system-imagegen"),
        "created_utc": utc_now(),
        "updated_utc": utc_now(),
        "phases": [
            {
                "phase_index": phase["phase_index"],
                "phase_number": phase["phase_number"],
                "phase_name": phase["phase_name"],
                "start_frame_index": phase["start_frame_index"],
                "end_frame_index": phase["end_frame_index"],
                "frame_count": phase["frame_count"],
                "anchor_frame_index": phase["anchor_frame_index"],
                "anchor_filename": phase["anchor_filename"],
                "anchor_status": "pending",
                "anchor_output_path": None,
                "anchor_approved_path": None,
                "fill_status": "pending",
                "completed": False,
                "completed_frame_count": 0,
                "last_reference_path": None,
                "history": [],
            }
            for phase in plan.get("phases", [])
        ],
        "frames": {
            frame_key(frame["frame_index"]): {
                "frame_index": frame["frame_index"],
                "phase_index": frame["phase_index"],
                "phase_name": frame["phase_name"],
                "filename": frame["filename"],
                "status": "pending",
                "operation": None,
                "output_path": None,
                "reference_image": None,
                "attempts": 0,
                "last_error": None,
                "history": [],
                "updated_utc": utc_now(),
            }
            for frame in plan.get("frames", [])
        },
    }


def load_or_initialize_state(plan_path: Path, plan: dict, state_path: Path, persist: bool) -> dict:
    if state_path.exists():
        return load_json(state_path)
    state = build_initial_state(plan_path, plan)
    if persist:
        save_json(state_path, state)
    return state


def find_phase(plan: dict, phase_number: int) -> dict:
    for phase in plan.get("phases", []):
        if int(phase["phase_number"]) == phase_number:
            return phase
    raise SystemExit(f"Phase {phase_number} was not found in the frame plan.")


def find_phase_state(state: dict, phase_number: int) -> dict:
    for phase in state.get("phases", []):
        if int(phase["phase_number"]) == phase_number:
            return phase
    raise SystemExit(f"Phase {phase_number} was not found in the runner state.")


def find_frame(plan: dict, frame_index: int) -> dict:
    for frame in plan.get("frames", []):
        if int(frame["frame_index"]) == frame_index:
            return frame
    raise SystemExit(f"Frame {frame_index} was not found in the frame plan.")


def frames_for_phase(plan: dict, phase_number: int) -> list[dict]:
    phase = find_phase(plan, phase_number)
    start = int(phase["start_frame_index"])
    end = int(phase["end_frame_index"])
    return [frame for frame in plan.get("frames", []) if start <= int(frame["frame_index"]) <= end]


def frame_state(state: dict, frame_index: int) -> dict:
    key = frame_key(frame_index)
    if key not in state["frames"]:
        raise SystemExit(f"Frame {frame_index} was not found in the runner state.")
    return state["frames"][key]


def expected_output_path(plan: dict, frame: dict) -> Path:
    return Path(plan["generated_frames_dir"]) / frame["filename"]


def parse_json_from_output(text: str) -> dict:
    stripped = text.strip()
    if not stripped:
        raise ValueError("No JSON output was produced.")
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object was found in the output.")
    return json.loads(stripped[start : end + 1])


def cm_command_common() -> list[str]:
    return [sys.executable, str(cm_image_gen_script_path())]


def build_generate_command(plan: dict, frame: dict, timeout: int) -> list[str]:
    command = cm_command_common()
    command.extend(
        [
            "generate",
            "--prompt",
            frame["prompt"],
            "--size",
            plan["size"],
            "--out-dir",
            plan["generated_frames_dir"],
            "--filename",
            frame["filename"],
            "--timeout",
            str(timeout),
        ]
    )
    if plan.get("quality"):
        command.extend(["--quality", plan["quality"]])
    if plan.get("background"):
        command.extend(["--background", plan["background"]])
    if plan.get("output_format"):
        command.extend(["--output-format", plan["output_format"]])
    return command


def build_edit_command(plan: dict, frame: dict, reference_path: Path, timeout: int) -> list[str]:
    command = cm_command_common()
    command.extend(
        [
            "edit",
            "--prompt",
            frame.get("edit_prompt") or frame["prompt"],
            "--image",
            str(reference_path),
            "--size",
            plan["size"],
            "--out-dir",
            plan["generated_frames_dir"],
            "--filename",
            frame["filename"],
            "--timeout",
            str(timeout),
        ]
    )
    if plan.get("quality"):
        command.extend(["--quality", plan["quality"]])
    if plan.get("background"):
        command.extend(["--background", plan["background"]])
    if plan.get("output_format"):
        command.extend(["--output-format", plan["output_format"]])
    return command


def append_history(record: dict, entry: dict) -> None:
    record.setdefault("history", []).append(entry)
    record["updated_utc"] = utc_now()


def sync_phase_state(plan: dict, state: dict, phase_number: int) -> None:
    phase = find_phase_state(state, phase_number)
    phase_frames = frames_for_phase(plan, phase_number)
    generated_count = 0
    for planned_frame in phase_frames:
        current = frame_state(state, int(planned_frame["frame_index"]))
        if current["status"] in {"generated", "approved"}:
            generated_count += 1

    phase["completed_frame_count"] = generated_count
    if phase["anchor_status"] == "approved":
        if generated_count >= int(phase["frame_count"]):
            phase["fill_status"] = "completed"
            phase["completed"] = True
        elif generated_count > 1:
            phase["fill_status"] = "in_progress"
            phase["completed"] = False
        else:
            phase["fill_status"] = "pending_fill"
            phase["completed"] = False
    elif phase["anchor_status"] == "generated":
        phase["fill_status"] = "waiting_for_anchor_approval"
        phase["completed"] = False
    else:
        phase["fill_status"] = "pending"
        phase["completed"] = False


def phase_reference_path(plan: dict, state: dict, phase_number: int, reference_mode: str) -> Path | None:
    phase = find_phase_state(state, phase_number)
    anchor_path = phase.get("anchor_approved_path")
    if not anchor_path:
        return None
    if reference_mode == "anchor":
        return Path(anchor_path)

    latest_path = Path(anchor_path)
    for planned_frame in frames_for_phase(plan, phase_number):
        current = frame_state(state, int(planned_frame["frame_index"]))
        if current["status"] in {"generated", "approved"} and current.get("output_path"):
            latest_path = Path(current["output_path"])
    return latest_path


def phase_summary(plan: dict, state: dict, phase_number: int) -> dict:
    phase = find_phase_state(state, phase_number)
    sync_phase_state(plan, state, phase_number)
    phase_frames = frames_for_phase(plan, phase_number)
    pending_frames = [frame for frame in phase_frames if frame_state(state, int(frame["frame_index"]))["status"] == "pending"]
    next_pending_frame = pending_frames[0] if pending_frames else None

    if phase["completed"]:
        next_action = "complete"
    elif phase["anchor_status"] == "generated":
        next_action = f"approve anchor for phase {phase_number}"
    elif phase["anchor_status"] != "approved":
        next_action = f"run anchor for phase {phase_number}"
    elif next_pending_frame is not None:
        next_action = f"fill phase {phase_number}"
    else:
        next_action = "complete"

    return {
        "phase_number": phase_number,
        "phase_name": phase["phase_name"],
        "anchor_status": phase["anchor_status"],
        "fill_status": phase["fill_status"],
        "completed": phase["completed"],
        "completed_frame_count": phase["completed_frame_count"],
        "frame_count": phase["frame_count"],
        "next_action": next_action,
    }


def next_phase_number(plan: dict, state: dict, requested_phase: int | None) -> int | None:
    phase_numbers = [int(phase["phase_number"]) for phase in plan.get("phases", [])]
    if requested_phase is not None:
        return requested_phase if requested_phase in phase_numbers else None
    for phase_number in phase_numbers:
        summary = phase_summary(plan, state, phase_number)
        if not summary["completed"]:
            return phase_number
    return None


def preview_or_run_command(command: list[str], expected_path: Path, dry_run: bool) -> dict:
    command_text = subprocess.list2cmdline([str(value) for value in command])
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "command": command_text,
            "output_path": str(expected_path.resolve()),
            "raw_stdout": "",
        }

    completed = subprocess.run(command, capture_output=True, text=True)
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if completed.returncode != 0:
        return {
            "ok": False,
            "dry_run": False,
            "command": command_text,
            "output_path": str(expected_path.resolve()),
            "error": (stderr.strip() or stdout.strip() or f"Command failed with exit code {completed.returncode}"),
            "raw_stdout": stdout,
            "raw_stderr": stderr,
        }

    try:
        payload = parse_json_from_output(stdout)
    except Exception as exc:
        return {
            "ok": False,
            "dry_run": False,
            "command": command_text,
            "output_path": str(expected_path.resolve()),
            "error": f"Failed to parse cm-imagegen JSON output: {exc}",
            "raw_stdout": stdout,
            "raw_stderr": stderr,
        }

    paths = payload.get("paths") or []
    resolved_output = str(expected_path.resolve())
    if paths:
        resolved_output = str(Path(paths[0]).expanduser().resolve())
    return {
        "ok": True,
        "dry_run": False,
        "command": command_text,
        "output_path": resolved_output,
        "payload": payload,
        "raw_stdout": stdout,
    }


def approve_phase_anchor(plan: dict, state: dict, phase_number: int, approved_path: Path, reason: str, require_existing_path: bool = True) -> dict:
    approved_path = approved_path.expanduser().resolve()
    if require_existing_path and not approved_path.exists():
        raise SystemExit(f"Approved anchor image does not exist: {approved_path}")

    phase = find_phase_state(state, phase_number)
    anchor_frame = frame_state(state, int(phase["anchor_frame_index"]))
    phase["anchor_status"] = "approved"
    phase["anchor_output_path"] = str(approved_path)
    phase["anchor_approved_path"] = str(approved_path)
    phase["last_reference_path"] = str(approved_path)
    append_history(
        phase,
        {
            "event": "anchor-approved",
            "reason": reason,
            "path": str(approved_path),
            "updated_utc": utc_now(),
        },
    )

    anchor_frame["status"] = "approved"
    anchor_frame["output_path"] = str(approved_path)
    anchor_frame["reference_image"] = None
    anchor_frame["last_error"] = None
    append_history(
        anchor_frame,
        {
            "event": "approved",
            "path": str(approved_path),
            "updated_utc": utc_now(),
        },
    )
    sync_phase_state(plan, state, phase_number)
    state["updated_utc"] = utc_now()
    return {
        "ok": True,
        "phase_number": phase_number,
        "phase_name": phase["phase_name"],
        "approved_path": str(approved_path),
        "next_action": phase_summary(plan, state, phase_number)["next_action"],
    }


def reject_phase_anchor(plan: dict, state: dict, phase_number: int, reason: str) -> dict:
    phase = find_phase_state(state, phase_number)
    phase_frames = frames_for_phase(plan, phase_number)

    append_history(
        phase,
        {
            "event": "anchor-rejected",
            "reason": reason,
            "path": phase.get("anchor_output_path"),
            "updated_utc": utc_now(),
        },
    )
    phase["anchor_status"] = "pending"
    phase["anchor_output_path"] = None
    phase["anchor_approved_path"] = None
    phase["last_reference_path"] = None
    phase["completed"] = False
    phase["fill_status"] = "pending"
    phase["completed_frame_count"] = 0

    for planned_frame in phase_frames:
        current = frame_state(state, int(planned_frame["frame_index"]))
        append_history(
            current,
            {
                "event": "phase-reset-after-anchor-rejection",
                "reason": reason,
                "updated_utc": utc_now(),
            },
        )
        current["status"] = "pending"
        current["operation"] = None
        current["output_path"] = None
        current["reference_image"] = None
        current["last_error"] = reason or "Anchor rejected."

    sync_phase_state(plan, state, phase_number)
    state["updated_utc"] = utc_now()
    return {
        "ok": True,
        "phase_number": phase_number,
        "phase_name": phase["phase_name"],
        "reason": reason,
        "next_action": phase_summary(plan, state, phase_number)["next_action"],
    }


def import_frame_output(plan: dict, state: dict, frame_index: int, imported_path: Path, approve_anchor: bool) -> dict:
    imported_path = imported_path.expanduser().resolve()
    if not imported_path.exists():
        raise SystemExit(f"Imported frame file does not exist: {imported_path}")

    planned_frame = find_frame(plan, frame_index)
    current = frame_state(state, frame_index)
    phase_number = int(planned_frame["phase_index"]) + 1
    phase = find_phase_state(state, phase_number)

    current["status"] = "generated"
    current["operation"] = "manual-import"
    current["output_path"] = str(imported_path)
    current["last_error"] = None
    append_history(
        current,
        {
            "event": "manual-import",
            "path": str(imported_path),
            "updated_utc": utc_now(),
        },
    )

    if planned_frame.get("is_anchor"):
        phase["anchor_status"] = "generated"
        phase["anchor_output_path"] = str(imported_path)
        append_history(
            phase,
            {
                "event": "anchor-imported",
                "path": str(imported_path),
                "updated_utc": utc_now(),
            },
        )
        if approve_anchor:
            payload = approve_phase_anchor(plan, state, phase_number, imported_path, "manual import with approval")
            payload["frame_index"] = frame_index
            payload["imported_path"] = str(imported_path)
        else:
            sync_phase_state(plan, state, phase_number)
            state["updated_utc"] = utc_now()
            payload = {
                "ok": True,
                "frame_index": frame_index,
                "phase_number": phase_number,
                "phase_name": phase["phase_name"],
                "imported_path": str(imported_path),
                "anchor_status": phase["anchor_status"],
                "next_action": phase_summary(plan, state, phase_number)["next_action"],
            }
    else:
        if phase["anchor_status"] == "approved":
            phase["last_reference_path"] = str(imported_path)
        sync_phase_state(plan, state, phase_number)
        state["updated_utc"] = utc_now()
        payload = {
            "ok": True,
            "frame_index": frame_index,
            "phase_number": phase_number,
            "phase_name": phase["phase_name"],
            "imported_path": str(imported_path),
            "next_action": phase_summary(plan, state, phase_number)["next_action"],
        }
    return payload


def run_anchor_with_cm(plan: dict, state: dict, phase_number: int, timeout: int, dry_run: bool) -> dict:
    planned_phase = find_phase(plan, phase_number)
    planned_frame = next(frame for frame in plan["frames"] if int(frame["frame_index"]) == int(planned_phase["anchor_frame_index"]))
    current = frame_state(state, int(planned_frame["frame_index"]))
    expected_path = expected_output_path(plan, planned_frame)
    command = build_generate_command(plan, planned_frame, timeout)
    result = preview_or_run_command(command, expected_path, dry_run)

    if result["ok"]:
        current["attempts"] += 1
        current["status"] = "generated"
        current["operation"] = "generate"
        current["output_path"] = result["output_path"]
        current["reference_image"] = None
        current["last_error"] = None
        append_history(
            current,
            {
                "event": "generated-anchor" if not dry_run else "dry-run-anchor",
                "command": result["command"],
                "path": result["output_path"],
                "updated_utc": utc_now(),
            },
        )
        phase = find_phase_state(state, phase_number)
        phase["anchor_status"] = "generated"
        phase["anchor_output_path"] = result["output_path"]
        phase["completed"] = False
        phase["last_reference_path"] = None
        append_history(
            phase,
            {
                "event": "anchor-generated" if not dry_run else "dry-run-anchor",
                "command": result["command"],
                "path": result["output_path"],
                "updated_utc": utc_now(),
            },
        )
    else:
        current["attempts"] += 1
        current["status"] = "failed"
        current["last_error"] = result["error"]
        append_history(
            current,
            {
                "event": "anchor-failed",
                "command": result["command"],
                "error": result["error"],
                "updated_utc": utc_now(),
            },
        )

    sync_phase_state(plan, state, phase_number)
    state["updated_utc"] = utc_now()
    return result


def run_fill_frame_with_cm(
    plan: dict,
    state: dict,
    phase_number: int,
    planned_frame: dict,
    timeout: int,
    dry_run: bool,
    reference_mode: str,
    fill_mode: str,
    allow_generate_fallback: bool,
) -> dict:
    current = frame_state(state, int(planned_frame["frame_index"]))
    reference_path = phase_reference_path(plan, state, phase_number, reference_mode)
    expected_path = expected_output_path(plan, planned_frame)

    attempted_edit = False
    if fill_mode == "generate-only":
        command = build_generate_command(plan, planned_frame, timeout)
        result = preview_or_run_command(command, expected_path, dry_run)
        operation = "generate"
    else:
        if reference_path is None and fill_mode == "edit-only":
            return {
                "ok": False,
                "error": f"Phase {phase_number} has no approved reference image for edit-only fill.",
                "command": "",
                "output_path": str(expected_path.resolve()),
            }

        if reference_path is None:
            command = build_generate_command(plan, planned_frame, timeout)
            result = preview_or_run_command(command, expected_path, dry_run)
            operation = "generate"
        else:
            attempted_edit = True
            command = build_edit_command(plan, planned_frame, reference_path, timeout)
            result = preview_or_run_command(command, expected_path, dry_run)
            operation = "edit"
            if not result["ok"] and fill_mode == "prefer-edit" and allow_generate_fallback:
                command = build_generate_command(plan, planned_frame, timeout)
                result = preview_or_run_command(command, expected_path, dry_run)
                operation = "generate"

    current["attempts"] += 1
    current["operation"] = operation
    current["reference_image"] = None if operation == "generate" else (str(reference_path) if reference_path is not None else None)

    if result["ok"]:
        current["status"] = "generated"
        current["output_path"] = result["output_path"]
        current["last_error"] = None
        append_history(
            current,
            {
                "event": "frame-generated" if operation == "generate" else "frame-edited",
                "command": result["command"],
                "path": result["output_path"],
                "reference_image": current["reference_image"],
                "updated_utc": utc_now(),
            },
        )
        phase = find_phase_state(state, phase_number)
        if reference_mode == "chain":
            phase["last_reference_path"] = result["output_path"]
    else:
        current["status"] = "failed"
        current["last_error"] = result["error"]
        append_history(
            current,
            {
                "event": "frame-failed",
                "command": result.get("command", ""),
                "error": result["error"],
                "reference_image": current["reference_image"],
                "attempted_edit": attempted_edit,
                "updated_utc": utc_now(),
            },
        )

    sync_phase_state(plan, state, phase_number)
    state["updated_utc"] = utc_now()
    return result


def build_status_payload(plan: dict, state: dict, state_path: Path) -> dict:
    phases = []
    for phase in plan.get("phases", []):
        phases.append(phase_summary(plan, state, int(phase["phase_number"])))

    next_action = "complete"
    next_phase = next_phase_number(plan, state, None)
    if next_phase is not None:
        next_action = phase_summary(plan, state, next_phase)["next_action"]

    return {
        "ok": True,
        "plan_path": state.get("frame_plan_path"),
        "state_path": str(state_path),
        "default_provider_mode": state.get("default_provider_mode") or plan.get("default_provider_mode") or "system-imagegen",
        "next_action": next_action,
        "phases": phases,
    }


def format_status_text(payload: dict) -> str:
    lines = [
        "# Flipbook Batch Runner",
        "",
        f'- Plan: `{payload["plan_path"]}`',
        f'- State: `{payload["state_path"]}`',
        f'- Default provider: `{payload["default_provider_mode"]}`',
        f'- Next action: `{payload["next_action"]}`',
        "",
        "## Phases",
    ]
    for phase in payload["phases"]:
        lines.append(
            f'- `Phase {phase["phase_number"]}: {phase["phase_name"]}` '
            f'anchor=`{phase["anchor_status"]}` fill=`{phase["fill_status"]}` '
            f'frames=`{phase["completed_frame_count"]}/{phase["frame_count"]}`'
        )
    return "\n".join(lines)


def command_status(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan_path).expanduser().resolve()
    plan = load_json(plan_path)
    state_path = normalize_state_path(plan_path, args.state_path)
    state = load_or_initialize_state(plan_path, plan, state_path, persist=False)
    payload = build_status_payload(plan, state, state_path)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_status_text(payload))
    return 0


def command_import_frame(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan_path).expanduser().resolve()
    plan = load_json(plan_path)
    state_path = normalize_state_path(plan_path, args.state_path)
    state = load_or_initialize_state(plan_path, plan, state_path, persist=True)
    payload = import_frame_output(plan, state, int(args.frame), Path(args.path), args.approve_anchor)
    save_json(state_path, state)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        lines = [
            "# Flipbook Batch Runner",
            "",
            f'- Imported `frame {payload["frame_index"]}` into `Phase {payload["phase_number"]}: {payload["phase_name"]}`',
            f'- Path: `{payload["imported_path"]}`',
            f'- Next action: `{payload["next_action"]}`',
        ]
        print("\n".join(lines))
    return 0


def command_approve_anchor(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan_path).expanduser().resolve()
    plan = load_json(plan_path)
    state_path = normalize_state_path(plan_path, args.state_path)
    state = load_or_initialize_state(plan_path, plan, state_path, persist=True)
    phase_number = int(args.phase)
    phase = find_phase_state(state, phase_number)
    approved_path_text = args.path or phase.get("anchor_output_path") or frame_state(state, int(phase["anchor_frame_index"])).get("output_path")
    if not approved_path_text:
        raise SystemExit(f"Phase {phase_number} has no generated anchor yet. Use --path to approve a manual anchor file.")
    approved_path = Path(approved_path_text).expanduser().resolve()
    payload = approve_phase_anchor(plan, state, phase_number, approved_path, "manual approval")
    save_json(state_path, state)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            "\n".join(
                [
                    "# Flipbook Batch Runner",
                    "",
                    f'- Approved anchor for `Phase {payload["phase_number"]}: {payload["phase_name"]}`',
                    f'- Anchor path: `{payload["approved_path"]}`',
                    f'- Next action: `{payload["next_action"]}`',
                ]
            )
        )
    return 0


def command_reject_anchor(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan_path).expanduser().resolve()
    plan = load_json(plan_path)
    state_path = normalize_state_path(plan_path, args.state_path)
    state = load_or_initialize_state(plan_path, plan, state_path, persist=True)
    payload = reject_phase_anchor(plan, state, int(args.phase), args.reason)
    save_json(state_path, state)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            "\n".join(
                [
                    "# Flipbook Batch Runner",
                    "",
                    f'- Rejected anchor for `Phase {payload["phase_number"]}: {payload["phase_name"]}`',
                    f'- Reason: `{payload["reason"] or "No reason provided"}`',
                    f'- Next action: `{payload["next_action"]}`',
                ]
            )
        )
    return 0


def build_manual_system_steps(
    plan: dict,
    state: dict,
    phase_number: int,
    reference_mode: str,
    fill_mode: str,
) -> list[dict]:
    runner_script_path = Path(__file__).resolve()
    phase = find_phase_state(state, phase_number)
    phase_frames = frames_for_phase(plan, phase_number)
    steps: list[dict] = []

    if phase["anchor_status"] != "approved":
        anchor_frame = next(frame for frame in phase_frames if frame.get("is_anchor"))
        expected_path = expected_output_path(plan, anchor_frame).resolve()
        steps.append(
            {
                "phase_number": phase_number,
                "phase_name": phase["phase_name"],
                "step": "anchor",
                "frame_index": int(anchor_frame["frame_index"]),
                "filename": anchor_frame["filename"],
                "operation": "generate",
                "prompt": anchor_frame["prompt"],
                "reference_image": None,
                "expected_output_path": str(expected_path),
                "import_command": f'python "{runner_script_path}" import-frame "{state["frame_plan_path"]}" --frame {anchor_frame["frame_index"]} --path "{expected_path}"',
                "approve_anchor_command": f'python "{runner_script_path}" approve-anchor "{state["frame_plan_path"]}" --phase {phase_number} --path "{expected_path}"',
            }
        )
        return steps

    chain_reference = phase_reference_path(plan, state, phase_number, reference_mode)
    for frame in phase_frames:
        if frame.get("is_anchor"):
            continue
        current = frame_state(state, int(frame["frame_index"]))
        if current["status"] in {"generated", "approved"}:
            if reference_mode == "chain" and current.get("output_path"):
                chain_reference = Path(current["output_path"])
            continue

        if fill_mode == "generate-only":
            operation = "generate"
            prompt = frame["prompt"]
            reference_image = None
        else:
            reference_image = str(chain_reference.resolve()) if chain_reference else None
            if reference_image is None and fill_mode == "edit-only":
                raise SystemExit(f"Phase {phase_number} needs an approved reference image before `edit-only` fill can continue.")
            operation = "edit" if reference_image else "generate"
            prompt = frame["edit_prompt"] if operation == "edit" else frame["prompt"]

        expected_path = expected_output_path(plan, frame).resolve()
        steps.append(
            {
                "phase_number": phase_number,
                "phase_name": phase["phase_name"],
                "step": f'frame {frame["frame_index"]}',
                "frame_index": int(frame["frame_index"]),
                "filename": frame["filename"],
                "operation": operation,
                "prompt": prompt,
                "reference_image": reference_image,
                "expected_output_path": str(expected_path),
                "import_command": f'python "{runner_script_path}" import-frame "{state["frame_plan_path"]}" --frame {frame["frame_index"]} --path "{expected_path}"',
            }
        )
        if reference_mode == "chain":
            chain_reference = expected_path
    return steps


def run_with_cm_imagegen(args: argparse.Namespace, plan: dict, state_path: Path, persistent_state: dict, working_state: dict) -> dict:
    actions: list[dict] = []
    while True:
        phase_number = next_phase_number(plan, working_state, args.phase)
        if phase_number is None:
            break

        summary = phase_summary(plan, working_state, phase_number)
        if summary["completed"]:
            if args.phase is not None:
                break
            continue

        phase_state = find_phase_state(working_state, phase_number)
        if phase_state["anchor_status"] == "generated" and not args.auto_approve_anchors:
            break

        if phase_state["anchor_status"] != "approved":
            result = run_anchor_with_cm(plan, working_state, phase_number, args.timeout, args.dry_run)
            actions.append(
                {
                    "phase_number": phase_number,
                    "phase_name": phase_state["phase_name"],
                    "step": "anchor",
                    "operation": "generate",
                    "ok": result["ok"],
                    "dry_run": args.dry_run,
                    "output_path": result.get("output_path"),
                    "command": result.get("command", ""),
                    "error": result.get("error"),
                    "mode": "cm-imagegen",
                }
            )
            if not result["ok"]:
                break
            if args.auto_approve_anchors:
                approve_phase_anchor(
                    plan,
                    working_state,
                    phase_number,
                    Path(result["output_path"]),
                    "auto approval during run",
                    require_existing_path=not args.dry_run,
                )
            else:
                break

        phase_frames = frames_for_phase(plan, phase_number)
        for planned_frame in phase_frames:
            if planned_frame.get("is_anchor"):
                continue
            current = frame_state(working_state, int(planned_frame["frame_index"]))
            if current["status"] in {"generated", "approved"}:
                continue
            result = run_fill_frame_with_cm(
                plan,
                working_state,
                phase_number,
                planned_frame,
                args.timeout,
                args.dry_run,
                args.reference_mode,
                args.fill_mode,
                args.allow_generate_fallback,
            )
            actions.append(
                {
                    "phase_number": phase_number,
                    "phase_name": phase_state["phase_name"],
                    "step": f'frame {planned_frame["frame_index"]}',
                    "operation": frame_state(working_state, int(planned_frame["frame_index"]))["operation"],
                    "ok": result["ok"],
                    "dry_run": args.dry_run,
                    "output_path": result.get("output_path"),
                    "command": result.get("command", ""),
                    "error": result.get("error"),
                    "reference_image": frame_state(working_state, int(planned_frame["frame_index"]))["reference_image"],
                    "mode": "cm-imagegen",
                }
            )
            if not result["ok"]:
                break

        sync_phase_state(plan, working_state, phase_number)
        if actions and not actions[-1]["ok"]:
            break
        if not args.through_all_phases:
            break
        if args.phase is not None:
            break

    payload = build_status_payload(plan, working_state, state_path)
    payload["actions"] = actions
    payload["dry_run"] = args.dry_run
    payload["provider"] = "cm-imagegen"
    if not args.dry_run:
        working_state["updated_utc"] = utc_now()
        save_json(state_path, working_state)
    return payload


def run_with_system_imagegen(args: argparse.Namespace, plan: dict, state_path: Path, state: dict) -> dict:
    phase_number = next_phase_number(plan, state, args.phase)
    actions: list[dict] = []
    if phase_number is not None:
        for step in build_manual_system_steps(plan, state, phase_number, args.reference_mode, args.fill_mode):
            action = dict(step)
            action["ok"] = True
            action["dry_run"] = args.dry_run
            action["mode"] = "system-imagegen"
            actions.append(action)

    payload = build_status_payload(plan, state, state_path)
    payload["actions"] = actions
    payload["dry_run"] = args.dry_run
    payload["provider"] = "system-imagegen"
    return payload


def command_run(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan_path).expanduser().resolve()
    plan = load_json(plan_path)
    state_path = normalize_state_path(plan_path, args.state_path)
    persistent_state = load_or_initialize_state(plan_path, plan, state_path, persist=not args.dry_run)
    working_state = copy.deepcopy(persistent_state) if args.dry_run else persistent_state
    provider = default_provider_mode(plan, args.provider)

    if provider == "system-imagegen":
        payload = run_with_system_imagegen(args, plan, state_path, working_state)
    else:
        payload = run_with_cm_imagegen(args, plan, state_path, persistent_state, working_state)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        lines = [
            "# Flipbook Batch Runner",
            "",
            f'- Plan: `{payload["plan_path"]}`',
            f'- State: `{payload["state_path"]}`',
            f'- Provider: `{payload["provider"]}`',
            f'- Dry run: `{payload["dry_run"]}`',
        ]
        if payload["actions"]:
            lines.extend(["", "## Actions"])
            for action in payload["actions"]:
                suffix = f' output=`{action["output_path"]}`' if action.get("output_path") else ""
                expected_suffix = f' expected=`{action["expected_output_path"]}`' if action.get("expected_output_path") else ""
                lines.append(
                    f'- `Phase {action["phase_number"]}: {action["phase_name"]}` '
                    f'`{action["step"]}` op=`{action["operation"]}` ok=`{action["ok"]}`{suffix}{expected_suffix}'
                )
                if action.get("reference_image"):
                    lines.append(f'  reference=`{action["reference_image"]}`')
                if action.get("prompt"):
                    lines.append(f'  prompt=`{action["prompt"]}`')
                if action.get("import_command"):
                    lines.append(f'  import=`{action["import_command"]}`')
                if action.get("approve_anchor_command"):
                    lines.append(f'  approve=`{action["approve_anchor_command"]}`')
                if action.get("error"):
                    lines.append(f'  error=`{action["error"]}`')
        else:
            lines.extend(["", "- No new work was emitted or executed."])

        lines.extend(["", "## Next", f'- `{payload["next_action"]}`'])
        lines.extend(["", "## Phases"])
        for phase in payload["phases"]:
            lines.append(
                f'- `Phase {phase["phase_number"]}: {phase["phase_name"]}` '
                f'anchor=`{phase["anchor_status"]}` fill=`{phase["fill_status"]}` '
                f'frames=`{phase["completed_frame_count"]}/{phase["frame_count"]}`'
            )
        print("\n".join(lines))
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "status":
        return command_status(args)
    if args.command == "run":
        return command_run(args)
    if args.command == "import-frame":
        return command_import_frame(args)
    if args.command == "approve-anchor":
        return command_approve_anchor(args)
    if args.command == "reject-anchor":
        return command_reject_anchor(args)
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
