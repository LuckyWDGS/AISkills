"""Estimated Blueprint node geometry shared by blueprint_layout and blueprint_lint.

Epic MCP returns node positions and pins but no node sizes, and get_node_size in editor Python
returns placeholders for K2 nodes. These estimates are calibrated on UE 5.8 graph-editor captures
(graph units, zoom 1.0) and lean large: a too-large box only costs spacing, a too-small one
makes the layout overlap nodes and route wires backward.

Input is one entry of BlueprintTools.get_node_infos (or a node of an inspect_blueprint snapshot):
{"node": {"refPath"}, "type_id", "position", "input_pins": [...], "output_pins": [...]},
each pin {"name", "type_id", "value", "connected_pins"}.
"""

from __future__ import annotations

import re
import json
from typing import Any


def logic_signature(infos: list[dict[str, Any]]) -> str:
    """Canonical node/pin/default/link data, excluding positions and comment presentation."""
    rows = []
    for info in infos:
        row = {"node": info["node"], "type_id": info["type_id"]}
        for side in ("input_pins", "output_pins"):
            row[side] = [{**{k: p.get(k) for k in ("name", "type_id", "value", "pin_id")},
                          "connected_pins": sorted(p["connected_pins"], key=lambda v: json.dumps(v, sort_keys=True))}
                         for p in info[side]]
        rows.append(row)
    return json.dumps(sorted(rows, key=lambda row: json.dumps(row["node"], sort_keys=True)), sort_keys=True)

# Localized exec pin type names (English and Simplified Chinese editors).
EXEC_PIN_TYPES = {"exec", "Exec", "执行"}

HEADER = 36.0           # title bar of a node without a "Target is ..." subtitle
HEADER_TARGET = 50.0    # title bar with the subtitle line
ROW = 28.0              # one pin row
PAD = 12.0              # bottom padding
COMPACT_HEIGHT = 32.0   # variable getters and reroutes
TITLE_CHAR = 10.5       # title font, per Latin character
LABEL_CHAR = 8.0        # pin label font, per Latin character
PIN_SIDE = 28.0         # pin icon plus inner padding on one side
CENTER_GAP = 40.0       # gap between the input and output label columns
WIDTH_MARGIN = 1.1

# Pins the engine shows only after expanding "advanced" when they are unconnected.
ADVANCED_PINS = {"TraceColor", "TraceHitColor", "DrawTime", "DrawDebugTime", "SimFrequency",
                 "OverrideGravityZ", "WorldContextObject", "LatentInfo", "bIgnoreSelf"}
HIDDEN_PINS = {"WorldContextObject", "LatentInfo", "__WorldContext"}
EXEC_LABELS = {"execute", "then", "exec", "Exec"}
# Break nodes for large structs show a few pins and fold the rest behind the advanced arrow.
BREAK_VISIBLE = 2

_NUMBER = re.compile(r"^-?\d+(\.\d+)?(e-?\d+)?$", re.IGNORECASE)
_VECTOR = re.compile(r"^(-?[\d.]+, ?-?[\d.]+, ?-?[\d.]+|\((X|Pitch)=.*\))$")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CJK = re.compile(r"[　-鿿＀-￯]")


def node_path(node: dict[str, Any]) -> str:
    ref = node["node"]
    return ref["refPath"] if isinstance(ref, dict) else str(ref)


def node_kind(node: dict[str, Any]) -> str:
    """Short K2 class name of the node object, e.g. K2Node_CallFunction."""
    return re.sub(r"_\d+$", "", node_path(node).rsplit(".", 1)[-1])


def is_exec_pin(pin: dict[str, Any]) -> bool:
    return pin.get("type_id") in EXEC_PIN_TYPES


def has_exec(node: dict[str, Any]) -> bool:
    return any(is_exec_pin(pin) for pin in node["input_pins"] + node["output_pins"])


def text_width(text: str, per_char: float) -> float:
    wide = len(_CJK.findall(text))
    return (len(text) - wide + 2 * wide) * per_char


def display_name(name: str) -> str:
    """Approximate the editor's pin label: bTraceComplex -> Trace Complex, ReturnValue -> Return Value."""
    if name in EXEC_LABELS:
        return ""
    if name == "self":
        return "Target"
    if re.match(r"^b[A-Z]", name):
        name = name[1:]
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)


def title_of(node: dict[str, Any]) -> str:
    title = str(node.get("type_id") or node_kind(node)).rsplit("|", 1)[-1]
    if title.startswith("Get") and node_kind(node) == "K2Node_VariableGet":
        title = title[3:]
    return display_name(title)


def _widget(pin: dict[str, Any]) -> tuple[float, int]:
    """(width, rows) of the default-value widget an unconnected input pin shows."""
    if pin.get("connected_pins") or is_exec_pin(pin):
        return 0.0, 1
    value = str(pin.get("value") or "")
    if value in ("true", "false"):
        return 28.0, 1
    if _NUMBER.match(value):
        return 64.0, 1
    if _VECTOR.match(value):
        return 200.0, 2
    if value.startswith("(R="):
        return 64.0, 1
    if _IDENTIFIER.match(value):
        return 150.0, 2            # enum / channel dropdown on its own row
    if value:
        return 110.0, 1
    return 36.0, 1                 # object pin showing "self" or an empty picker


def visible_pins(node: dict[str, Any], output: bool) -> list[dict[str, Any]]:
    pins = node["output_pins"] if output else node["input_pins"]
    shown = [pin for pin in pins if pin["name"] not in HIDDEN_PINS]
    if output and title_of(node).startswith("Break") and len(shown) > 6:
        return [pin for i, pin in enumerate(shown) if i < BREAK_VISIBLE or pin.get("connected_pins")]
    return [pin for pin in shown if pin.get("connected_pins") or pin["name"] not in ADVANCED_PINS]


def _folded(node: dict[str, Any]) -> bool:
    return any(len(visible_pins(node, side)) < len([p for p in (node["output_pins"] if side else node["input_pins"])
                                                    if p["name"] not in HIDDEN_PINS]) for side in (False, True))


def _rows(pins: list[dict[str, Any]], inputs: bool) -> list[tuple[float, int]]:
    """Per pin: (label + widget width, row count)."""
    rows = []
    for pin in pins:
        label = text_width(display_name(pin["name"]), LABEL_CHAR)
        widget, count = _widget(pin) if inputs else (0.0, 1)
        rows.append((label + (widget if count == 1 else 0.0), count))
        if count == 2:
            rows[-1] = (max(label, widget), 2)
    return rows


def _header(node: dict[str, Any]) -> float:
    names = {pin["name"] for pin in node["input_pins"]}
    return HEADER_TARGET if "self" in names and node_kind(node) == "K2Node_CallFunction" else HEADER


def estimate_size(node: dict[str, Any]) -> tuple[float, float]:
    """(width, height) in graph units."""
    kind = node_kind(node)
    if kind == "K2Node_Knot":
        return 32.0, 16.0
    if kind in ("K2Node_VariableGet", "K2Node_Self") and not node["input_pins"]:
        label = node["output_pins"][0]["name"] if node["output_pins"] else title_of(node)
        return text_width(display_name(label), LABEL_CHAR) + 64.0, COMPACT_HEIGHT
    ins, outs = _rows(visible_pins(node, False), True), _rows(visible_pins(node, True), False)
    row_count = max(sum(c for _, c in ins), sum(c for _, c in outs), 1) + (1 if _folded(node) else 0)
    pairs = max(len(ins), len(outs))
    widest_row = max(((ins[i][0] if i < len(ins) else 0.0) + (outs[i][0] if i < len(outs) else 0.0)
                      for i in range(pairs)), default=0.0) + 2 * PIN_SIDE + CENTER_GAP
    if kind in ("K2Node_PromotableOperator", "K2Node_CommutativeAssociativeBinaryOperator"):
        return max(150.0, widest_row), 12.0 + ROW * row_count
    header = 30.0 if kind in ("K2Node_VariableSet",) else _header(node)
    title = text_width(title_of(node), TITLE_CHAR) + 60.0
    return round(max(title, widest_row, 140.0) * WIDTH_MARGIN), header + ROW * row_count + PAD


def estimate_box(node: dict[str, Any]) -> tuple[float, float, float, float]:
    width, height = estimate_size(node)
    return float(node["position"]["x"]), float(node["position"]["y"]), width, height


def pin_offset(node: dict[str, Any], pin_name: str, output: bool) -> float:
    """Vertical offset of a pin's centre from the node's top edge."""
    kind = node_kind(node)
    if kind in ("K2Node_VariableGet", "K2Node_Self", "K2Node_Knot") and not node["input_pins"]:
        return COMPACT_HEIGHT / 2
    pins = visible_pins(node, output)
    rows = _rows(pins, not output)
    header = 6.0 if kind in ("K2Node_PromotableOperator", "K2Node_CommutativeAssociativeBinaryOperator") else (
        30.0 if kind == "K2Node_VariableSet" else _header(node))
    row = 0
    for pin, (_, count) in zip(pins, rows):
        if pin["name"] == pin_name:
            return header + ROW * row + ROW / 2
        row += count
    return header + ROW / 2


def pin_point(node: dict[str, Any], box: tuple[float, float, float, float], pin_name: str, output: bool) -> tuple[float, float]:
    x, y, width, _ = box
    return (x + width if output else x), y + pin_offset(node, pin_name, output)


def segment_hits_box(a: tuple, b: tuple, box: tuple, inset: float = 12.0) -> bool:
    """True when the straight segment a-b passes through box (Liang-Barsky clip)."""
    x, y, w, h = box[0] + inset, box[1] + inset, box[2] - 2 * inset, box[3] - 2 * inset
    if w <= 0 or h <= 0:
        return False
    dx, dy = b[0] - a[0], b[1] - a[1]
    low, high = 0.0, 1.0
    for p, q in ((-dx, a[0] - x), (dx, x + w - a[0]), (-dy, a[1] - y), (dy, y + h - a[1])):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            low = max(low, t)
        else:
            high = min(high, t)
        if low > high:
            return False
    return True
