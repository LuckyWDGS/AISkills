"""Read persisted comment bounds without opening Slate or editing a Blueprint.

ObjectExporterT3D omits properties equal to the native class defaults. Only the
stock EdGraphNode_Comment is accepted: its position defaults are zero; width and
height come from BlueprintEditorLibrary.get_node_size on the same object.
"""

from __future__ import annotations

import math
import re


GEOMETRY_SOURCE = "serialized_bounds_ue_node_size"


def decode_object_export(data: bytes) -> str:
    """Epic writes non-ANSI text exports as UTF-16 with a BOM on Windows."""
    return data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")


def parse_comment_bounds(text: str, expected_path: str, size: list[float]) -> dict[str, float]:
    """Parse one official export, rejecting wrong objects, ambiguous fields and stale size reads."""
    lines = text.lstrip("\ufeff").splitlines()
    headers = [line for line in lines if line.lstrip().startswith("Begin Object")]
    if len(headers) != 1 or not lines or lines[0] != headers[0] or lines[-1].strip() != "End Object":
        raise ValueError("Expected a single complete comment object export")
    if not re.search(r'\bClass=/Script/UnrealEd\.EdGraphNode_Comment\s', headers[0]):
        raise ValueError("Only the native EdGraphNode_Comment defaults have been verified")
    match = re.search(r'\bExportPath="[^"\']+\'([^\']+)\'"', headers[0])
    if not match or match.group(1) != expected_path:
        raise ValueError("Comment export identity does not match the requested object")
    if len(size) != 2 or any(not math.isfinite(v) or v <= 0 for v in size):
        raise ValueError("Comment size is unavailable")
    values = {}
    for name, default in zip(("NodePosX", "NodePosY", "NodeWidth", "NodeHeight"), (0, 0, *size)):
        matches = [line.strip().split("=", 1)[1] for line in lines[1:-1]
                   if line.strip().startswith(name + "=")]
        if len(matches) > 1 or (matches and not re.fullmatch(r"-?\d+", matches[0])):
            raise ValueError(f"Ambiguous or malformed {name}")
        values[name] = int(matches[0]) if matches else default
    if [values["NodeWidth"], values["NodeHeight"]] != list(size):
        raise ValueError("Comment changed between the size read and export")
    return dict(zip(("x", "y", "width", "height"), values.values()))


def contained_nodes(bounds: dict, node_bounds: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Return fully enclosed and partially intersecting nodes, using UE's model sizes."""
    def rect(box):
        values = [box[key] for key in ("x", "y", "width", "height")]
        if any(not math.isfinite(v) for v in values) or values[2] <= 0 or values[3] <= 0:
            raise ValueError("Invalid graph bounds")
        x, y, w, h = values
        return x, y, x + w, y + h

    x, y, right, bottom = rect(bounds)
    enclosed, partial = [], []
    for name, box in node_bounds.items():
        nx, ny, nr, nb = rect(box)
        if nx >= x and ny >= y and nr <= right and nb <= bottom:
            enclosed.append(name)
        elif min(nr, right) > max(nx, x) and min(nb, bottom) > max(ny, y):
            partial.append(name)
    return enclosed, partial


def geometry_matches_snapshot(frame: dict, nodes: dict[str, dict]) -> bool:
    """Never validate an old MCP snapshot using positions from a different graph state."""
    measured = frame.get("node_bounds", {})
    if set(measured) != set(nodes):
        return False
    return all(measured[name].get("x") == node.get("position", {}).get("x") and
               measured[name].get("y") == node.get("position", {}).get("y") for name, node in nodes.items())
