"""Explicit Images API options and inspection of returned media bytes."""

import io
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path


OUTPUT_FORMATS = ("png", "jpeg", "webp", "gif", "svg")
SVG_EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


def add_media_arguments(parser):
    parser.add_argument("--output-compression", type=int, help="JPEG/WebP only, 0-100.")
    parser.add_argument("--frame-count", type=int, help="GIF only, 2-16; default 9.")
    parser.add_argument("--frame-duration-ms", type=int, help="GIF only, 20-2000; default 200, rounded by the API to 10 ms.")
    parser.add_argument("--svg-model", help="Optional SVG author model; requires provider permission for model selection.")
    parser.add_argument("--svg-reasoning", choices=SVG_EFFORTS, help="SVG author reasoning, separate from image complexity.")
    parser.add_argument("--stream", action="store_true", default=None, help="Request Images SSE; save final images, not intermediate previews.")
    parser.add_argument("--partial-images", type=int, help="With --stream, request 0-3 intermediate previews.")
    parser.add_argument("--moderation", choices=("auto", "low"))
    parser.add_argument("--safety-identifier", help="Optional pseudonymous end-user ID, at most 128 characters.")


def extra_image_fields(args, operation, api="images"):
    """Reject unsupported combinations before catalog checks or billable POSTs."""
    get = lambda name: getattr(args, name, None)
    fmt = get("output_format")
    names = ("output_compression", "frame_count", "frame_duration_ms", "svg_model",
             "svg_reasoning", "stream", "partial_images", "moderation", "safety_identifier", "markup")
    if api != "images":
        if fmt in ("gif", "svg") or any(get(name) is not None for name in names):
            raise SystemExit("GIF/SVG and the advanced image options require --api images; they are not silently forwarded to Responses.")
        return {}
    if get("n") is not None and not 1 <= get("n") <= 10:
        raise SystemExit("--n must be between 1 and 10.")
    if get("markup") and get("mask"):
        raise SystemExit("--markup and --mask cannot be combined.")
    if get("markup") and operation != "edit":
        raise SystemExit("--markup requires an image edit.")
    compression = get("output_compression")
    if compression is not None and (fmt not in ("jpeg", "webp") or not 0 <= compression <= 100):
        raise SystemExit("--output-compression requires --output-format jpeg|webp and a value from 0 to 100.")
    partials = get("partial_images")
    if partials is not None and (not get("stream") or not 0 <= partials <= 3):
        raise SystemExit("--partial-images requires --stream and a value from 0 to 3.")
    if get("safety_identifier") is not None and not 1 <= len(get("safety_identifier")) <= 128:
        raise SystemExit("--safety-identifier must contain 1-128 characters.")
    if fmt != "gif" and any(get(name) is not None for name in ("frame_count", "frame_duration_ms")):
        raise SystemExit("--frame-count and --frame-duration-ms require --output-format gif.")
    if fmt != "svg" and any(get(name) is not None for name in ("svg_model", "svg_reasoning")):
        raise SystemExit("--svg-model and --svg-reasoning require --output-format svg.")
    if fmt in ("gif", "svg") and (get("stream") or partials is not None):
        raise SystemExit("GIF/SVG do not support streaming or partial images.")
    fields = {name: get(name) for name in ("output_compression", "stream", "partial_images",
                                          "moderation", "safety_identifier") if get(name) is not None}
    if fmt == "gif":
        if get("mask"):
            raise SystemExit("GIF output does not support --mask.")
        count = get("frame_count") if get("frame_count") is not None else 9
        duration = get("frame_duration_ms") if get("frame_duration_ms") is not None else 200
        if not 2 <= count <= 16:
            raise SystemExit("--frame-count must be between 2 and 16.")
        if not 20 <= duration <= 2000:
            raise SystemExit("--frame-duration-ms must be between 20 and 2000 (documented guide range).")
        fields.update(frame_count=count, frame_duration_ms=duration)
    if fmt == "svg":
        if operation == "edit":
            raise SystemExit("SVG edits are not enabled: the official guide and edit schema disagree. Use SVG generation.")
        if get("n") not in (None, 1):
            raise SystemExit("SVG output requires --n 1.")
        fields["n"] = 1
        if get("svg_reasoning") and not get("svg_model"):
            raise SystemExit("--svg-reasoning requires --svg-model and provider access to SVG model selection.")
        if get("svg_model"):
            if not get("svg_model").strip():
                raise SystemExit("--svg-model cannot be empty.")
            fields["svg"] = {"model": get("svg_model")}
            if get("svg_reasoning"):
                fields["svg"]["reasoning"] = {"effort": get("svg_reasoning")}
    return fields


def validate_size_option(value, model, *, exact=False):
    if value == "auto":
        if exact:
            raise SystemExit("--require-exact-size needs explicit WIDTHxHEIGHT, not auto.")
        return
    match = re.fullmatch(r"([1-9][0-9]*)x([1-9][0-9]*)", value or "")
    if not match:
        raise SystemExit("--size must be auto or WIDTHxHEIGHT, for example 1536x1024.")
    width, height = map(int, match.groups())
    if model.startswith(("gpt-image-2.5", "gpt-image-2.6")):
        if width % 16 or height % 16 or max(width, height) > 3 * min(width, height):
            raise SystemExit("Custom dimensions must be multiples of 16 with an aspect ratio from 1:3 to 3:1.")
    # Do not impose 2.5 pixel budgets on GIFs or claim a verified 2.6 gateway limit.


def _svg_root(raw):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("SVG declarations with external/entity definitions are not supported")
    root = ET.fromstring(raw)
    if root.tag not in ("svg", "{http://www.w3.org/2000/svg}svg"):
        raise ValueError("not an SVG root")
    return root


def detect_format(raw):
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if raw.startswith(b"\xff\xd8"):
        return "jpeg"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "webp"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if raw.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"<"):
        try:
            _svg_root(raw)
            return "svg"
        except (ET.ParseError, ValueError):
            pass
    return None


def inspect_media(raw):
    fmt = detect_format(raw)
    info = {"format": fmt, "readable": False, "dimensions": None}
    if fmt == "svg":
        root = _svg_root(raw)
        for node in root.iter():
            tag = node.tag.rsplit("}", 1)[-1].lower()
            if tag in ("script", "foreignobject", "image", "animate", "animatemotion", "animatetransform", "set"):
                info["error"] = "svg_is_not_static_self_contained_vector"
                return info
            for name, value in node.attrib.items():
                local = name.rsplit("}", 1)[-1].lower()
                if local.startswith("on") or (local in ("href", "src") and not value.startswith("#")):
                    info["error"] = "svg_has_active_or_external_content"
                    return info
            text = " ".join(node.attrib.values()) + (node.text or "")
            if re.search(r"@import|url\(\s*['\"]?(?!#)[^\s'\"]", text, re.I):
                info["error"] = "svg_has_external_style_reference"
                return info
        def length(value):
            match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(?:px)?", value or "")
            return float(match[1]) if match else None
        width, height = length(root.get("width")), length(root.get("height"))
        if width and height:
            info["dimensions"] = [width, height]
            info["dimension_source"] = "width_height"
        else:
            try:
                box = [float(x) for x in re.split(r"[ ,]+", root.get("viewBox", "").strip())]
                if len(box) == 4 and all(math.isfinite(x) for x in box) and box[2] > 0 and box[3] > 0:
                    info["view_box"] = box
                    # viewBox user units are not evidence of a rendered pixel size.
            except ValueError:
                pass
        info.update(readable=True, vector_element_count=sum(1 for _ in root.iter()))
        return info
    if not fmt:
        info["error"] = "unrecognized_image_bytes"
        return info
    try:
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as im:
            info["dimensions"] = list(im.size)
            durations, hashes = [], set()
            import hashlib
            for index in range(getattr(im, "n_frames", 1)):
                im.seek(index)
                im.load()
                durations.append(im.info.get("duration", 0))
                if fmt == "gif":
                    hashes.add(hashlib.sha256(im.convert("RGBA").tobytes()).hexdigest())
            info["readable"] = True
            if fmt == "gif":
                info.update(frame_count=len(durations), frame_durations_ms=durations,
                            total_duration_ms=sum(durations), distinct_frames=len(hashes), loop=im.info.get("loop"))
    except ImportError:
        if fmt == "png" and len(raw) >= 33 and raw[12:16] == b"IHDR":
            info.update(dimensions=[int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")], readable=True)
        else:
            info["error"] = "Pillow_required_for_media_inspection"
    except Exception as exc:
        info["error"] = "media_decode_failed:" + type(exc).__name__
    return info


def validate_media_outputs(paths, args):
    requested = getattr(args, "output_format", None)
    results, warnings = [], []
    count = getattr(args, "n", None)
    if count is not None and len(paths) != count:
        warnings.append({"warning": "output_count_mismatch", "expected": count, "actual": len(paths)})
    for path in paths:
        info = inspect_media(Path(path).read_bytes())
        info["path"] = str(Path(path).resolve())
        results.append(info)
        if not info["readable"]:
            warnings.append({"path": info["path"], "warning": info.get("error", "unreadable_media")})
        if requested and info["format"] != requested:
            warnings.append({"path": info["path"], "warning": "output_format_mismatch", "expected": requested, "actual": info["format"]})
        if requested == "gif" and info["format"] == "gif" and info["readable"]:
            expected = getattr(args, "frame_count", None) or 9
            if info["frame_count"] != expected or info["distinct_frames"] < 2:
                warnings.append({"path": info["path"], "warning": "gif_animation_mismatch", "expected_frames": expected,
                                 "actual_frames": info["frame_count"], "distinct_frames": info["distinct_frames"]})
            duration = getattr(args, "frame_duration_ms", None) or 200
            if any(abs(value - duration) > 10 for value in info["frame_durations_ms"]):
                warnings.append({"path": info["path"], "warning": "gif_timing_mismatch", "requested_frame_ms": duration})
    return {"requested_output_format": requested, "media_outputs": results,
            "media_validation_failed": bool(warnings) or not bool(paths), "media_validation_warnings": warnings}


def validate_markup(markup, original):
    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise SystemExit("Pillow is required to validate --markup before upload.")
    try:
        with Image.open(io.BytesIO(original.data)) as source, Image.open(io.BytesIO(markup.data)) as overlay:
            if overlay.format != "PNG" or overlay.size != ImageOps.exif_transpose(source).size:
                raise SystemExit("--markup must be a PNG with the first image's dimensions after orientation.")
            if overlay.convert("RGBA").getchannel("A").getextrema()[0] == 255:
                raise SystemExit("--markup must contain transparent pixels.")
    except (OSError, ValueError) as exc:
        raise SystemExit("Cannot decode --markup or its source image: " + type(exc).__name__)
