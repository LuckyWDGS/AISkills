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
- set_camera_cut_binding fails inside the tool ("call() takes at most 0 arguments"); use
  get_binding_id + ObjectTools for complete camera-cut binding IDs (bind_camera_cuts).
- SceneTools.find_actors(name=...) is a substring match on actor labels; filter on the exact label.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from .mcp import connect, marker_json, run_python, unwrap_result
from .background_compat import spawnable_script

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


def valid_binding(binding: Any, sequence: dict[str, str] | None = None) -> dict[str, Any]:
    """Reject the zero/None proxy some official tools return without an error."""
    try:
        guid = UUID(str(binding["bindingId"]))
        ref = binding["sequence"]["refPath"]
        if not guid.int or not isinstance(ref, str) or not ref or ref == "None":
            raise ValueError()
        if sequence is not None and ref.split(".")[0] != sequence["refPath"].split(".")[0]:
            raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError):
        raise RuntimeError("Invalid Sequencer binding: expected a nonzero GUID and the target sequence reference") from None
    return {**binding, "bindingId": str(guid).upper()}


def binding_id_data(value: Any) -> dict[str, Any]:
    """Keep the complete official ID, including its sequence resolution space."""
    try:
        guid = UUID(str(value["guid"]))
        if any(type(value[key]) is not int for key in ("sequenceId", "resolveParentIndex")):
            raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError):
        raise RuntimeError("Invalid camera binding ID: GUID, sequenceId and resolveParentIndex are required") from None
    return {**value, "guid": str(guid).upper()}


class Editor:
    """One MCP session plus editor-Python calls; every tool call is recorded in self.calls."""

    def __init__(self, project: str | None = None):
        self.project = project or os.environ.get("UE_MCP_PROJECT")
        self.client = connect(project=self.project)
        self.calls: list[dict[str, Any]] = []

    def close(self) -> None:
        self.client.close()

    def call(self, toolset: str, tool: str, **args: Any) -> Any:
        if toolset == SEQ_TOOLS and "binding" in args:
            valid_binding(args["binding"])
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

    def python(self, script: str, marker: str = "CODEX_SEQ ", *, gap: str) -> Any:
        """Run stock editor Python; the script prints one marker line with a JSON payload."""
        if not gap.strip():
            raise ValueError("Remote Python requires an identified MCP gap")
        record = {"transport": "Epic Python Remote Execution", "gap": gap}
        self.calls.append(record)
        try:
            result = run_python(script, project=self.project)
        except Exception as exc:
            record["error"] = str(exc)
            raise
        record.update({"engine_version": result.get("node", {}).get("engine_version"),
                       "success": result.get("success"),
                       "warnings": [row.get("output", "") for row in result.get("output", []) if row.get("type") == "Warning"],
                       "errors": [row.get("output", "") for row in result.get("output", []) if row.get("type") == "Error"]})
        try:
            record["result"] = marker_json(result, marker)
        except (RuntimeError, ValueError) as exc:
            record["error"] = str(exc)
            raise
        return record["result"]

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
        result = self.call("AssetTools", "exists", path=asset_path.split(".")[0])
        if not isinstance(result, bool):
            raise RuntimeError("Asset existence is unknown; refusing creation or replacement")
        return result

    def save_asset(self, asset_path: str) -> bool:
        path = asset_path.split(".")[0]
        if self.call("AssetTools", "save_assets", asset_paths=[path]) is not True:
            raise RuntimeError(f"save_assets failed for {path}")
        if self.call("AssetTools", "is_dirty", asset_path=path) is not False:
            raise RuntimeError(f"{path} is still dirty or save state is unknown")
        return True

    def backup_asset(self, source: str, target: str) -> None:
        if not target.startswith("/Game/") or "." in target or ":" in target or target == source:
            raise RuntimeError("backup-path must be a distinct /Game/... package path")
        if self.asset_exists(target):
            raise RuntimeError(f"backup target already exists: {target}")
        if self.call("AssetTools", "duplicate", path=source, new_path=target) is not True or not self.asset_exists(target):
            raise RuntimeError("backup duplication failed; source not replaced")
        self.save_asset(target)

    def sequence_state(self, *, allow_editor_ui: bool = False) -> dict[str, Any]:
        """UI-dependent helpers must be explicitly selected, before creating any asset."""
        if not allow_editor_ui:
            raise RuntimeError("This helper requires opening Sequencer. Background policy refused before writing; "
                               "use explicit-sequence MCP edits or a verified public background API. "
                               "--allow-editor-ui is only for an explicitly requested UI workflow.")
        root = self.seq("get_current_sequence")
        if not root:
            return {"sequence": None}
        focused = self.seq("get_focused_sequence")
        if focused and focused != root:
            raise RuntimeError("A sub-sequence is focused; this helper cannot restore its hierarchy safely.")
        if self.seq("is_playing") is not False:
            raise RuntimeError("An existing sequence is playing or playback state is unknown; preserve the user session.")
        return {"sequence": root, "frame": self.seq("get_playhead_frame"),
                "speed": self.seq("get_playback_speed"), "loop": self.seq("get_loop_mode")}

    @contextmanager
    def sequence_session(self, sequence: dict, state: dict, *, keep_open: bool = False):
        """Restore only the UI session this operation owns, including when opening times out."""
        succeeded = False
        try:
            self.seq("open_sequence", sequence=sequence)
            yield
            succeeded = True
        finally:
            if not (keep_open and succeeded):
                current = self.seq("get_current_sequence")
                if current == sequence:
                    previous = state["sequence"]
                    if previous != sequence:
                        self.seq("close_sequence")
                        if previous:
                            self.seq("open_sequence", sequence=previous)
                    if previous:
                        self.seq("set_playhead_frame", frame=state["frame"])
                        self.seq("set_playback_speed", speed=state["speed"])
                        self.seq("set_loop_mode", loop=state["loop"])
                        self.seq("force_evaluate")
                # If the user switched sequences during the operation, leave their new session alone.

    # -- sequence structure ----------------------------------------------------------------
    def add_spawnable_from_class(self, sequence: dict[str, str], actor_class_path: str) -> dict[str, Any]:
        """MCP first; fill its verified active-Sequencer gap without opening a timeline."""
        def ids():
            rows = self.seq("get_bindings", sequence=sequence)
            if not isinstance(rows, list):
                raise RuntimeError("Binding inventory is unknown; inspect before another write")
            keys = [valid_binding(row, sequence)["bindingId"] for row in rows]
            if len(set(keys)) != len(keys):
                raise RuntimeError("Binding inventory contains duplicate IDs; inspect before another write")
            return set(keys)

        before = ids()
        # Exceptions/timeouts are ambiguous: never repeat the write through another route.
        native = self.seq("add_spawnable_from_class", sequence=sequence, actor_class_path=actor_class_path)
        try:
            binding = valid_binding(native, sequence)
        except RuntimeError:
            if ids() != before:
                raise RuntimeError("MCP returned an invalid binding after changing the inventory; inspect partial work") from None
            try:
                known_empty = isinstance(native, dict) and native.get("sequence") == "None" and UUID(str(native.get("bindingId"))).int == 0
            except (TypeError, ValueError, AttributeError):
                known_empty = False
            if not known_empty:
                raise RuntimeError("MCP returned an unrecognized invalid proxy; no fallback creation attempted") from None
            focused = self.seq("get_focused_sequence")
            if isinstance(focused, dict) and focused.get("refPath", "").split(".")[0] == sequence["refPath"].split(".")[0]:
                raise RuntimeError("MCP returned an invalid binding for the focused sequence; background gap is unproven") from None
            if focused not in (None, "None") and not (isinstance(focused, dict) and focused.get("refPath")):
                raise RuntimeError("Focused sequence is unknown; refusing an unproven fallback") from None
            script = spawnable_script(sequence["refPath"], actor_class_path)
            result = self.python(script, gap=(
                "UE 5.8.4 MCP add_spawnable_from_class calls LevelSequenceEditorSubsystem and requires the target "
                "timeline open; invalid proxy and unchanged inventory confirmed. The deprecated public sequence "
                "extension is permitted only on the audited engine build, with its warning retained; no UI is opened."))
            binding = valid_binding(result.get("binding") if isinstance(result, dict) else None, sequence)
        after = ids()
        if binding["bindingId"] in before or after != before | {binding["bindingId"]}:
            raise RuntimeError("Spawnable binding readback disagrees with creation; inspect partial work before retrying")
        return binding

    def transform_section(self, binding: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, str]:
        """The binding's transform section, created when missing.

        Explicitly make a new transform section unbounded; defaults vary by section class. For a level actor
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

    def bind_camera_cuts(self, sequence_path: str, cuts: list[tuple[dict, str]]) -> list[dict[str, Any]]:
        """[CINE.CameraCuts] 官方 MCP 完整绑定与回读；任何不确定结果停止后续写入。"""
        if not cuts:
            return []
        sequence = object_ref(sequence_path)
        bindings = self.seq("get_bindings", sequence=sequence)
        if not isinstance(bindings, list):
            raise RuntimeError("Binding inventory is unknown; refusing camera-cut writes")
        by_guid = {}
        for binding in bindings:
            binding = valid_binding(binding, sequence)
            if binding["bindingId"] in by_guid:
                raise RuntimeError("Binding inventory contains duplicate IDs; refusing camera-cut writes")
            by_guid[binding["bindingId"]] = binding
        # Preflight all targets before the first write. Names alone cannot identify a section.
        pending, seen = [], set()
        for section, guid in cuts:
            path = section.get("refPath", "") if isinstance(section, dict) else ""
            if not path.startswith(sequence["refPath"] + ":") or path in seen:
                raise RuntimeError("Camera-cut section must be unique and belong to the target sequence")
            seen.add(path)
            binding = valid_binding({"bindingId": guid, "sequence": sequence}, sequence)
            if binding["bindingId"] not in by_guid:
                raise RuntimeError("Camera-cut binding is absent from the target sequence")
            expected = binding_id_data(self.seq("get_binding_id", sequence=sequence, binding=by_guid[binding["bindingId"]]))
            if expected["guid"] != binding["bindingId"]:
                raise RuntimeError("get_binding_id returned a different GUID; refusing camera-cut writes")
            pending.append((section, expected, self.camera_binding_id(section)))
        done = []
        for section, expected, before in pending:
            changed = before != expected
            if changed:
                # Use the reflected EditAnywhere property, with all official struct fields.
                result = self.call("ObjectTools", "set_properties", instance=section,
                                   values=json.dumps({"cameraBindingId": expected}))
                actual = self.camera_binding_id(section)
                if result is not True or actual != expected:
                    raise RuntimeError(f"Camera-cut binding readback failed for {section['refPath']}: {actual}; inspect before retrying")
            else:
                actual = before
            done.append({"section": short(section), "ok": True, "binding_id": actual, "changed": changed})
        return done

    def camera_binding_id(self, section: dict[str, str]) -> dict[str, Any]:
        """Read an editable cut binding through official MCP; zero GUID is an unbound cut."""
        data = self.call("ObjectTools", "get_properties", instance=section, properties=["cameraBindingId"])
        if isinstance(data, str):
            data = json.loads(data)
        if not isinstance(data, dict) or "cameraBindingId" not in data:
            raise RuntimeError("Camera-cut binding property is unavailable; inspect the current official schema")
        return binding_id_data(data["cameraBindingId"])
