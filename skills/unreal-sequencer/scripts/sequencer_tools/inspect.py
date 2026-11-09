"""Read a Level Sequence's structure (MCP first, read-only) and lint it (pure Python)."""

from __future__ import annotations

import json
from typing import Any


def decoded(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def mcp_dump(editor: Any, asset: str) -> dict[str, Any]:
    """Read covered structure/keys through MCP; Python reads only missing binding/section metadata."""
    from .editor import object_ref, short
    seq = object_ref(asset)
    rate = decoded(editor.seq("get_display_rate", sequence=seq))
    tick = decoded(editor.seq("get_tick_resolution", sequence=seq))
    playback = decoded(editor.seq("get_playback_range", sequence=seq))
    gaps: list[dict[str, Any]] = []

    def section_row(section):
        cls = short(editor.call("ObjectTools", "get_class", instance=section))
        has_start = editor.seq("has_section_start_frame", section=section)
        has_end = editor.seq("has_section_end_frame", section=section)
        bounds = decoded(editor.seq("get_section_range", section=section)) if has_start and has_end else {}
        row = {"name": short(section), "class": cls, "start": bounds.get("start"), "end": bounds.get("end"),
               "channels": [], "ref": section}
        if cls == "MovieSceneCameraCutSection":
            row["camera_binding"] = editor.camera_binding_id(section)
            row["camera"] = row["camera_binding"]["guid"].replace("-", "").upper()
        if has_start != has_end or cls == "MovieSceneSkeletalAnimationSection":
            gaps.append({"path": section["refPath"], "class": cls, "partial_range": has_start != has_end})
        for channel in editor.key("get_channel_names", section=section) or []:
            keys = decoded(editor.key("get_keys", section=section, channel_name=channel))
            row["channels"].append({"name": channel, "keys": [[key["frame"], key["value"]] for key in keys]})
        return row

    def track_row(track):
        return {"name": short(track), "class": short(editor.call("ObjectTools", "get_class", instance=track)),
                "display": editor.seq("get_track_display_name", track=track),
                "sections": [section_row(s) for s in editor.seq("get_sections", track=track) or []]}

    bindings = []
    for binding in editor.seq("get_bindings", sequence=seq) or []:
        bid = binding["bindingId"].replace("-", "").upper()
        display = editor.seq("get_binding_name", binding=binding)
        children = [child["bindingId"].replace("-", "").upper()
                    for child in editor.seq("get_child_possessables", binding=binding) or []]
        bindings.append({"id": bid, "name": display, "display": display, "parent": None, "children": children,
                         "tracks": [track_row(t) for t in editor.seq("get_tracks_on_binding", binding=binding) or []]})
    tracks = [track_row(t) for t in editor.seq("get_tracks_on_sequence", sequence=seq) or []]
    # MCP ObjectTools covers cut IDs; Python supplies only the remaining metadata gaps.
    script = r'''
import json, unreal
def _codex_metadata():
    seq = unreal.load_asset(__SEQ__)
    guid = lambda g: unreal.GuidLibrary.conv_guid_to_string(g).upper()
    names = {}
    for b in seq.get_bindings():
        parent = b.get_parent()
        template = b.get_object_template()
        cls = template.get_class() if template else b.get_possessed_object_class()
        names[guid(b.get_id())] = {"name": str(b.get_name()), "parent": guid(parent.get_id()) if parent and parent.is_valid() else None,
                                 "object_class": cls.get_path_name() if cls else None,
                                 "is_camera": isinstance(unreal.get_default_object(cls), unreal.CameraActor) if cls else None}
    sections = {}
    for request in json.loads(__REQUESTS__):
        obj = unreal.find_object(None, request["path"])
        if obj is None:
            raise RuntimeError("Section no longer resolves: " + request["path"])
        row = {}
        if request["partial_range"]:
            row["start"] = obj.get_start_frame() if obj.has_start_frame() else None
            row["end"] = obj.get_end_frame() if obj.has_end_frame() else None
        if request["class"] == "MovieSceneSkeletalAnimationSection":
            anim = obj.get_editor_property("params").get_editor_property("animation")
            row["animation"] = anim.get_path_name() if anim else None
        sections[request["path"]] = row
    print("CODEX_SEQ " + json.dumps({"bindings": names, "sections": sections}))
_codex_metadata()
'''
    metadata = {"bindings": {}, "sections": {}}
    if bindings or gaps:
        script = script.replace("__SEQ__", json.dumps(asset.split(".")[0])).replace("__REQUESTS__", repr(json.dumps(gaps)))
        metadata = editor.python(script, gap="No MCP getters for binding internal name/parent/template class, animation and one-sided section ranges (UE 5.8.4 source).")
    for binding in bindings:
        binding.update(metadata["bindings"][binding["id"]])
    for track in tracks + [t for b in bindings for t in b["tracks"]]:
        for section in track["sections"]:
            section.update(metadata["sections"].get(section.pop("ref")["refPath"], {}))
    return {"sequence": seq["refPath"], "display_rate": [rate["numerator"], rate["denominator"]],
            "tick_resolution": [tick["numerator"], tick["denominator"]],
            "playback": [playback["start"], playback["end"]], "tracks": tracks, "bindings": bindings,
            "transport": "Epic MCP; stock Python only for identified metadata gaps"}

CAMERA_HINTS = ("CameraComponent",)


def camera_ids(dump: dict[str, Any]) -> set[str]:
    """Camera actor classes and bindings that own a camera component child."""
    by_id = {b["id"]: b for b in dump["bindings"]}
    found = set()
    for binding in dump["bindings"]:
        if binding.get("is_camera") is True or any(by_id.get(c, {}).get("name") in CAMERA_HINTS for c in binding["children"]):
            found.add(binding["id"])
    return found


def lint(dump: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def add(severity: str, rule: str, message: str) -> None:
        out.append({"severity": severity, "rule": rule, "message": message})

    start, end = dump["playback"]
    ids = {b["id"]: b for b in dump["bindings"]}
    cameras = camera_ids(dump)
    cut_tracks = [t for t in dump["tracks"] if t["class"] == "MovieSceneCameraCutTrack"]
    if cameras and not cut_tracks:
        add("warning", "no_camera_cuts", "cameras exist but there is no camera cut track; the sequence never takes the view")
    cuts = sorted((s for t in cut_tracks for s in t["sections"]), key=lambda s: (s["start"] is None, s["start"] or 0))
    used = set()
    cursor = start
    for cut in cuts:
        camera = cut.get("camera") or ""
        if camera.strip("0") == "" or camera not in ids:
            add("error", "cut_without_camera", f"camera cut {cut['name']} ({cut['start']}-{cut['end']}) is not bound to a camera in this sequence")
        used.add(camera)
        if cut["start"] is None or cut["end"] is None:
            add("warning", "cut_unbounded", f"camera cut {cut['name']} has an open range")
            continue
        if cut["start"] > cursor:
            add("warning", "cut_gap", f"no camera cut between frames {cursor} and {cut['start']}")
        elif cut["start"] < cursor:
            add("error", "cut_overlap", f"camera cut {cut['name']} starts at {cut['start']} before the previous cut ends at {cursor}")
        cursor = max(cursor, cut["end"])
    if cuts and cursor < end:
        add("warning", "cut_gap", f"no camera cut between frames {cursor} and {end}")
    for camera in sorted(cameras - used):
        add("warning", "unused_camera", f"camera {ids[camera]['display'] or ids[camera]['name']} is never cut to")
    for owner, tracks in [("sequence", dump["tracks"])] + [(b["display"] or b["name"], b["tracks"]) for b in dump["bindings"]]:
        for track in tracks:
            if track["class"] == "MovieSceneSpawnTrack":
                continue
            if not track["sections"]:
                add("warning", "empty_track", f"{owner}: track {track['display'] or track['class']} has no sections")
            for section in track["sections"]:
                if section["start"] is not None and section["end"] is not None and section["end"] <= section["start"]:
                    add("warning", "empty_section", f"{owner}: section {section['name']} has no length")
                if section["class"] == "MovieSceneSkeletalAnimationSection" and not section.get("animation"):
                    add("error", "animation_missing", f"{owner}: skeletal animation section {section['name']} has no animation")
                for channel in section["channels"]:
                    outside = [k[0] for k in channel["keys"] if not start <= k[0] <= end]
                    if outside:
                        add("info", "key_outside_range", f"{owner}: {track['display'] or track['class']}.{channel['name']} "
                            f"has keys outside {start}-{end}: {outside[:4]}")
    return out


def summarize(dump: dict[str, Any]) -> dict[str, Any]:
    cuts = [s for t in dump["tracks"] if t["class"] == "MovieSceneCameraCutTrack" for s in t["sections"]]
    names = {b["id"]: b["display"] or b["name"] for b in dump["bindings"]}
    rate = dump["display_rate"][0] / dump["display_rate"][1]
    return {
        "fps": rate, "playback": dump["playback"],
        "seconds": round((dump["playback"][1] - dump["playback"][0]) / rate, 3),
        "cameras": sorted(names[c] for c in camera_ids(dump)),
        "cuts": [{"camera": names.get(c.get("camera"), c.get("camera")), "start": c["start"], "end": c["end"]} for c in cuts],
        "bindings": [{"name": b["name"], "tracks": [t["display"] or t["class"] for t in b["tracks"]]} for b in dump["bindings"]],
    }
