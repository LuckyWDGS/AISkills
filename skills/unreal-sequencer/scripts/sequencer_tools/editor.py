"""Thin editor-side wrapper over Epic's Sequencer MCP toolsets, with the verified UE 5.8 workarounds.

Verified behaviour (UE 5.8.4, see references/sequencer-mcp-toolsets.md):
- Frames in every Sequencer tool are display-rate frames, not tick-resolution ticks.
- create_camera / add_actors work on the sequence open in Sequencer, so open_sequence first.
- create_camera adds a transform track, a spawn track and, on its CameraComponent child binding,
  float tracks CurrentFocalLength, ManualFocusDistance and CurrentAperture: key those, never add
  duplicates (a second track for the same property is overridden and does nothing).
- Transform channels: Location.X/Y/Z, Rotation.X = roll, Rotation.Y = pitch, Rotation.Z = yaw.
- A float property section has one channel named "None".
- set_property_name_and_path's display_name argument becomes the property *name*: pass the
  property's FName (e.g. "CurrentFocalLength"), not a spaced label.
- set_camera_cut_binding fails inside the tool ("call() takes at most 0 arguments"); camera cuts
  are bound with stock editor Python instead (bind_camera_cuts).
- SceneTools.find_actors(name=...) is a substring match on actor labels; filter on the exact label.
"""

from __future__ import annotations

import json
from typing import Any

from .mcp import connect, run_python, stdout_of, unwrap_result

SEQ_TOOLS = "SequencerTools"
KEY_TOOLS = "SequencerKeyframingTools"
CAMERA_TRACKS = {"focal": "CurrentFocalLength", "focus": "ManualFocusDistance", "aperture": "CurrentAperture"}
TRACK = {
    "camera_cut": "/Script/MovieSceneTracks.MovieSceneCameraCutTrack",
    "transform": "/Script/MovieSceneTracks.MovieScene3DTransformTrack",
    "skeletal": "/Script/MovieSceneTracks.MovieSceneSkeletalAnimationTrack",
    "fade": "/Script/MovieSceneTracks.MovieSceneFadeTrack",
    "float": "/Script/MovieSceneTracks.MovieSceneFloatTrack",
    "event": "/Script/MovieSceneTracks.MovieSceneEventTrack",
}


def object_ref(asset_path: str) -> dict[str, str]:
    name = asset_path.rsplit("/", 1)[-1]
    return {"refPath": asset_path if "." in name else f"{asset_path}.{name}"}


def short(ref: Any) -> str:
    path = ref.get("refPath", "") if isinstance(ref, dict) else str(ref)
    return path.rsplit(".", 1)[-1].rsplit(":", 1)[-1]


class Editor:
    """One MCP session plus editor-Python calls; every tool call is recorded in self.calls."""

    def __init__(self, project: str | None = None):
        self.project = project
        self.client = connect(project=project)
        self.calls: list[dict[str, Any]] = []

    def close(self) -> None:
        self.client.close()

    def call(self, toolset: str, tool: str, **args: Any) -> Any:
        try:
            result = unwrap_result(self.client.call_resolved_tool(toolset, tool, args))
        except Exception as exc:
            self.calls.append({"tool": f"{toolset}.{tool}", "args": args, "error": str(exc)[:400]})
            raise
        self.calls.append({"tool": f"{toolset}.{tool}", "args": args, "result": result})
        return result

    def seq(self, tool: str, **args: Any) -> Any:
        return self.call(SEQ_TOOLS, tool, **args)

    def key(self, tool: str, **args: Any) -> Any:
        return self.call(KEY_TOOLS, tool, **args)

    def python(self, script: str, marker: str = "CODEX_SEQ ") -> Any:
        """Run stock editor Python; the script prints one marker line with a JSON payload."""
        result = run_python(script, project=self.project)
        text = stdout_of(result)
        for line in text.splitlines():
            if line.startswith(marker):
                return json.loads(line[len(marker):])
        errors = stdout_of(result, kinds=("Error", "Warning"))
        raise RuntimeError(f"editor Python failed: {(errors or result.get('result') or text)[:600]}")

    # -- level -------------------------------------------------------------------------
    def find_actor(self, label: str) -> dict[str, str] | None:
        for actor in self.call("SceneTools", "find_actors", name=label, tag="", collision_channels=[]) or []:
            if self.call("ActorTools", "get_label", actor=actor) == label:
                return actor
        return None

    def actor_location(self, actor: dict[str, str]) -> list[float]:
        loc = self.call("ActorTools", "get_actor_transform", actor=actor)["location"]
        return [loc["x"], loc["y"], loc["z"]]

    def actor_bounds(self, actor: dict[str, str]) -> list[list[float]] | None:
        box = self.call("ActorTools", "get_actor_bounds", actor=actor)
        if not box or not box.get("isValid", True):
            return None
        return [[box["min"][a] for a in "xyz"], [box["max"][a] for a in "xyz"]]

    def actor_bounds_center(self, actor: dict[str, str]) -> list[float]:
        box = self.call("ActorTools", "get_actor_bounds", actor=actor)
        if not box or not box.get("isValid", True):
            return self.actor_location(actor)
        return [(box["min"][a] + box["max"][a]) / 2 for a in "xyz"]

    def asset_exists(self, asset_path: str) -> bool:
        script = ("import json, unreal\nprint('CODEX_SEQ ' + json.dumps(unreal.EditorAssetLibrary.does_asset_exist("
                  + json.dumps(asset_path.split(".")[0]) + ")))")
        return bool(self.python(script))

    # -- sequence structure ----------------------------------------------------------------
    def transform_section(self, binding: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, str]:
        """The binding's transform section, created when missing.

        A section added through MCP has no length, so a new one is made unbounded. For a level actor
        pass its current transform (ActorTools.get_actor_transform): every channel's default is set to it,
        otherwise unkeyed channels evaluate to 0 (rotation) and 1 (scale) and snap the actor.
        """
        tracks = self.seq("find_tracks_by_type", binding=binding, track_type={"refPath": TRACK["transform"]})
        track = tracks[0] if tracks else self.seq("add_track_to_binding", binding=binding, track_type={"refPath": TRACK["transform"]})
        sections = self.seq("get_sections", track=track)
        section = sections[0] if sections else self.seq("add_section", track=track)
        if not sections:
            # Unbounded like the sections create_camera makes, so keys on the last frame still evaluate.
            self.seq("set_section_start_bounded", section=section, bounded=False)
            self.seq("set_section_end_bounded", section=section, bounded=False)
        if current:
            loc, rot, scale = current["location"], current["rotation"], current.get("scale") or {"x": 1, "y": 1, "z": 1}
            defaults = {"Location.X": loc["x"], "Location.Y": loc["y"], "Location.Z": loc["z"],
                        "Rotation.X": rot["roll"], "Rotation.Y": rot["pitch"], "Rotation.Z": rot["yaw"],
                        "Scale.X": scale["x"], "Scale.Y": scale["y"], "Scale.Z": scale["z"]}
            for channel, value in defaults.items():
                self.key("set_default_value", section=section, channel_name=channel, value=float(value))
        return section

    def camera_property_sections(self, camera: dict[str, Any]) -> dict[str, dict[str, str]]:
        """{'focal'|'focus'|'aperture': section} on the camera component's existing float tracks."""
        found: dict[str, dict[str, str]] = {}
        for child in self.seq("get_child_possessables", binding=camera) or []:
            for track in self.seq("get_tracks_on_binding", binding=child) or []:
                name = str(self.seq("get_track_display_name", track=track))
                for key, prop in CAMERA_TRACKS.items():
                    if name.replace(" ", "") == prop and key not in found:
                        sections = self.seq("get_sections", track=track)
                        found[key] = sections[0] if sections else self.seq("add_section", track=track)
        return found

    def add_float_key(self, section: dict[str, str], channel: str, frame: int, value: float, interpolation: str = "") -> None:
        self.key("add_key_float", section=section, channel_name=channel, frame=int(frame), value=float(value),
                 interpolation=interpolation)

    def key_transform(self, section: dict[str, str], frame: int, location: list[float] | None,
                      rotation: list[float] | None, interpolation: str) -> None:
        if location is not None:
            for axis, value in zip("XYZ", location):
                self.add_float_key(section, f"Location.{axis}", frame, value, interpolation)
        if rotation is not None:
            pitch, yaw, roll = (list(rotation) + [0.0])[:3]
            for channel, value in (("Rotation.Y", pitch), ("Rotation.Z", yaw), ("Rotation.X", roll)):
                self.add_float_key(section, channel, frame, value, interpolation)

    def bind_camera_cuts(self, sequence_path: str, cuts: list[tuple[str, str]]) -> list[dict[str, Any]]:
        """Bind camera-cut sections (by object name) to cameras (by binding GUID) with stock editor Python."""
        script = r'''
import json, unreal
def _codex():
    seq = unreal.load_asset(__SEQ__)
    by_guid = {unreal.GuidLibrary.conv_guid_to_string(b.get_id()).upper(): b for b in seq.get_bindings()}
    sections = {}
    for track in seq.get_tracks():
        if isinstance(track, unreal.MovieSceneCameraCutTrack):
            for section in track.get_sections():
                sections[section.get_name()] = section
    done = []
    for section_name, guid in json.loads(__CUTS__):
        binding = by_guid.get(guid.replace("-", "").upper())
        section = sections.get(section_name)
        if binding is None or section is None:
            done.append({"section": section_name, "ok": False})
            continue
        section.set_camera_binding_id(unreal.MovieSceneSequenceExtensions.get_binding_id(seq, binding))
        bound = unreal.GuidLibrary.conv_guid_to_string(section.get_camera_binding_id().get_editor_property("guid")).upper()
        done.append({"section": section_name, "ok": bound == guid.replace("-", "").upper()})
    print("CODEX_SEQ " + json.dumps(done))
_codex()
'''
        script = script.replace("__SEQ__", json.dumps(sequence_path.split(".")[0])).replace("__CUTS__", repr(json.dumps(cuts)))
        return self.python(script)
