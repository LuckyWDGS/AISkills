"""Read a Level Sequence's structure (stock editor Python, read-only) and lint it (pure Python)."""

from __future__ import annotations

from typing import Any

DUMP_SCRIPT = r'''
import json, unreal

def _codex_dump():
    seq = unreal.load_asset(__SEQ__)
    if not isinstance(seq, unreal.LevelSequence):
        print("CODEX_SEQ " + json.dumps({"error": "not a LevelSequence: " + __SEQ__}))
        return
    unit = unreal.MovieSceneTimeUnit.DISPLAY_RATE
    guid = lambda g: unreal.GuidLibrary.conv_guid_to_string(g).upper()

    def frames(section):
        start = section.get_start_frame() if section.has_start_frame() else None
        end = section.get_end_frame() if section.has_end_frame() else None
        return start, end

    def channel_rows(section):
        rows = []
        for channel in section.get_all_channels():
            keys = []
            try:
                for key in channel.get_keys():
                    value = key.get_value()
                    keys.append([key.get_time(unit).frame_number.value, value if isinstance(value, (int, float, bool)) else str(value)])
            except Exception:
                pass
            rows.append({"name": str(channel.get_name()), "keys": keys})
        return rows

    def section_row(section):
        start, end = frames(section)
        row = {"name": section.get_name(), "class": section.get_class().get_name(), "start": start, "end": end,
               "channels": channel_rows(section)}
        if isinstance(section, unreal.MovieSceneCameraCutSection):
            row["camera"] = guid(section.get_camera_binding_id().get_editor_property("guid"))
        if isinstance(section, unreal.MovieSceneSkeletalAnimationSection):
            anim = section.get_editor_property("params").get_editor_property("animation")
            row["animation"] = anim.get_path_name() if anim else None
        return row

    def track_row(track):
        return {"name": track.get_name(), "class": track.get_class().get_name(), "display": str(track.get_display_name()),
                "sections": [section_row(s) for s in track.get_sections()]}

    bindings = []
    for binding in seq.get_bindings():
        children = [guid(c.get_id()) for c in binding.get_child_possessables()]
        parent = binding.get_parent()
        bindings.append({"id": guid(binding.get_id()), "name": str(binding.get_name()), "display": str(binding.get_display_name()),
                         "parent": guid(parent.get_id()) if parent and parent.is_valid() else None, "children": children,
                         "tracks": [track_row(t) for t in binding.get_tracks()]})
    rate, tick = seq.get_display_rate(), seq.get_tick_resolution()
    print("CODEX_SEQ " + json.dumps({
        "sequence": seq.get_path_name(),
        "display_rate": [rate.numerator, rate.denominator], "tick_resolution": [tick.numerator, tick.denominator],
        "playback": [seq.get_playback_start(), seq.get_playback_end()],
        "tracks": [track_row(t) for t in seq.get_tracks()], "bindings": bindings}))

_codex_dump()
'''

CAMERA_HINTS = ("CameraComponent",)


def camera_ids(dump: dict[str, Any]) -> set[str]:
    """Bindings that own a camera component child (cine cameras, camera actors)."""
    by_id = {b["id"]: b for b in dump["bindings"]}
    found = set()
    for binding in dump["bindings"]:
        if any(by_id.get(c, {}).get("name") in CAMERA_HINTS for c in binding["children"]):
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
