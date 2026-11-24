"""Background image capture through Epic's MCP: asset thumbnails and posed scene frames.

UE 5.9 uses ``SceneCaptureToolset`` with an explicit camera snapshot and checks
the editor view before/after. UE 5.8 uses posed ``CaptureViewport`` without
moving the user's camera; it needs explicit empty annotation arguments.
"""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .protocol import McpError, unwrap_result


SCHEMA_VERSION = "mcp_capture/1"
TRANSPORT = "epic-mcp EditorAppToolset"
# Grid and labels off; UE 5.8 needs every field even when the overlay is unused.
NO_ANNOTATIONS = {"gridSpacing": 0, "gridExtent": 0, "gridHeight": 0, "maxLabelDistance": 0,
                  "classFilter": None, "maxLabels": 0}


def asset_package_path(asset_path: str) -> str:
    """'/Game/M/M_X.M_X' -> '/Game/M/M_X'; CaptureAssetImage takes the package path."""
    head, _, leaf = asset_path.rpartition("/")
    return f"{head}/{leaf.split('.', 1)[0]}" if head else asset_path


def parse_pose(text: str) -> dict[str, Any]:
    """'x,y,z,pitch,yaw,roll' (cm, degrees) -> a ToolsetTransform."""
    try:
        x, y, z, pitch, yaw, roll = (float(part) for part in text.split(","))
    except ValueError as exc:
        raise McpError(f"Pose must be 'x,y,z,pitch,yaw,roll' (six numbers), got {text!r}") from exc
    return {"location": {"x": x, "y": y, "z": z}, "rotation": {"pitch": pitch, "yaw": yaw, "roll": roll},
            "scale": {"x": 1, "y": 1, "z": 1}}


def png_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def save_image(image: dict[str, Any], out_png: Path) -> dict[str, Any]:
    try:
        data = base64.b64decode(image.get("data") or "", validate=True)
    except (binascii.Error, ValueError, TypeError) as exc:
        raise McpError("Capture returned invalid base64 image data") from exc
    if not data:
        raise McpError("Capture returned an empty image")
    size = png_size(data)
    if not size or min(size) <= 0:
        raise McpError("Capture did not return a PNG image with valid dimensions")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_png.write_bytes(data)
    return {"path": str(out_png), "mime_type": image.get("mimeType", ""), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "width": size[0] if size else None, "height": size[1] if size else None}


def result_image(raw: Any, value: Any = None) -> dict[str, Any]:
    """UE59.Capture.Media：URN 仅作关联标识，真实图片来自同一结果的 image 块。"""
    value = unwrap_result(raw) if value is None else value
    if isinstance(value, dict):
        embedded = value.get("image", value)
        if isinstance(embedded, dict) and "data" in embedded:
            return embedded  # UE 5.8 embeds media in the JSON return value.
    blocks = [item for item in raw.get("content", [])
              if isinstance(item, dict) and item.get("type") == "image"] if isinstance(raw, dict) else []
    if len(blocks) != 1:
        raise McpError(f"Capture returned {len(blocks)} image content blocks; expected one. "
                       "A urn:toolresult reference is not a downloadable URL or file path.")
    return blocks[0]


def capture_asset(client: Any, asset_path: str, out_png: Path) -> dict[str, Any]:
    """The editor's thumbnail render of an asset (material sphere, mesh, texture, ...)."""
    raw = client.call_resolved_tool(
        "EditorAppToolset", "CaptureAssetImage", {"assetPath": asset_package_path(asset_path)})
    return save_image(result_image(raw), out_png)


def capture_scene59(client: Any, out_png: Path, pose: dict[str, Any] | None = None) -> dict[str, Any]:
    """UE59.Capture.Offscreen：显式相机快照离屏渲染，同时记录用户视口前后状态。"""
    before = unwrap_result(client.call_resolved_tool("SceneCaptureToolset", "GetActiveEditorView", {}))
    if not isinstance(before, dict) or not before.get("world") or not isinstance(before.get("camera"), dict):
        raise McpError("SceneCaptureToolset returned no active level viewport camera/world")
    camera = copy.deepcopy(before["camera"])
    if pose:
        camera.update(location=pose["location"], rotation=pose["rotation"])
    dimensions = before.get("sourceDimensions") or {}
    raw = client.call_resolved_tool("SceneCaptureToolset", "Capture", {
        "world": before["world"], "camera": camera, "mode": "Lit",
        "options": {"width": dimensions.get("x") or 1024, "height": dimensions.get("y") or 1024,
                    "screenPercentage": 1},
    })
    result = unwrap_result(raw)
    frame = save_image(result_image(raw, result), out_png)
    after = unwrap_result(client.call_resolved_tool("SceneCaptureToolset", "GetActiveEditorView", {}))
    metadata = result.get("metadata") or {}
    captured_camera = metadata.get("camera") or camera
    frame.update(camera_location=captured_camera.get("location"), camera_rotation=captured_camera.get("rotation"),
                 camera_fov=captured_camera.get("fOV"), capture_metadata=metadata,
                 warnings=result.get("warnings") or [], transport="epic-mcp SceneCaptureToolset",
                 camera_before=before.get("camera"), camera_after=after.get("camera"),
                 world_before=before.get("world"), world_after=after.get("world"),
                 camera_unchanged=before.get("camera") == after.get("camera") and before.get("world") == after.get("world"))
    return frame


def capture_viewport(client: Any, out_png: Path, pose: dict[str, Any] | None = None) -> dict[str, Any]:
    """One level-viewport frame, from ``pose`` when given, else from the current viewport camera."""
    inventory = client.list_toolsets() if hasattr(client, "list_toolsets") else []
    if any(item["name"].rsplit(".", 1)[-1] == "SceneCaptureToolset" for item in inventory):
        return capture_scene59(client, out_png, pose)
    arguments: dict[str, Any] = {"annotations": NO_ANNOTATIONS, "bShowUI": False}
    if pose:
        arguments["captureTransform"] = pose
    raw = client.call_resolved_tool("EditorAppToolset", "CaptureViewport", arguments)
    result = unwrap_result(raw)
    frame = save_image(result_image(raw, result), out_png)
    frame.update(camera_location=result.get("cameraLocation"), camera_rotation=result.get("cameraRotation"),
                 camera_fov=result.get("cameraFOV"))
    return frame


def capture_report(client: Any, mode: str, out_dir: Path, stem: str, *, asset_path: str = "",
                   pose: dict[str, Any] | None = None, frames: int = 1, interval: float = 0.0) -> dict[str, Any]:
    """Capture and describe the frames; never raises for a failed capture, it is reported instead."""
    rows: list[dict[str, Any]] = []
    error = ""
    try:
        for index in range(max(1, frames) if mode == "viewport" else 1):
            if index and interval > 0:
                time.sleep(interval)
            out_png = out_dir / (f"{stem}.png" if frames <= 1 else f"{stem}-f{index:02d}.png")
            rows.append(capture_asset(client, asset_path, out_png) if mode == "asset"
                        else capture_viewport(client, out_png, pose))
            if rows[-1].get("camera_unchanged") is False:
                raise McpError("Editor view camera or world changed during capture; "
                               "image and before/after state were retained. No camera restore was attempted.")
    except McpError as exc:
        error = str(exc)
    return {
        "tool": "mcp_capture",
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "asset_path": asset_path,
        "pose": pose,
        "interval_seconds": interval if mode == "viewport" and frames > 1 else 0,
        "transport": rows[0].get("transport", TRANSPORT) if rows else TRANSPORT,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ok": bool(rows) and not error,
        "error": error,
        "frames": rows,
        # Distinct hashes show the image changed; temporal AA noise also changes it, so judge motion visually.
        "distinct_frames": len({row["sha256"] for row in rows}),
    }
