#!/usr/bin/env python3
"""Evaluate a Level Sequence at frames and record what it actually does (state evidence, no screenshots).

    python scripts/sequence_sample.py /Game/Cinematics/LS_Intro --allow-editor-ui --project MyGame --frames 0,45,90 --out <dir>
    python scripts/sequence_sample.py /Game/Cinematics/LS_Intro --allow-editor-ui --project MyGame --apply-report <dir>/apply-report.json --out <dir>

For every sampled frame it records each bound actor's transform, the camera components' focal
length / aperture / focus distance, and which camera the camera cuts select. With --apply-report
(from sequence_plan_apply.py) it also samples every planned camera and actor key and checks
location (1 cm), rotation (0.5 deg), focal length (0.1 mm), focus (1 cm), aperture (0.01) against the plan, and traces a
line of sight from every aimed camera key to its look-at point (SceneTools.trace_world): a hit
before the target's bounds means the subject is blocked. Exit 1 when any check fails.
UI evaluation requires explicit --allow-editor-ui. Restore the previous idle root sequence
and playhead on success or failure; never interrupt playback. Cut labels are structure-derived.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

SCHEMA_VERSION = "sequence_sample/2"
TOLERANCE = {"location": 1.0, "angle": 0.5, "focal": 0.1, "focus": 1.0, "aperture": 0.01}
OCCLUSION_SLACK = 5.0   # cm a trace may stop short of the target's bounds before it counts as blocked


def angle_delta(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def active_camera(cuts: list[dict[str, Any]], frame: int) -> str | None:
    for cut in cuts:
        if cut["start"] is not None and cut["end"] is not None and cut["start"] <= frame < cut["end"]:
            return cut["camera"]
    return None


def check_keys(samples: dict[int, dict[str, Any]], planned: dict[str, Any]) -> list[dict[str, Any]]:
    """Compare sampled state (rows keyed by binding id) with the resolved camera/actor keys of an apply report."""
    checks = []
    for camera_id, info in planned.items():
        binding = info["binding"].replace("-", "").upper()
        for key in info["keys"]:
            state = samples.get(key["frame"], {}).get("bindings", {}).get(binding, {})
            row = {"camera": camera_id, "frame": key["frame"], "ok": True, "diff": {}, "checked": []}
            transform = state.get("transform")
            if transform is None and any(key.get(p) is not None for p in ("location", "rotation")):
                row.update(ok=False, diff={"missing": "no transform sampled"})
                row["checked"].append("transform_missing")
            elif transform is not None:
                if key.get("location") is not None:
                    loc = transform["location"]
                    d = max(abs(loc[a] - v) for a, v in zip("xyz", key["location"]))
                    row["diff"]["location"] = round(d, 3)
                    row["ok"] &= d <= TOLERANCE["location"]
                    row["checked"].append("location")
                if key.get("rotation") is not None:
                    rot = transform["rotation"]
                    expected = (list(key["rotation"]) + [0.0])[:3]
                    d = max(angle_delta(rot[axis], value) for axis, value in zip(("pitch", "yaw", "roll"), expected))
                    row["diff"]["angle"] = round(d, 3)
                    row["ok"] &= d <= TOLERANCE["angle"]
                    row["checked"].append("rotation_pitch_yaw_roll")
            for field, prop in (("focal", "CurrentFocalLength"), ("focus", "ManualFocusDistance"), ("aperture", "CurrentAperture")):
                if key.get(field) is not None:
                    value = state.get("camera", {}).get(prop)
                    d = abs(value - key[field]) if value is not None else None
                    row["diff"][field] = None if d is None else round(d, 3)
                    row["ok"] &= d is not None and d <= TOLERANCE[field]
                    row["checked"].append(field)
                    if field == "focus":
                        method = state.get("camera", {}).get("FocusMethod")
                        manual = isinstance(method, str) and method.rsplit(".", 1)[-1].lower() == "manual"
                        row["diff"]["focus_method"] = method
                        row["ok"] &= manual
            row["ok"] &= bool(row["checked"])
            checks.append(row)
    return checks


def occlusion_checks(editor: Any, cameras: dict[str, Any], sample_row: dict, frame: int) -> list[dict[str, Any]]:
    """Run immediately after evaluating this frame, using the sampled camera and current target."""
    from sequencer_tools.plan import ray_box_entry

    checks = []
    for camera_id, info in cameras.items():
        for key in info["keys"]:
            if key["frame"] != frame or key.get("look_at") is None:
                continue
            binding = info["binding"].replace("-", "").upper()
            transform = sample_row["bindings"].get(binding, {}).get("transform")
            if transform is None:
                checks.append({"camera": camera_id, "frame": frame, "check": "line_of_sight", "ok": False,
                               "diff": {"missing": "camera transform"}})
                continue
            origin = [transform["location"][a] for a in "xyz"]
            aim, box = key["look_at"], None
            if isinstance(aim, str):
                actor = editor.find_actor(aim)
                if actor is None:
                    checks.append({"camera": camera_id, "frame": frame, "check": "line_of_sight", "ok": False,
                                   "diff": {"missing": f"target {aim}"}})
                    continue
                box = editor.actor_bounds(actor)
                aim = ([sum(v) / 2 for v in zip(*box)] if box and info.get("aim", "bounds") == "bounds"
                       else editor.actor_location(actor))
            distance = sum((aim[i] - origin[i]) ** 2 for i in range(3)) ** 0.5
            entry = ray_box_entry(origin, aim, *box) if box else None
            clear_until = (entry if entry is not None else distance) - OCCLUSION_SLACK
            hit = editor.call("SceneTools", "trace_world", start=dict(zip("xyz", origin)), end=dict(zip("xyz", aim)))
            ok = hit is None or float(hit) >= clear_until
            checks.append({"camera": camera_id, "frame": key["frame"], "check": "line_of_sight", "ok": ok,
                           "diff": {"first_hit_cm": None if hit is None else round(float(hit), 1),
                                    "target_at_cm": round(max(clear_until + OCCLUSION_SLACK, 0), 1)}})
    return checks


def sample(editor: Any, sequence: str, frames: list[int], cuts: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """{frame: {"camera_cut": binding id, "bindings": {binding id: {"transform"|"camera": ...}}}}"""
    from sequencer_tools.editor import object_ref

    seq = object_ref(sequence)
    bindings = editor.seq("get_bindings", sequence=seq) or []
    out: dict[int, dict[str, Any]] = {}
    for frame in frames:
        editor.seq("set_playhead_frame", frame=frame)
        editor.seq("force_evaluate")
        row: dict[str, Any] = {"camera_cut": active_camera(cuts, frame), "bindings": {}}
        for binding in bindings:
            key = binding["bindingId"].replace("-", "").upper()
            for obj in editor.seq("get_bound_objects", binding=binding) or []:
                state = row["bindings"].setdefault(key, {})
                if "Component" in obj["refPath"].rsplit(".", 1)[-1]:
                    props = editor.call("ObjectTools", "get_properties", instance=obj,
                                        properties=["CurrentFocalLength", "CurrentAperture", "FocusSettings"]) or {}
                    focus = props.get("FocusSettings") if isinstance(props.get("FocusSettings"), dict) else {}
                    state["camera"] = {"CurrentFocalLength": props.get("CurrentFocalLength"),
                                       "CurrentAperture": props.get("CurrentAperture"),
                                       "ManualFocusDistance": focus.get("manualFocusDistance", focus.get("ManualFocusDistance")),
                                       "FocusMethod": focus.get("focusMethod", focus.get("FocusMethod"))}
                else:
                    state["transform"] = editor.call("ActorTools", "get_actor_transform", actor=obj)
        out[frame] = row
    return out


def sample_session(editor: Any, sequence: str, frames: list[int], cuts: list[dict], dump: dict,
                   cameras: dict, *, allow_editor_ui: bool = False, keep_open: bool = False) -> tuple[dict, list]:
    from sequencer_tools.editor import object_ref
    state = editor.sequence_state(allow_editor_ui=allow_editor_ui)
    if editor.call("EditorAppToolset", "IsPIERunning") is not False:
        raise RuntimeError("PIE/Simulate is running or its state is unknown; no sequence evaluation performed.")
    samples, sight = {}, []
    with editor.sequence_session(object_ref(sequence), state, keep_open=keep_open):
        for frame in frames:
            row = sample(editor, sequence, [frame], cuts)
            attach_camera_state(row, dump)
            sight.extend(occlusion_checks(editor, cameras, row[frame], frame))
            samples.update(row)
    return samples, sight


def verification(checks: list[dict]) -> dict:
    return {"status": ("passed" if all(c["ok"] for c in checks) else "failed") if checks else "collected",
            "checks_performed": len(checks), "passed": all(c["ok"] for c in checks) if checks else None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sequence")
    parser.add_argument("--frames", default="", help="Comma-separated display-rate frames")
    parser.add_argument("--apply-report", type=Path, help="apply-report.json from sequence_plan_apply.py")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--keep-open", action="store_true")
    parser.add_argument("--allow-editor-ui", action="store_true", help="Explicitly permit opening Sequencer for evaluation")
    parser.add_argument("--project", default=os.environ.get("UE_MCP_PROJECT"))
    args = parser.parse_args(argv)
    if not args.allow_editor_ui:
        parser.error("sampling currently requires opening Sequencer; background policy refuses. Use --allow-editor-ui only when requested.")
    if not args.project:
        parser.error("--project or UE_MCP_PROJECT is required")

    from sequence_inspect import dump_sequence
    from sequencer_tools.editor import Editor

    dump = dump_sequence(args.sequence, args.project)
    names = {b["id"]: b["display"] or b["name"] for b in dump["bindings"]}
    cuts = [s for t in dump["tracks"] if t["class"] == "MovieSceneCameraCutTrack" for s in t["sections"]]
    frames = {int(f) for f in args.frames.split(",") if f.strip()}
    planned, result = {}, {}
    if args.apply_report:
        result = json.loads(args.apply_report.read_text(encoding="utf-8"))["result"]
        planned = {**result["cameras"], **{label: info for label, info in result.get("actors", {}).items() if info.get("keys")}}
        frames |= {k["frame"] for info in planned.values() for k in info["keys"]}
    if not frames:
        frames = {dump["playback"][0], (dump["playback"][0] + dump["playback"][1]) // 2, dump["playback"][1] - 1}
    editor = Editor(args.project)
    try:
        samples, sight = sample_session(editor, args.sequence, sorted(frames), cuts, dump, result.get("cameras", {}),
                                       allow_editor_ui=args.allow_editor_ui, keep_open=args.keep_open)
    finally:
        editor.close()
    attach_camera_state(samples, dump)
    checks = (check_keys(samples, planned) if planned else []) + sight
    readable = {str(f): {"camera_cut": names.get(r["camera_cut"] or "", r["camera_cut"]),
                         "bindings": {names.get(i, i): st for i, st in r["bindings"].items()}}
                for f, r in sorted(samples.items())}
    report = {"tool": "sequence_sample", "schema_version": SCHEMA_VERSION, "sequence": dump["sequence"],
              "frames": sorted(frames), "samples": readable,
              "checks": checks, **verification(checks),
              "coverage": {"checked_fields": sorted({p for c in checks for p in c.get("checked", [])}),
                           "not_verified": ["runtime active camera selection (cut names are structural)", "fade output",
                                            "skeletal animation playback", "event execution", "gameplay exit/skip state"]}}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "samples.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for frame, row in readable.items():
        print(frame, "cut:", row["camera_cut"], {n: _brief(st) for n, st in row["bindings"].items() if _brief(st)})
    for check in checks:
        print("PASS" if check["ok"] else "FAIL", check.get("check", "key"), check["camera"], check["frame"], check["diff"])
    return 1 if report["passed"] is False else 0


def attach_camera_state(samples: dict[int, dict[str, Any]], dump: dict[str, Any]) -> None:
    """Move each camera component child's state onto its parent camera binding row (rows keyed by id)."""
    for row in samples.values():
        for binding in dump["bindings"]:
            state = row["bindings"].get(binding["id"])
            if binding.get("parent") and state and "camera" in state:
                row["bindings"].setdefault(binding["parent"], {})["camera"] = state["camera"]
                del row["bindings"][binding["id"]]


def _brief(state: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "transform" in state:
        loc, rot = state["transform"]["location"], state["transform"]["rotation"]
        out["loc"] = [round(loc[a], 1) for a in "xyz"]
        out["rot"] = [round(rot[a], 1) for a in ("pitch", "yaw", "roll")]
    if "camera" in state:
        out["focal"] = state["camera"].get("CurrentFocalLength")
    return out


if __name__ == "__main__":
    raise SystemExit(main())
