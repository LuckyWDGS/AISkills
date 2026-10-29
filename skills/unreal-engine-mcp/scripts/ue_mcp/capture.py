"""Background image capture through EditorAppToolset: asset thumbnails and posed level-viewport frames.

``CaptureViewport`` with a pose renders from that pose without moving the user's
viewport camera (verified on UE 5.8.4), so it is the preview route for placed
actors such as a Niagara system in a level. UE 5.8 rejects omitted optional
arguments, so empty annotations are sent explicitly.
"""

from __future__ import annotations

import base64
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
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def save_image(image: dict[str, Any], out_png: Path) -> dict[str, Any]:
    data = base64.b64decode(image.get("data") or "")
    if not data:
        raise McpError("Capture returned an empty image")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    out_png.write_bytes(data)
    size = png_size(data)
    return {"path": str(out_png), "mime_type": image.get("mimeType", ""), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "width": size[0] if size else None, "height": size[1] if size else None}


def capture_asset(client: Any, asset_path: str, out_png: Path) -> dict[str, Any]:
    """The editor's thumbnail render of an asset (material sphere, mesh, texture, ...)."""
    image = unwrap_result(client.call_resolved_tool(
        "EditorAppToolset", "CaptureAssetImage", {"assetPath": asset_package_path(asset_path)}))
    return save_image(image, out_png)


def capture_viewport(client: Any, out_png: Path, pose: dict[str, Any] | None = None) -> dict[str, Any]:
    """One level-viewport frame, from ``pose`` when given, else from the current viewport camera."""
    arguments: dict[str, Any] = {"annotations": NO_ANNOTATIONS, "bShowUI": False}
    if pose:
        arguments["captureTransform"] = pose
    result = unwrap_result(client.call_resolved_tool("EditorAppToolset", "CaptureViewport", arguments))
    frame = save_image(result.get("image") or {}, out_png)
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
    except McpError as exc:
        error = str(exc)
    return {
        "tool": "mcp_capture",
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "asset_path": asset_path,
        "pose": pose,
        "interval_seconds": interval if mode == "viewport" and frames > 1 else 0,
        "transport": TRANSPORT,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ok": bool(rows) and not error,
        "error": error,
        "frames": rows,
        # Distinct hashes show the image changed; temporal AA noise also changes it, so judge motion visually.
        "distinct_frames": len({row["sha256"] for row in rows}),
    }
