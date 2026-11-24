"""Fit a perspective camera to labelled UE world points in a photograph.

The solve is offline and keeps the supplied roll and all world coordinates fixed.
Use --evaluate-only to measure a known camera, or --candidate-camera to compare two saved poses.
"""

import argparse
import json
from pathlib import Path

import numpy as np


def vector(values, length, label):
    result = np.asarray(values, dtype=float)
    if result.shape != (length,) or not np.isfinite(result).all():
        raise ValueError(f"{label} needs {length} finite numbers")
    return result


def project(points, pose, roll, size):
    """Return pixel centres (top left is 0,0) and signed forward depth in cm."""
    location = pose[:3]
    yaw, pitch, fov = np.radians(pose[3:])
    cy, sy = np.cos(yaw), np.sin(yaw)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cr, sr = np.cos(np.radians(roll)), np.sin(np.radians(roll))
    forward = np.array([cp * cy, cp * sy, sp])
    level_right = np.array([-sy, cy, 0])
    level_up = np.cross(forward, level_right)
    right = cr * level_right - sr * level_up
    up = sr * level_right + cr * level_up

    relative = points - location
    depth = relative @ forward
    focal_px = 0.5 * size[0] / np.tan(0.5 * fov)
    # Keep trial steps around the camera plane finite. Actual poses are checked below.
    offset = np.column_stack((relative @ right, -(relative @ up)))
    pixels = (size - 1) / 2 + focal_px * offset / np.maximum(depth[:, None], 1e-6)
    return pixels, depth


def fit_pose(world, observed, weights, initial, roll, size):
    try:
        from scipy.optimize import least_squares
    except ImportError as error:
        raise ValueError("Fitting needs SciPy. --evaluate-only needs only NumPy.") from error

    if len(np.unique(world, axis=0)) < 4 or np.linalg.matrix_rank(world - world.mean(axis=0)) < 2:
        raise ValueError("Fitting needs at least four distinct anchors spanning more than one line")

    def residual(pose):
        pixels, _ = project(world, pose, roll, size)
        return ((pixels - observed) * np.sqrt(weights[:, None])).ravel()

    lower = [-np.inf, -np.inf, -np.inf, -np.inf, -90, 0]
    upper = [np.inf, np.inf, np.inf, np.inf, 90, 180]
    result = least_squares(residual, initial, bounds=(lower, upper), jac="3-point", x_scale="jac")
    if not result.success:
        raise ValueError(f"Camera fit did not converge: {result.message}")
    # A front-facing wall can be reproduced at many combinations of forward position
    # and focal length, even with hundreds of perfectly labelled points on the wall.
    _, depth = project(world, result.x, roll, size)
    if np.ptp(depth) <= 1e-7 * np.max(np.abs(depth)):
        raise ValueError("Equal viewing depths leave forward position and FOV ambiguous. Add a nearer or farther off-axis anchor.")
    lengths = np.linalg.norm(result.jac, axis=0)
    if np.any(lengths == 0) or np.linalg.matrix_rank(result.jac / lengths, tol=1e-7) < 6:
        raise ValueError("The anchors do not resolve camera pose and FOV. Add landmarks at another depth.")
    return result.x


def read_pose(camera):
    if not isinstance(camera, dict):
        raise ValueError("camera must contain location, rotation and horizontal fOV")
    if camera.get("projectionMode", "Perspective") != "Perspective":
        raise ValueError("This projection expects a perspective camera")
    location, rotation = camera["location"], camera["rotation"]
    initial = vector([location[k] for k in "xyz"] +
                     [rotation["yaw"], rotation["pitch"], camera["fOV"]], 6, "camera")
    roll = float(rotation.get("roll", 0))
    if not np.isfinite(roll) or abs(initial[4]) >= 90 or not 0 < initial[5] < 180:
        raise ValueError("Use finite roll, pitch between -90 and 90, and horizontal fOV between 0 and 180 degrees")
    return initial, roll


def describe_pose(pose, roll):
    return {"location": dict(zip("xyz", pose[:3].tolist())),
            "rotation": {"pitch": float(pose[4]), "yaw": float(pose[3]), "roll": roll}, "fOV": float(pose[5])}


def analyze(data, evaluate_only, *, baseline_camera=None, candidate_camera=None):
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object with imageSize, camera and points")
    size = vector(data["imageSize"], 2, "imageSize")
    if np.any(size < 1) or np.any(size != np.floor(size)):
        raise ValueError("imageSize needs the photograph's positive integer width and height")
    initial, roll = read_pose(data["camera"])
    baseline, baseline_roll = (initial, roll) if baseline_camera is None else read_pose(baseline_camera)

    points = data["points"]
    if not isinstance(points, list) or not points:
        raise ValueError("points needs at least one labelled correspondence")
    names = [point["name"] for point in points]
    if any(not isinstance(name, str) or not name.strip() for name in names) or len(set(names)) != len(names):
        raise ValueError("Give each landmark a unique, non-empty name")
    world = np.stack([vector(point["ueCm"], 3, name) for point, name in zip(points, names)])
    observed = np.stack([vector(point["photoPx"], 2, name) for point, name in zip(points, names)])
    weights = vector([point.get("weight", 1) for point in points], len(points), "weights")
    used = weights > 0
    if (weights < 0).any() or not used.any():
        raise ValueError("Weights must be non-negative, with at least one positive anchor")
    raw_weights = weights
    weights = weights / weights.max()

    def check_visibility(labels, depths):
        hidden = [name for name, depth in zip(labels, depths) if depth <= 1e-6]
        if hidden:
            raise ValueError(f"Photographed landmarks on or behind the camera plane: {', '.join(hidden)}")

    def used_rms(errors):
        return float(np.sqrt(np.average(errors ** 2, weights=weights[used])))

    fit_names = [name for name, keep in zip(names, used) if keep]
    initial_pixels, initial_depths = project(world[used], initial, roll, size)
    initial_rms = None
    if (initial_depths > 1e-6).all():
        initial_rms = used_rms(np.linalg.norm(initial_pixels - observed[used], axis=1))
    elif baseline_camera is None or candidate_camera is None:
        check_visibility(fit_names, initial_depths)
    if candidate_camera is not None:
        pose, pose_roll = read_pose(candidate_camera)
    elif evaluate_only:
        pose, pose_roll = initial, roll
    else:
        pose = fit_pose(world[used], observed[used], weights[used], initial, roll, size)
        pose_roll = roll
    projected, depths = project(world, pose, pose_roll, size)
    check_visibility(names, depths)
    base_pixels, base_depths = project(world, baseline, baseline_roll, size)
    check_visibility(fit_names, base_depths[used])
    base_errors = np.linalg.norm(base_pixels - observed, axis=1)
    offsets = projected - observed
    errors = np.linalg.norm(offsets, axis=1)
    before_weighted, after_weighted = used_rms(base_errors[used]), used_rms(errors[used])
    before_held = after_held = change_held = None
    if (~used).any():
        after_held = float(np.sqrt(np.mean(errors[~used] ** 2)))
        if (base_depths[~used] > 1e-6).all():
            before_held = float(np.sqrt(np.mean(base_errors[~used] ** 2)))
            change_held = after_held - before_held
    rows = []
    for i, name in enumerate(names):
        base_visible = base_depths[i] > 1e-6
        rows.append({"name": name, "weight": float(raw_weights[i]), "role": "fit" if used[i] else "held-out",
                     "photoPx": observed[i].tolist(),
                     "baselineProjectedPx": base_pixels[i].tolist() if base_visible else None,
                     "baselineErrorPx": float(base_errors[i]) if base_visible else None,
                     "projectedPx": projected[i].tolist(), "offsetPx": offsets[i].tolist(), "errorPx": float(errors[i])})
    return {
        "imageSize": size.astype(int).tolist(),
        "camera": describe_pose(pose, pose_roll),
        "initialWeightedRmsPx": initial_rms,
        "baselineCamera": describe_pose(baseline, baseline_roll),
        "fitPointCount": int(used.sum()), "heldOutPointCount": int((~used).sum()),
        "baselineWeightedRmsPx": before_weighted, "weightedRmsPx": after_weighted,
        "weightedRmsChangePx": after_weighted - before_weighted,
        "baselineHeldOutRmsPx": before_held, "heldOutRmsPx": after_held, "heldOutRmsChangePx": change_held,
        "points": rows,
    }


def camera_from_file(path):
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a camera or a JSON object containing camera in {path}")
    return data.get("camera", data)


def save_overlay(report, photo_path, output_path):
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
    except ImportError as error:
        raise ValueError("Saving a photo overlay needs Pillow") from error
    if output_path.suffix.lower() != ".png":
        raise ValueError("Use a separate .png file for the overlay")
    if output_path.exists() and output_path.samefile(photo_path):
        raise ValueError("The overlay would overwrite its source photograph")
    with Image.open(photo_path) as source:
        photo = ImageOps.exif_transpose(source).convert("RGB")
    if photo.size != tuple(report["imageSize"]):
        raise ValueError(f"Photo size {photo.size} differs from anchor imageSize {report['imageSize']}. Use the same frame and pixel grid.")
    for family in ("msyh.ttc", "NotoSansCJK-Regular.ttc", "DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(family, 14)
            break
        except OSError:
            continue
    else:
        font = ImageFont.load_default()
    ink = ImageDraw.Draw(photo)
    yellow, orange, cyan = "#FFED62", "#FF8134", "#00E1EF"
    rows = report["points"]
    labels = [f"{i:02d}  {p['name']}  [{p['role']}]" for i, p in enumerate(rows, 1)]
    legend = [("Photo landmark (+)", yellow), ("Baseline projection (square)", orange),
              ("Candidate projection (circle)", cyan)]
    width = max(int(np.ceil(ink.textlength(s, font=font))) for s in labels + [s for s, _ in legend]) + 24
    row_height = max(20, font.getbbox("Ag")[3] + 5)
    margin = 10
    panel = Image.new("RGB", (photo.width + width, max(photo.height, (len(labels) + 4) * row_height + 2 * margin)), "#171B22")
    # Draw onto the photo first so off-frame projections cannot spill into the legend.
    for i, p in enumerate(rows, 1):
        for xy, marker, colour in ((p["baselineProjectedPx"], "square", orange), (p["projectedPx"], "circle", cyan),
                                    (p["photoPx"], "cross", yellow)):
            if xy is None or not (0 <= xy[0] < photo.width and 0 <= xy[1] < photo.height):
                continue
            x, y = (int(np.floor(n + .5)) for n in xy)
            if marker == "square":
                ink.rectangle((x - 6, y - 6, x + 6, y + 6), outline=colour, width=2)
            elif marker == "circle":
                ink.ellipse((x - 4, y - 4, x + 4, y + 4), outline=colour, width=2)
            else:
                ink.line((x - 2, y, x + 2, y), fill=colour)
                ink.line((x, y - 2, x, y + 2), fill=colour)
                ink.text((x + 7, y + 2), str(i), font=font, fill=colour, stroke_width=1, stroke_fill="black")
    panel.paste(photo)
    ink = ImageDraw.Draw(panel)
    for i, (label, colour) in enumerate(legend):
        ink.text((photo.width + margin, margin + i * row_height), label, font=font, fill=colour)
    for i, label in enumerate(labels, 4):
        ink.text((photo.width + margin, margin + i * row_height), label, font=font, fill="white")
    panel.save(output_path, format="PNG")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("anchors", type=Path, help="UTF-8 JSON. See the reference-interiors guide.")
    parser.add_argument("--evaluate-only", action="store_true", help="Report errors at the supplied pose")
    parser.add_argument("--baseline-camera", type=Path, help="Saved camera for comparison. Defaults to camera in anchors.")
    parser.add_argument("--candidate-camera", type=Path, help="Evaluate this saved camera without fitting.")
    parser.add_argument("--photo", type=Path, help="Original photograph, with the exact imageSize and framing of the anchors")
    parser.add_argument("--overlay", type=Path, help="Write annotated photo and point legend to a separate PNG")
    args = parser.parse_args()
    if bool(args.overlay) != bool(args.photo):
        parser.error("--photo and --overlay must be supplied together")
    try:
        data = json.loads(args.anchors.read_text(encoding="utf-8-sig"))
        output = analyze(data, args.evaluate_only, baseline_camera=camera_from_file(args.baseline_camera),
                         candidate_camera=camera_from_file(args.candidate_camera))
        if args.overlay:
            for source in (args.anchors, args.baseline_camera, args.candidate_camera):
                if source and args.overlay.exists() and args.overlay.samefile(source):
                    raise ValueError("The overlay would overwrite an input file")
            save_overlay(output, args.photo, args.overlay)
    except (OSError, KeyError, TypeError, ValueError, np.linalg.LinAlgError) as error:
        parser.exit(2, f"{parser.prog}: {error}\n")
    print(json.dumps(output, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
