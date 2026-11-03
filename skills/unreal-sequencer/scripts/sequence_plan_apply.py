#!/usr/bin/env python3
"""Build a Level Sequence from a shot plan (JSON) through Epic's Sequencer MCP toolsets.

    python scripts/sequence_plan_apply.py plan.json                      # validate and print the frame-normalized plan
    python scripts/sequence_plan_apply.py plan.json --execute --out <dir> # build it in the running editor

The plan format is in references/shot-plan.md. Execution creates the sequence, spawnable cine
cameras with transform/focal/focus/aperture keys (look_at aims them at actors or points), camera
cuts, possessable bindings for level actors with transform keys and skeletal animation sections,
and an optional fade track. It refuses to overwrite an existing asset unless --replace is given
(Epic's create_level_sequence deletes an existing asset at the path). Nothing is saved unless
--save is passed, which only the user may ask for.
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

from sequencer_tools.plan import look_at_targets, normalize, resolve_camera_keys, validate  # noqa: E402

SCHEMA_VERSION = "sequence_plan_apply/1"


def build(plan: dict[str, Any], editor: Any, *, replace: bool = False, keep_open: bool = False,
          save: bool = False) -> dict[str, Any]:
    from sequencer_tools.editor import TRACK, short

    seq_info = plan["sequence"]
    path = seq_info["path"].split(".")[0]
    report: dict[str, Any] = {"sequence": path, "cameras": {}, "shots": [], "actors": {}, "targets": {}, "fade": None,
                              "saved": False}
    if editor.call("EditorAppToolset", "IsPIERunning"):
        raise RuntimeError("stop PIE before editing sequences")
    if editor.asset_exists(path) and not replace:
        raise RuntimeError(f"{path} already exists; pass --replace to rebuild it (the old asset is deleted)")

    # look_at aims at an actor's bounds centre ("aim": "bounds", default) or its pivot ("aim": "pivot").
    positions: dict[str, dict[str, list[float]]] = {"bounds": {}, "pivot": {}}
    actors: dict[str, dict[str, str]] = {}
    for label in sorted(look_at_targets(plan) | {a["actor"] for a in plan.get("actors", [])}):
        actor = editor.find_actor(label)
        if actor is None:
            raise RuntimeError(f"no actor labelled {label!r} in the current level")
        actors[label] = actor
        positions["pivot"][label] = editor.actor_location(actor)
        positions["bounds"][label] = editor.actor_bounds_center(actor)
        report["targets"][label] = {"pivot": positions["pivot"][label], "bounds": editor.actor_bounds(actor)}

    package, name = path.rsplit("/", 1)
    seq = editor.seq("create_level_sequence", package_path=package, asset_name=name)
    editor.seq("set_display_rate", sequence=seq, numerator=int(seq_info["fps"]), denominator=1)
    editor.seq("set_playback_range", sequence=seq, start_frame=seq_info["start_frame"], end_frame=seq_info["end_frame"])
    editor.seq("open_sequence", sequence=seq)

    cameras: dict[str, dict[str, Any]] = {}
    for camera in plan.get("cameras", []):
        binding = editor.seq("create_camera", spawnable=True)
        editor.seq("set_binding_name", binding=binding, name=camera.get("label") or camera["id"])
        interpolation = camera.get("interpolation", "cubic")
        section = editor.transform_section(binding)
        props = editor.camera_property_sections(binding)
        keys = resolve_camera_keys(camera, positions[camera.get("aim", "bounds")])
        for index, key in enumerate(keys):
            editor.key_transform(section, key["frame"], key.get("location"), key.get("rotation"), interpolation)
            for prop in ("focal", "focus", "aperture"):
                value = key.get(prop, camera.get(prop) if index == 0 else None)
                if value is not None and prop in props:
                    editor.add_float_key(props[prop], "None", key["frame"], value, interpolation)
        cameras[camera["id"]] = binding
        report["cameras"][camera["id"]] = {"binding": binding["bindingId"], "keys": keys, "property_tracks": sorted(props)}

    shots = sorted(plan.get("shots", []), key=lambda s: s["start_frame"])
    # create_camera also adds a camera cut track with one cut per new camera; replace those with the plan's shots.
    cut_track = next((t for t in editor.seq("get_tracks_on_sequence", sequence=seq) or []
                      if "MovieSceneCameraCutTrack" in t["refPath"].rsplit(".", 1)[-1]), None)
    if cut_track:
        for section in editor.seq("get_sections", track=cut_track) or []:
            editor.seq("remove_section", track=cut_track, section=section)
    if shots:
        cut_track = cut_track or editor.seq("add_track_to_sequence", sequence=seq, track_type={"refPath": TRACK["camera_cut"]})
        cuts = []
        for shot in shots:
            section = editor.seq("add_section", track=cut_track)
            editor.seq("set_section_range", section=section, start_frame=shot["start_frame"], end_frame=shot["end_frame"])
            cuts.append((short(section), cameras[shot["camera"]]["bindingId"]))
            report["shots"].append({"camera": shot["camera"], "start_frame": shot["start_frame"],
                                    "end_frame": shot["end_frame"], "section": short(section)})
        bound = editor.bind_camera_cuts(path, cuts)
        for shot, result in zip(report["shots"], bound):
            shot["bound"] = bool(result.get("ok"))

    for entry in plan.get("actors", []):
        label = entry["actor"]
        binding = (editor.seq("add_actors", actors=[actors[label]]) or [None])[0]
        if binding is None:
            raise RuntimeError(f"could not bind {label}")
        info: dict[str, Any] = {"binding": binding["bindingId"]}
        if entry.get("keys"):
            current = editor.call("ActorTools", "get_actor_transform", actor=actors[label])
            section = editor.transform_section(binding, current)
            origin = [current["location"][a] for a in "xyz"]
            resolved = []
            for key in entry["keys"]:
                location = key.get("location")
                if key.get("offset") is not None:
                    location = [origin[i] + key["offset"][i] for i in range(3)]
                editor.key_transform(section, key["frame"], location, key.get("rotation"),
                                     entry.get("interpolation", "cubic"))
                resolved.append({"frame": key["frame"], "location": location, "rotation": key.get("rotation")})
            info["keys"] = resolved
            info["start_transform"] = current
        anim = entry.get("animation")
        if anim:
            track = editor.seq("add_track_to_binding", binding=binding, track_type={"refPath": TRACK["skeletal"]})
            section = editor.seq("add_section", track=track)
            editor.seq("set_section_animation", section=section, anim_sequence_path=anim["asset"])
            editor.seq("set_section_range", section=section, start_frame=anim["start_frame"], end_frame=anim["end_frame"])
            info["animation"] = short(section)
        report["actors"][label] = info

    if plan.get("fade"):
        track = editor.seq("add_track_to_sequence", sequence=seq, track_type={"refPath": TRACK["fade"]})
        section = editor.seq("add_section", track=track)
        channel = (editor.key("get_channel_names", section=section) or ["None"])[0]
        for key in plan["fade"]:
            editor.add_float_key(section, channel, key["frame"], key["value"], key.get("interpolation", "linear"))
        report["fade"] = {"channel": channel, "keys": len(plan["fade"])}

    editor.seq("set_playhead_frame", frame=seq_info["start_frame"])
    editor.seq("force_evaluate")
    if save:
        script = ("import json, unreal\nprint('CODEX_SEQ ' + json.dumps(unreal.EditorAssetLibrary.save_asset("
                  + json.dumps(path) + ", only_if_is_dirty=False)))")
        report["saved"] = bool(editor.python(script))
    if not keep_open:
        editor.seq("close_sequence")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--execute", action="store_true", help="Build in the running editor (default: validate only)")
    parser.add_argument("--replace", action="store_true", help="Rebuild an existing sequence asset (deletes it first)")
    parser.add_argument("--keep-open", action="store_true", help="Leave the sequence open in Sequencer")
    parser.add_argument("--save", action="store_true", help="Save the sequence asset (only when the user asked)")
    parser.add_argument("--out", type=Path, help="Directory for apply-report.json")
    parser.add_argument("--project", default=os.environ.get("UE_MCP_PROJECT"))
    args = parser.parse_args(argv)
    plan = normalize(json.loads(args.plan.read_text(encoding="utf-8")))
    findings = validate(plan)
    report: dict[str, Any] = {"tool": "sequence_plan_apply", "schema_version": SCHEMA_VERSION, "plan": str(args.plan),
                              "findings": findings, "executed": False}
    errors = [f for f in findings if f["severity"] == "error"]
    if args.execute and not errors:
        from sequencer_tools.editor import Editor

        editor = Editor(args.project)
        try:
            report["result"] = build(plan, editor, replace=args.replace, keep_open=args.keep_open, save=args.save)
            report["executed"] = True
        except Exception as exc:
            report["error"] = str(exc)
        finally:
            report["calls"] = len(editor.calls)
            editor.close()
    else:
        report["normalized_plan"] = plan
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "apply-report.json").write_text(text + "\n", encoding="utf-8")
    print(text)
    if errors:
        return 2
    return 1 if report.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
