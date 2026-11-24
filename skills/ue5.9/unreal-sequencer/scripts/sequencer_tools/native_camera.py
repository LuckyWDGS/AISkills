"""UE 5.9 原生后台相机序列：仅新建、延后绑定、结构与曲线回读。"""

from __future__ import annotations

import copy
import json
import math
import ntpath
import re
from pathlib import Path
from uuid import UUID

from .mcp import unwrap_result


SEQUENCE_OWNER = "MovieSceneSequenceExtensions"
SECTION_OWNER = "MovieSceneSectionExtensions"
TRACK_OWNER = "MovieSceneTrackExtensions"
BINDING_OWNER = "MovieSceneBindingExtensions"
TAG_OWNER = "MovieSceneBindingTagExtensions"
EDITOR_OWNER = "LevelSequenceEditorBlueprintLibrary"
TRANSFORM_NAMES = ("Location.X", "Location.Y", "Location.Z", "Rotation.X", "Rotation.Y", "Rotation.Z",
                   "Scale.X", "Scale.Y", "Scale.Z")


def ref_path(value):
    return value.get("refPath") if isinstance(value, dict) else None


def validate_project(project: str) -> str:
    if not isinstance(project, str) or not project.lower().endswith(".uproject"):
        raise ValueError("An absolute .uproject path is required")
    if not (ntpath.isabs(project) or Path(project).is_absolute()):
        raise ValueError("An absolute .uproject path is required")
    return project


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def _integer(value, label):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _vector(value, label):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{label} must contain three numbers")
    return [_number(v, label) for v in value]


def camera_transform(location, target):
    """UE channels store rotation as roll, pitch, yaw, in degrees."""
    direction = [b - a for a, b in zip(location, target)]
    distance_xy = math.hypot(direction[0], direction[1])
    if math.hypot(distance_xy, direction[2]) < 1e-6:
        raise ValueError("A camera cannot look at its own location")
    pitch = math.degrees(math.atan2(direction[2], distance_xy))
    yaw = math.degrees(math.atan2(direction[1], direction[0]))
    return [*location, 0.0, pitch, yaw, 1.0, 1.0, 1.0]


def validate_plan(source: dict) -> dict:
    if not isinstance(source, dict):
        raise ValueError("Plan must be a JSON object")
    allowed = {"sequence", "module_id", "description_zh", "binding_name", "binding_tag", "display_rate",
               "playback", "camera_keys", "fade_keys"}
    if set(source) - allowed:
        raise ValueError(f"Unknown plan fields: {sorted(set(source) - allowed)}")
    plan = copy.deepcopy(source)
    path = plan.get("sequence", "")
    if not isinstance(path, str) or not re.fullmatch(r"/Game/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+", path):
        raise ValueError("sequence must be a new /Game package path without an object suffix")
    for name in ["module_id", "description_zh", "binding_name", "binding_tag"]:
        if not isinstance(plan.get(name), str) or not plan[name].strip():
            raise ValueError(f"{name} is required")
    if not re.search(r"[\u3400-\u9fff]", plan["description_zh"]):
        raise ValueError("description_zh must explain the module in Chinese")
    rate = plan.get("display_rate")
    if not isinstance(rate, list) or len(rate) != 2 or any(_integer(v, "display_rate") <= 0 for v in rate):
        raise ValueError("display_rate must be a positive rational [numerator, denominator]")
    playback = plan.get("playback")
    if not isinstance(playback, list) or len(playback) != 2:
        raise ValueError("playback must be [inclusive_start, exclusive_end]")
    start, end = [_integer(v, "playback") for v in playback]
    if end <= start or end - start > 100000:
        raise ValueError("playback must be nonempty and at most 100000 display frames")
    keys = plan.get("camera_keys")
    if not isinstance(keys, list) or len(keys) < 2:
        raise ValueError("camera_keys needs at least two poses")
    previous = start - 1
    for key in keys:
        if not isinstance(key, dict) or set(key) != {"frame", "location", "look_at"}:
            raise ValueError("Each camera key needs frame, location and look_at")
        frame = _integer(key["frame"], "camera frame")
        if not start <= frame < end or frame <= previous:
            raise ValueError("Camera frames must increase within the half-open playback range")
        previous = frame
        key["location"] = _vector(key["location"], "location")
        key["look_at"] = _vector(key["look_at"], "look_at")
        key["transform"] = camera_transform(key["location"], key["look_at"])
    if keys[0]["frame"] != start or keys[-1]["frame"] != end - 1:
        raise ValueError("Camera poses must include the first and last visible frame")
    # Avoid an unintended 360-degree turn at the +/-180-degree boundary.
    for previous_key, key in zip(keys, keys[1:]):
        yaw = key["transform"][5]
        prior_yaw = previous_key["transform"][5]
        key["transform"][5] = prior_yaw + (yaw - prior_yaw + 180.0) % 360.0 - 180.0
    fades = plan.get("fade_keys", [])
    if not isinstance(fades, list):
        raise ValueError("fade_keys must be an array")
    previous = start - 1
    for key in fades:
        if not isinstance(key, dict) or set(key) != {"frame", "value"}:
            raise ValueError("Each fade key needs frame and value")
        frame = _integer(key["frame"], "fade frame")
        value = _number(key["value"], "fade value")
        if not start <= frame < end or frame <= previous or not 0 <= value <= 1:
            raise ValueError("Fade frames must increase in range and values must be 0..1")
        previous = frame
    plan["fade_keys"] = fades
    return plan


def validate_binding(binding, sequence):
    if not isinstance(binding, dict) or binding.get("sequence") != sequence:
        raise RuntimeError("Invalid or foreign sequence binding; stopping without dependent writes")
    try:
        guid = UUID(binding["bindingId"])
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError("Invalid sequence binding GUID") from exc
    if guid.int == 0:
        raise RuntimeError("Zero sequence binding GUID; creation did not succeed")
    return binding


def same_root_binding(left, right):
    """Root-local (0) and root-resolved (-1) IDs differ in representation only.

    Preserve both returned descriptors; this predicate must not rewrite an ID
    passed to an API. Nested-sequence identities are intentionally rejected.
    """
    try:
        return (UUID(left["guid"]) == UUID(right["guid"]) and UUID(left["guid"]).int != 0
                and left["sequenceId"] == right["sequenceId"] == 0
                and left["resolveParentIndex"] in (-1, 0) and right["resolveParentIndex"] in (-1, 0))
    except (TypeError, ValueError, KeyError, AttributeError):
        return False


def verify_linear_samples(values, keys, start, end, label):
    """Check the whole visible curve, including between-key interpolation."""
    if not isinstance(values, list) or len(values) != end - start or not keys:
        raise RuntimeError(f"Curve sample count mismatch for {label}")
    segment = 0
    for frame, actual in zip(range(start, end), values):
        while segment + 1 < len(keys) and frame > keys[segment + 1][0]:
            segment += 1
        if frame <= keys[0][0]:
            expected = keys[0][1]
        elif segment + 1 == len(keys):
            expected = keys[-1][1]
        else:
            left, right = keys[segment:segment + 2]
            fraction = (frame - left[0]) / (right[0] - left[0])
            expected = left[1] + fraction * (right[1] - left[1])
        if (isinstance(actual, bool) or not isinstance(actual, (int, float))
                or not math.isfinite(actual) or not math.isclose(actual, expected, abs_tol=1e-4)):
            raise RuntimeError(f"Linear curve readback mismatch for {label} at {frame}: {actual!r} != {expected}")


class NativeCameraBuilder:
    """Create-only builder. No world/viewport evaluation, UI fallback or write retry."""

    def __init__(self, client):
        self.client = client
        self.records = []
        self.creation_attempted = False
        self.created = None

    def call(self, owner, tool, **args):
        try:
            result = unwrap_result(self.client.call_resolved_tool(owner, tool, args))
        except Exception as exc:
            self.records.append({"toolset": owner, "tool": tool, "arguments": args, "error": str(exc)})
            raise
        self.records.append({"toolset": owner, "tool": tool, "arguments": args, "result": result})
        return result

    def require_tools(self, fades):
        tools = {
            EDITOR_OWNER: ["CreateLevelSequence", "GetCurrentLevelSequence"],
            SEQUENCE_OWNER: ["AddEmptyBinding", "AddTrack", "SetDisplayRate", "SetPlaybackRange", "GetBindings",
                             "GetDisplayRate", "GetPlaybackStart", "GetPlaybackEnd", "GetBindingID", "FindBindingsByTag"],
            BINDING_OWNER: ["AddTrack", "SetDisplayName", "GetTracks"],
            TAG_OWNER: ["TagBinding", "GetBindingTags"],
            TRACK_OWNER: ["AddSection", "GetSections", "SetDisplayName"],
            SECTION_OWNER: ["SetRange", "SetCompletionMode", "GetCompletionMode", "SetCameraCutBinding",
                            "GetNumericChannels", "SetDoubleDefault", "SetFloatDefault", "AddDoubleKey",
                            "AddFloatKey", "GetChannelKeys", "EvaluateChannelKeys", "GetStartFrame", "GetEndFrame"],
            "AssetToolset": ["Exists", "IsDirty", "UpdateMetadataTags", "SaveAsset"],
            "ObjectToolset": ["ListProperties", "GetProperties"],
            "EditorAppToolset": ["IsPIERunning"],
        }
        for owner, names in tools.items():
            for name in names:
                if not self.client.find_tool(owner, name):
                    raise RuntimeError(f"Required native tool missing: {owner}.{name}; no asset created")

    def section(self, track, plan):
        section = self.call(TRACK_OWNER, "AddSection", track=track)
        if not ref_path(section):
            raise RuntimeError("Track section creation returned no reference")
        self.call(SECTION_OWNER, "SetRange", section=section,
                  startFrame=plan["playback"][0], endFrame=plan["playback"][1])
        self.call(SECTION_OWNER, "SetCompletionMode", section=section, inCompletionMode="RestoreState")
        return section

    def key(self, channel, frame, value):
        self.call(SECTION_OWNER, "Add" + channel["channelType"] + "Key", channel=channel,
                  inTime={"value": frame}, newValue=value, timeUnit="DisplayRate", inInterpolation="Linear")

    def build(self, plan: dict, *, save=False):
        # Validate before querying the editor; callers cannot smuggle compiled fields.
        plan = validate_plan(plan)
        identity = self.client.initialize_result or {}
        version = identity.get("_meta", {}).get("com.epicgames.unrealengine/instance", {}).get("engineVersion", "")
        if not version.startswith("5.9."):
            raise RuntimeError(f"This builder requires a freshly verified UE 5.9 editor, got {version!r}")
        validate_project(self.client.expected_project)
        self.require_tools(bool(plan["fade_keys"]))
        if self.call("EditorAppToolset", "IsPIERunning") is not False:
            raise RuntimeError("PIE/Simulate state is active or unknown; no asset created")
        before = self.call(EDITOR_OWNER, "GetCurrentLevelSequence")
        if before not in (None, "None", ""):
            raise RuntimeError("An editor timeline is already open; preserve it and use a scoped workflow")
        exists = self.call("AssetToolset", "Exists", path=plan["sequence"])
        if exists is not False:
            raise RuntimeError("Target exists or its absence is unproven; this builder never replaces assets")
        package, name = plan["sequence"].rsplit("/", 1)
        self.creation_attempted = True
        sequence = self.call(EDITOR_OWNER, "CreateLevelSequence", packagePath=package, assetName=name)
        self.created = sequence
        if ref_path(sequence) != plan["sequence"] + "." + name:
            raise RuntimeError("Unexpected created asset reference; inspect partial work before continuing")
        self.call("AssetToolset", "UpdateMetadataTags", assetPath=plan["sequence"], setTags=[
            {"key": "Codex.ModuleId", "value": plan["module_id"]},
            {"key": "Description", "value": plan["description_zh"]},
            {"key": "Codex.BindingPolicy", "value": "运行前按BindingTag绑定真实相机；完成/停止/跳过均恢复原视角与输入"},
        ])
        start, end = plan["playback"]
        self.call(SEQUENCE_OWNER, "SetDisplayRate", sequence=sequence,
                  displayRate={"numerator": plan["display_rate"][0], "denominator": plan["display_rate"][1]})
        self.call(SEQUENCE_OWNER, "SetPlaybackRange", sequence=sequence, startFrame=start, endFrame=end)
        binding = validate_binding(self.call(SEQUENCE_OWNER, "AddEmptyBinding", sequence=sequence,
                                            name=plan["binding_name"]), sequence)
        self.call(BINDING_OWNER, "SetDisplayName", inBinding=binding, inDisplayName="开场相机｜运行时绑定")
        self.call(TAG_OWNER, "TagBinding", binding=binding, tagName=plan["binding_tag"])
        transform_track = self.call(BINDING_OWNER, "AddTrack", inBinding=binding,
                                    trackType={"refPath": "/Script/MovieSceneTracks.MovieScene3DTransformTrack"})
        self.call(TRACK_OWNER, "SetDisplayName", track=transform_track, inName="镜头推进｜位移与朝向")
        transform_section = self.section(transform_track, plan)
        channels = self.call(SECTION_OWNER, "GetNumericChannels", section=transform_section)
        indexed = {c["channelName"]: c for c in channels}
        if not set(TRANSFORM_NAMES).issubset(indexed):
            raise RuntimeError(f"Transform channel contract changed: {sorted(indexed)}; partial work retained")
        defaults = dict(zip(TRANSFORM_NAMES, plan["camera_keys"][0]["transform"]))
        defaults["Weight"] = 1.0
        for channel in channels:
            name = channel["channelName"]
            if name not in defaults:
                raise RuntimeError(f"Unexpected transform channel {name!r}; inspect before authoring")
            self.call(SECTION_OWNER, "Set" + channel["channelType"] + "Default", channel=channel,
                      inDefaultValue=defaults[name])
        for key in plan["camera_keys"]:
            for name, value in zip(TRANSFORM_NAMES[:6], key["transform"][:6]):
                self.key(indexed[name], key["frame"], value)
        cut_track = self.call(SEQUENCE_OWNER, "AddTrack", sequence=sequence,
                              trackType={"refPath": "/Script/MovieSceneTracks.MovieSceneCameraCutTrack"})
        self.call(TRACK_OWNER, "SetDisplayName", track=cut_track, inName="开场镜头｜覆盖全部可见帧")
        cut_section = self.section(cut_track, plan)
        self.call(SECTION_OWNER, "SetCameraCutBinding", section=cut_section, cameraBinding=binding)
        fade_section = None
        if plan["fade_keys"]:
            fade_track = self.call(SEQUENCE_OWNER, "AddTrack", sequence=sequence,
                                   trackType={"refPath": "/Script/MovieSceneTracks.MovieSceneFadeTrack"})
            self.call(TRACK_OWNER, "SetDisplayName", track=fade_track, inName="开场淡入｜结束恢复")
            fade_section = self.section(fade_track, plan)
            fade_channels = self.call(SECTION_OWNER, "GetNumericChannels", section=fade_section)
            if len(fade_channels) != 1 or fade_channels[0]["channelType"] != "Float":
                raise RuntimeError("Unexpected Fade channel contract; partial work retained")
            self.call(SECTION_OWNER, "SetFloatDefault", channel=fade_channels[0], inDefaultValue=0.0)
            for key in plan["fade_keys"]:
                self.key(fade_channels[0], key["frame"], key["value"])
        report = self.verify(plan, sequence, binding, transform_section, cut_section, fade_section)
        after = self.call(EDITOR_OWNER, "GetCurrentLevelSequence")
        if after != before:
            raise RuntimeError("Timeline state changed; preserving state and refusing to claim background success")
        if save:
            self.call("AssetToolset", "SaveAsset", assetPath=plan["sequence"])
        dirty = self.call("AssetToolset", "IsDirty", assetPath=plan["sequence"])
        if not isinstance(dirty, bool) or (save and dirty):
            raise RuntimeError("Candidate save state could not be verified")
        report.update({"dirty": dirty, "saved": bool(save and dirty is False), "timeline_before": before,
                       "timeline_after": after, "runtime": "not_run", "visual": "not_run"})
        return report

    def verify(self, plan, sequence, binding, transform_section, cut_section, fade_section):
        bindings = self.call(SEQUENCE_OWNER, "GetBindings", sequence=sequence)
        if len(bindings) != 1 or bindings[0] != binding:
            raise RuntimeError("Created binding inventory does not match the intended camera")
        rate = self.call(SEQUENCE_OWNER, "GetDisplayRate", sequence=sequence)
        playback = [self.call(SEQUENCE_OWNER, "GetPlaybackStart", sequence=sequence),
                    self.call(SEQUENCE_OWNER, "GetPlaybackEnd", sequence=sequence)]
        if rate != dict(zip(["numerator", "denominator"], plan["display_rate"])) or playback != plan["playback"]:
            raise RuntimeError("Frame-rate or playback-range readback mismatch")
        tag_ids = self.call(SEQUENCE_OWNER, "FindBindingsByTag", sequence=sequence, tagName=plan["binding_tag"])
        binding_id = self.call(SEQUENCE_OWNER, "GetBindingID", sequence=sequence, inBinding=binding)
        if len(tag_ids) != 1 or not same_root_binding(tag_ids[0], binding_id):
            raise RuntimeError("Binding tag did not resolve to exactly the created camera binding")
        cut_properties = self.call("ObjectToolset", "ListProperties", instance=cut_section,
                                   nameFilter="camera.*binding", maxDepth=0)
        property_names = {path.split(".", 1)[0].split(" ", 1)[0] for path in cut_properties}
        if len(property_names) != 1:
            raise RuntimeError(f"Camera cut binding property was not discovered: {cut_properties}")
        property_name = next(iter(property_names))
        cut_values = self.call("ObjectToolset", "GetProperties", instance=cut_section, properties=[property_name])
        if isinstance(cut_values, str):
            cut_values = json.loads(cut_values)
        camera_id = cut_values[property_name]
        if not same_root_binding(camera_id, binding_id):
            raise RuntimeError(f"Camera-cut binding readback mismatch: {camera_id}")
        sections = [transform_section, cut_section] + ([fade_section] if fade_section else [])
        for section in sections:
            bounds = [self.call(SECTION_OWNER, "GetStartFrame", section=section),
                      self.call(SECTION_OWNER, "GetEndFrame", section=section)]
            completion = self.call(SECTION_OWNER, "GetCompletionMode", section=section)
            if bounds != playback or completion != "RestoreState":
                raise RuntimeError("Section bounds/completion mode readback mismatch")
        samples = {}
        for i, name in enumerate(TRANSFORM_NAMES[:6]):
            values = self.call(SECTION_OWNER, "EvaluateChannelKeys", section=transform_section,
                               channelName=name, startFrame=playback[0], endFrame=playback[1])
            verify_linear_samples(values, [(key["frame"], key["transform"][i]) for key in plan["camera_keys"]],
                                  *playback, name)
            samples[name] = values
        fade_values = None
        if fade_section:
            names = self.call(SECTION_OWNER, "GetNumericChannels", section=fade_section)
            if len(names) != 1:
                raise RuntimeError("Fade readback channel count mismatch")
            fade_values = self.call(SECTION_OWNER, "EvaluateChannelKeys", section=fade_section,
                                    channelName=names[0]["channelName"], startFrame=playback[0], endFrame=playback[1])
            verify_linear_samples(fade_values, [(key["frame"], key["value"]) for key in plan["fade_keys"]],
                                  *playback, "Fade")
        return {"sequence": sequence, "binding": binding, "binding_id": binding_id,
                "tag_binding_id": tag_ids[0], "cut_binding_id": camera_id,
                "binding_tag": plan["binding_tag"], "display_rate": rate, "playback": playback,
                "transform_section": transform_section, "cut_section": cut_section,
                "fade_section": fade_section, "camera_samples": samples, "fade_samples": fade_values,
                "verification": "structure_and_authored_curve_data_only"}
