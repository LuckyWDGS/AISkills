"""Shot plans: normalization, validation and camera math. Pure Python, no editor needed.

A plan (JSON) describes one Level Sequence:

    {"sequence": {"path": "/Game/Cinematics/LS_Intro", "fps": 30, "seconds": 8},
     "cameras": [{"id": "Wide", "label": "建立镜头", "aperture": 2.8, "interpolation": "cubic",
                  "keys": [{"time": 0, "location": [-800, 0, 300], "look_at": "Hero", "focal": 24},
                           {"time": 4, "location": [-500, 200, 250], "look_at": [0, 0, 120], "focal": 35}]}],
     "shots": [{"camera": "Wide", "start": 0, "end": 4}, {"camera": "Close", "start": 4, "end": 8}],
     "actors": [{"actor": "Hero", "keys": [{"time": 0, "offset": [0, 0, 0]}, {"time": 2, "offset": [300, 0, 0]}],
                 "animation": {"asset": "/Game/Anims/AS_Wave", "start": 1, "end": 3}}],
     "fade": [{"time": 0, "value": 1}, {"time": 0.5, "value": 0}]}

Times are seconds ("time", "start", "end") or display-rate frames ("frame", "start_frame",
"end_frame"); everything is normalized to display-rate frames, which is what the Sequencer MCP
tools take. Camera rotation is explicit ("rotation": [pitch, yaw, roll]) or aimed with "look_at"
(an actor label or a world point); a label aims at the actor's bounds centre, or at its pivot with
"aim": "pivot" on the camera. "focus": "auto" focuses on the look-at point.
"""

from __future__ import annotations

import copy
import math
from fractions import Fraction
from typing import Any

INTERPOLATIONS = {"cubic", "linear", "constant", "break", ""}
DEFAULT_FPS = 30


def finding(severity: str, rule: str, message: str, **detail: Any) -> dict[str, Any]:
    return {"severity": severity, "rule": rule, "message": message, **detail}


def frame_rate(value: Any = DEFAULT_FPS) -> Fraction:
    """Exact positive rate: integer/decimal, '30000/1001', or numerator/denominator object.

    Decimal 29.97 means exactly 2997/100; use 30000/1001 for the NTSC rate.
    """
    if isinstance(value, bool):
        raise ValueError("fps must be a positive frame rate")
    if isinstance(value, dict):
        n, d = value.get("numerator"), value.get("denominator")
        if type(n) is not int or type(d) is not int or n <= 0 or d <= 0:
            raise ValueError("fps numerator and denominator must be positive integers")
        rate = Fraction(n, d)
    else:
        rate = Fraction(str(value))
    if rate <= 0 or rate.numerator > 2147483647 or rate.denominator > 2147483647:
        raise ValueError("fps must be positive and fit UE's int32 numerator/denominator")
    return rate


def to_frame(item: dict[str, Any], fps: Fraction, seconds_key: str, frame_key: str) -> int | None:
    if item.get(frame_key) is not None:
        return int(item[frame_key])
    if item.get(seconds_key) is not None:
        return round(Fraction(str(item[seconds_key])) * fps)
    return None


def look_at_rotation(origin: list[float], target: list[float]) -> list[float]:
    """[pitch, yaw, roll] in degrees that points an actor's +X axis from origin at target."""
    dx, dy, dz = (target[i] - origin[i] for i in range(3))
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return [round(pitch, 4), round(yaw, 4), 0.0]


def unwrap_yaws(values: list[float]) -> list[float]:
    """Keep consecutive yaw keys within 180 degrees so cubic keys never spin the long way round."""
    out: list[float] = []
    for value in values:
        if out:
            while value - out[-1] > 180:
                value -= 360
            while value - out[-1] < -180:
                value += 360
        out.append(value)
    return out


def normalize(plan: dict[str, Any]) -> dict[str, Any]:
    """Deep copy with every time converted to frames ("frame", "start_frame", "end_frame")."""
    plan = copy.deepcopy(plan)
    seq = plan.setdefault("sequence", {})
    fps = frame_rate(seq.get("fps", DEFAULT_FPS))
    seq["fps"] = fps.numerator if fps.denominator == 1 else {"numerator": fps.numerator, "denominator": fps.denominator}
    start = to_frame(seq, fps, "start", "start_frame") or 0
    end = to_frame(seq, fps, "seconds", "end_frame")
    if end is None and seq.get("seconds") is None:
        ends = [to_frame(s, fps, "end", "end_frame") for s in plan.get("shots", [])]
        end = max([e for e in ends if e is not None], default=None)
    seq["start_frame"], seq["end_frame"] = start, end
    for camera in plan.get("cameras", []):
        for key in camera.get("keys", []):
            key["frame"] = to_frame(key, fps, "time", "frame")
    for shot in plan.get("shots", []):
        shot["start_frame"] = to_frame(shot, fps, "start", "start_frame")
        shot["end_frame"] = to_frame(shot, fps, "end", "end_frame")
    for actor in plan.get("actors", []):
        for key in actor.get("keys", []):
            key["frame"] = to_frame(key, fps, "time", "frame")
        anim = actor.get("animation")
        if anim:
            anim["start_frame"] = to_frame(anim, fps, "start", "start_frame") or 0
            anim["end_frame"] = to_frame(anim, fps, "end", "end_frame")
    for key in plan.get("fade", []):
        key["frame"] = to_frame(key, fps, "time", "frame")
    return plan


def validate(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Problems in a normalized plan; any "error" blocks execution."""
    out: list[dict[str, Any]] = []
    seq = plan.get("sequence", {})
    path = str(seq.get("path") or "")
    if not path.startswith("/Game/") or path.endswith("/"):
        out.append(finding("error", "sequence_path", f"sequence.path must be a /Game/... asset path, got {path!r}"))
    start, end = seq.get("start_frame"), seq.get("end_frame")
    if end is None or end <= (start or 0):
        out.append(finding("error", "sequence_range", "sequence needs seconds/end_frame (or shots) after its start"))
        end = None
    cameras = {c.get("id"): c for c in plan.get("cameras", [])}
    if None in cameras or len(cameras) != len(plan.get("cameras", [])):
        out.append(finding("error", "camera_id", "every camera needs a unique id"))
    for cid, camera in cameras.items():
        keys = camera.get("keys", [])
        if not keys:
            out.append(finding("error", "camera_keys", f"camera {cid} has no keys"))
        frames = [k.get("frame") for k in keys]
        if any(f is None for f in frames):
            out.append(finding("error", "key_time", f"camera {cid} has a key without time/frame"))
        elif frames != sorted(set(frames)):
            out.append(finding("error", "key_order", f"camera {cid} keys must be in increasing time without duplicates"))
        if camera.get("aim", "bounds") not in ("bounds", "pivot"):
            out.append(finding("error", "aim", f"camera {cid}: aim must be 'bounds' or 'pivot'"))
        if camera.get("interpolation", "cubic") not in INTERPOLATIONS:
            out.append(finding("error", "interpolation", f"camera {cid}: interpolation must be one of {sorted(INTERPOLATIONS)}"))
        for key in keys:
            if "location" in key and len(key["location"]) != 3:
                out.append(finding("error", "location", f"camera {cid} key {key.get('frame')}: location needs 3 numbers"))
            if "rotation" in key and "look_at" in key:
                out.append(finding("error", "rotation", f"camera {cid} key {key.get('frame')}: give rotation or look_at, not both"))
            if key.get("focus") == "auto" and "look_at" not in key:
                out.append(finding("error", "focus", f"camera {cid} key {key.get('frame')}: focus 'auto' needs look_at"))
            if end is not None and key.get("frame") is not None and not (start or 0) <= key["frame"] <= end:
                out.append(finding("warning", "key_outside_range", f"camera {cid} key at frame {key['frame']} is outside the playback range"))
        if "keys" in camera and "location" not in (keys[0] if keys else {}):
            out.append(finding("warning", "camera_start", f"camera {cid}: first key has no location; the camera starts where it spawns"))
    shots = sorted(plan.get("shots", []), key=lambda s: (s.get("start_frame") is None, s.get("start_frame") or 0))
    if not shots:
        out.append(finding("warning", "no_shots", "no shots: the sequence will have no camera cuts"))
    previous_end = start or 0
    for shot in shots:
        cid, s, e = shot.get("camera"), shot.get("start_frame"), shot.get("end_frame")
        if cid not in cameras:
            out.append(finding("error", "shot_camera", f"shot uses unknown camera {cid!r}"))
        if s is None or e is None or e <= s:
            out.append(finding("error", "shot_range", f"shot {cid} needs start < end"))
            continue
        if s > previous_end:
            out.append(finding("warning", "cut_gap", f"no camera between frames {previous_end} and {s}"))
        elif s < previous_end:
            out.append(finding("error", "cut_overlap", f"shot {cid} starts at {s} before the previous shot ends at {previous_end}"))
        previous_end = e
    if shots and end is not None and previous_end < end:
        out.append(finding("warning", "cut_gap", f"no camera between frames {previous_end} and {end}"))
    used = {s.get("camera") for s in shots}
    for cid in cameras:
        if cid not in used:
            out.append(finding("warning", "unused_camera", f"camera {cid} is never cut to"))
    for actor in plan.get("actors", []):
        if not actor.get("actor"):
            out.append(finding("error", "actor_label", "actor entries need the actor's label"))
        for key in actor.get("keys", []):
            if key.get("frame") is None:
                out.append(finding("error", "key_time", f"actor {actor.get('actor')} has a key without time/frame"))
            if "location" in key and "offset" in key:
                out.append(finding("error", "location", f"actor {actor.get('actor')} key {key.get('frame')}: give location or offset, not both"))
        anim = actor.get("animation")
        if anim and (not str(anim.get("asset", "")).startswith("/Game/") or anim.get("end_frame") is None):
            out.append(finding("error", "animation", f"actor {actor.get('actor')}: animation needs a /Game asset and an end"))
    return out


def resolve_camera_keys(camera: dict[str, Any], positions: dict[str, list[float]]) -> list[dict[str, Any]]:
    """Camera keys with rotation and focus filled in from look_at targets (labels resolved via positions)."""
    keys = []
    last_location = None
    for index, key in enumerate(camera.get("keys", [])):
        key = dict(key)
        if index == 0:
            for prop in ("focal", "focus", "aperture"):
                if camera.get(prop) is not None:
                    key.setdefault(prop, camera[prop])
        location = key.get("location") or last_location
        last_location = location
        target = key.get("look_at")
        if target is not None:
            point = positions.get(target) if isinstance(target, str) else target
            if point is None:
                raise KeyError(f"look_at target {target!r} was not found in the level")
            if location is None:
                raise ValueError(f"camera {camera.get('id')}: look_at needs a location on the same or an earlier key")
            key["rotation"] = look_at_rotation(location, point)
            key["aim_point"] = [round(v, 3) for v in point]
            if key.get("focus") == "auto":
                key["focus"] = round(math.dist(location, point), 2)
        keys.append(key)
    yaws = unwrap_yaws([k["rotation"][1] for k in keys if "rotation" in k])
    for key in (k for k in keys if "rotation" in k):
        key["rotation"] = [key["rotation"][0], yaws.pop(0), key["rotation"][2] if len(key["rotation"]) > 2 else 0.0]
    return keys


def look_at_targets(plan: dict[str, Any]) -> set[str]:
    return {k["look_at"] for c in plan.get("cameras", []) for k in c.get("keys", []) if isinstance(k.get("look_at"), str)}


def ray_box_entry(origin: list[float], target: list[float], box_min: list[float], box_max: list[float]) -> float | None:
    """Distance along origin->target where the ray enters the box (0 if origin is inside), None if it misses."""
    direction = [target[i] - origin[i] for i in range(3)]
    length = math.sqrt(sum(d * d for d in direction)) or 1.0
    direction = [d / length for d in direction]
    near, far = 0.0, float("inf")
    for i in range(3):
        if abs(direction[i]) < 1e-9:
            if not box_min[i] <= origin[i] <= box_max[i]:
                return None
            continue
        t1, t2 = (box_min[i] - origin[i]) / direction[i], (box_max[i] - origin[i]) / direction[i]
        near, far = max(near, min(t1, t2)), min(far, max(t1, t2))
        if near > far:
            return None
    return near
