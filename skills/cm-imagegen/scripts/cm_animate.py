#!/usr/bin/env python3
"""Compose periodic PNG layers into a GIF locally; never calls an image API."""

import argparse
import contextlib
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
except ImportError as exc:
    raise SystemExit("Local animation needs Pillow and NumPy: pip install Pillow numpy") from exc


TAU = math.tau


def fields(value, allowed, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError(f"Unknown {label} fields: {', '.join(sorted(unknown))}")


def number(value, low, high, label, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if not low <= value <= high or (integer and int(value) != value):
        raise ValueError(f"{label} must be {'an integer ' if integer else ''}in {low}..{high}")
    return int(value) if integer else float(value)


def pair(value, low, high, label, integer=False):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must be [x, y]")
    return tuple(number(v, low, high, label, integer) for v in value)


def motion(value, limit, label):
    fields(value, ("amplitude", "cycles", "phase"), label)
    return (
        number(value.get("amplitude", 0), -limit, limit, f"{label}.amplitude"),
        number(value.get("cycles", 1), 1, 20, f"{label}.cycles", True),
        number(value.get("phase", 0), -TAU, TAU, f"{label}.phase"),
    )


def oscillate(spec, phase):
    amplitude, cycles, offset = spec
    return amplitude * math.sin(cycles * phase + offset)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Scene:
    def __init__(self, config, root):
        fields(config, ("background", "size", "frame_count", "frame_duration_ms", "supersample", "water", "layers"), "scene")
        self.size = pair(config.get("size", [960, 640]), 16, 2048, "size", True)
        self.count = number(config.get("frame_count", 100), 2, 600, "frame_count", True)
        self.delay = number(config.get("frame_duration_ms", 60), 20, 2000, "frame_duration_ms", True)
        if self.delay % 10:
            raise ValueError("GIF frame_duration_ms must be a multiple of 10")
        if self.count * self.delay > 120000:
            raise ValueError("Local loop duration must be at most 120 seconds")
        self.scale = number(config.get("supersample", 3), 1, 3, "supersample", True)
        self.sources = []
        bg = self.load_image(config.get("background"), root)
        if bg.convert("RGBA").getchannel("A").getextrema()[0] < 255:
            raise ValueError("Background must be opaque; flatten it explicitly before composing")
        # Cover preserves aspect ratio; the scene coordinates use the output canvas.
        self.background = ImageOps.fit(bg.convert("RGB"), self.size, Image.Resampling.LANCZOS)
        self.bg_array = np.asarray(self.background, dtype=np.float32)
        self.yy, self.xx = np.mgrid[:self.size[1], :self.size[0]].astype(np.float32)
        self.rows = np.arange(self.size[1])[:, None]
        self.water = None
        if "water" in config:
            water = config["water"]
            fields(water, ("top", "amplitude_px"), "water")
            top = number(water.get("top", self.size[1] / 2), 0, self.size[1] - 1, "water.top")
            amplitude = number(water.get("amplitude_px", 1.2), 0, 12, "water.amplitude_px")
            weight = np.clip((self.yy - top) / (self.size[1] - top), 0, 1) ** .7
            self.water = (weight, amplitude)
        layers = config.get("layers")
        if not isinstance(layers, list) or not 1 <= len(layers) <= 8:
            raise ValueError("layers must contain 1..8 foreground layers")
        self.layers = [self.prepare_layer(layer, root) for layer in layers]

    def load_image(self, name, root):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("background/image must name a local image file")
        path = (Path(root) / name).resolve()
        with Image.open(path) as opened:
            if getattr(opened, "n_frames", 1) != 1:
                raise ValueError("Use still image inputs, not an existing animation")
            image = ImageOps.exif_transpose(opened).copy()
        self.sources.append({"file": path.name, "sha256": sha256(path), "size": list(image.size)})
        return image

    def prepare_layer(self, config, root):
        fields(config, ("image", "width", "position", "anchor", "rotation", "x", "y", "reflection", "shadow", "ripples"), "layer")
        image = self.load_image(config.get("image"), root).convert("RGBA")
        alpha = image.getchannel("A")
        bounds = alpha.point(lambda a: 255 if a > 24 else 0).getbbox()
        if bounds is None or alpha.getextrema()[0] == 255:
            raise ValueError("Foreground needs visible pixels and real transparency; no automatic background removal")
        image = image.crop(bounds)
        width = number(config.get("width", image.width), 1, 2048, "layer.width", True)
        height = max(1, round(width * image.height / image.width))
        if height > 2048:
            raise ValueError("Resized foreground height exceeds 2048")
        position = pair(config.get("position", [self.size[0] / 2, self.size[1] / 2]), -4096, 4096, "layer.position")
        anchor = pair(config.get("anchor", [.5, 1]), 0, 1, "layer.anchor")
        rotation = motion(config.get("rotation", {}), 30, "rotation")
        x = motion(config.get("x", {}), 2048, "x")
        y = motion(config.get("y", {}), 2048, "y")
        for effect in ("reflection", "shadow", "ripples"):
            if not isinstance(config.get(effect, False), bool):
                raise ValueError(f"layer.{effect} must be true or false")
        pad = math.ceil(2 * math.hypot(width, height) * math.sin(math.radians(abs(rotation[0])) / 2)) + 4
        plate = Image.new("RGBA", ((width + 2 * pad) * self.scale, (height + 2 * pad) * self.scale))
        plate.alpha_composite(image.resize((width * self.scale, height * self.scale), Image.Resampling.LANCZOS), (pad * self.scale, pad * self.scale))
        return dict(plate=plate, width=width, height=height, pivot=(pad + width * anchor[0], pad + height * anchor[1]),
                    position=position, rotation=rotation, x=x, y=y,
                    reflection=config.get("reflection", False), shadow=config.get("shadow", False), ripples=config.get("ripples", False))

    def water_frame(self, phase):
        if self.water is None:
            return self.background.convert("RGBA")
        weight, amplitude = self.water
        dx = weight * amplitude * (.68 * np.sin(self.yy * .145 + 2 * phase) + .32 * np.sin(self.yy * .062 + self.xx * .008 - phase))
        sample = np.clip(self.xx + dx, 0, self.size[0] - 1.001)
        left = sample.astype(np.int32)
        mix = (sample - left)[..., None]
        warped = self.bg_array[self.rows, left] * (1 - mix) + self.bg_array[self.rows, left + 1] * mix
        return Image.fromarray(np.uint8(np.clip(warped, 0, 255))).convert("RGBA")

    def frame(self, phase):
        # Integer-cycle oscillations and no duplicate endpoint give an exact period.
        phase %= TAU
        frame = self.water_frame(phase)
        for layer in self.layers:
            cx = layer["position"][0] + oscillate(layer["x"], phase)
            cy = layer["position"][1] + oscillate(layer["y"], phase)
            pivot = layer["pivot"]
            origin = (cx - pivot[0], cy - pivot[1])
            px, py = (math.floor(v) for v in origin)
            plate = layer["plate"].rotate(oscillate(layer["rotation"], phase), Image.Resampling.BICUBIC,
                                           center=(pivot[0] * self.scale, pivot[1] * self.scale))
            plate = plate.transform(plate.size, Image.Transform.AFFINE,
                                    (1, 0, -(origin[0] - px) * self.scale, 0, 1, -(origin[1] - py) * self.scale),
                                    Image.Resampling.BICUBIC)
            plate = plate.resize((plate.width // self.scale, plate.height // self.scale), Image.Resampling.LANCZOS)
            width = layer["width"]
            if layer["shadow"]:
                shadow = Image.new("RGBA", self.size)
                ImageDraw.Draw(shadow).ellipse((cx - width * .41, cy - 8, cx + width * .41, cy + 9), fill=(23, 63, 56, 75))
                frame.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(5)))
            if layer["reflection"]:
                source = plate.crop((0, 0, plate.width, max(1, round(pivot[1]))))
                reflection = ImageOps.flip(source).resize((source.width, max(1, round(source.height * .64))), Image.Resampling.BICUBIC)
                ref = np.array(reflection.filter(ImageFilter.GaussianBlur(.55)), dtype=np.float32)
                ry, rx = np.mgrid[:ref.shape[0], :ref.shape[1]]
                wave = (2.8 * np.sin(ry * .36 + 2 * phase) + 1.5 * np.sin(ry * .78 - phase)).astype(np.int32)
                ref = ref[ry, np.clip(rx + wave, 0, ref.shape[1] - 1)]
                ref[..., 3] *= .26 * np.exp(-ry / (ref.shape[0] * .47)) * (.825 + .175 * np.sin(ry * 1.23 + 2 * phase))
                frame.alpha_composite(Image.fromarray(np.uint8(ref)), (px, round(cy - 1)))
            if layer["ripples"]:
                ripple = Image.new("RGBA", (self.size[0] * self.scale, self.size[1] * self.scale))
                draw = ImageDraw.Draw(ripple)
                for k in range(4):
                    cycle = (phase / TAU + k / 4) % 1
                    rx = width * (.38 + cycle * .15)
                    ry = 7 + cycle * 16
                    opacity = round(28 * math.sin(math.pi * cycle) ** 2)
                    box = ((cx - rx) * self.scale, (cy - ry) * self.scale, (cx + rx) * self.scale, (cy + ry) * self.scale)
                    draw.arc(box, 3, 177, fill=(221, 226, 185, opacity), width=2)
                    draw.arc(box, 185, 355, fill=(27, 98, 91, round(opacity * .6)), width=2)
                frame.alpha_composite(ripple.resize(self.size, Image.Resampling.LANCZOS))
            frame.alpha_composite(plate, (px, py))
        return frame.convert("RGB")


def palette_for(scene):
    samples = []
    for index in range(8):
        im = scene.frame(TAU * index / 8)
        im.thumbnail((512, 512), Image.Resampling.LANCZOS)
        samples.append(im)
    sheet = Image.new("RGB", (samples[0].width, samples[0].height * len(samples)))
    for index, im in enumerate(samples):
        sheet.paste(im, (0, index * im.height))
    return sheet.quantize(colors=256, method=Image.Quantize.MEDIANCUT)


def inspect_gif(path):
    durations, hashes = [], set()
    with Image.open(path) as gif:
        if gif.format != "GIF":
            raise ValueError("Encoder did not produce a GIF")
        size, loop, count = gif.size, gif.info.get("loop"), gif.n_frames
        for index in range(count):
            gif.seek(index)
            durations.append(gif.info.get("duration", 0))
            hashes.add(hashlib.sha256(gif.convert("RGB").tobytes()).digest())
    return dict(size=list(size), frames=count, distinct_frames=len(hashes), duration_ms=sum(durations),
                frame_delays_ms=sorted(set(durations)), loop=loop, bytes=Path(path).stat().st_size)


def compose(scene, output, encoder="auto", ffmpeg="ffmpeg", preview=None):
    output = Path(output).resolve()
    if output.suffix.lower() != ".gif":
        raise ValueError("Output filename must end in .gif")
    if preview:
        preview = Path(preview).resolve()
        if preview == output or preview.suffix.lower() != ".png":
            raise ValueError("Preview must be a separate .png path")
    binary = shutil.which(ffmpeg)
    if encoder == "auto":
        encoder = "ffmpeg" if binary else "pillow"
    if encoder == "ffmpeg" and not binary:
        raise ValueError("FFmpeg not found; install it, pass --ffmpeg, or use --encoder pillow")
    if encoder == "pillow" and scene.size[0] * scene.size[1] * scene.count > 64000000:
        raise ValueError("Pillow buffers frames; reduce canvas/frame count or install FFmpeg")
    output.parent.mkdir(parents=True, exist_ok=True)
    palette = palette_for(scene)
    first = np.asarray(scene.frame(0), dtype=np.int16)
    periodic_error = int(np.abs(first - np.asarray(scene.frame(TAU), dtype=np.int16)).max())
    differences, previous = [], first

    def frames():
        nonlocal previous
        for index in range(scene.count):
            frame = scene.frame(TAU * index / scene.count)
            array = np.asarray(frame, dtype=np.int16)
            if index:
                differences.append(float(np.abs(array - previous).mean()))
            previous = array
            yield frame
        differences.append(float(np.abs(previous - first).mean()))

    # Validate a temporary output before replacing any existing deliverable.
    with tempfile.TemporaryDirectory(prefix=".cm-animate-", dir=output.parent) as temp:
        temp = Path(temp)
        target = temp / "animation.gif"
        if encoder == "ffmpeg":
            palette_path = temp / "palette.png"
            colors = np.asarray(palette.getpalette()[:768], dtype=np.uint8).reshape(16, 16, 3)
            Image.fromarray(colors).save(palette_path)
            rate = Fraction(1000, scene.delay)
            command = [binary, "-v", "error", "-y", "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size",
                       f"{scene.size[0]}x{scene.size[1]}", "-framerate", str(rate), "-i", "pipe:0", "-i", str(palette_path),
                       "-filter_complex", "[0:v][1:v]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle", "-loop", "0", str(target)]
            with tempfile.TemporaryFile() as errors:
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=errors)
                try:
                    for frame in frames():
                        process.stdin.write(frame.tobytes())
                    process.stdin.close()
                    if process.wait(timeout=120):
                        raise RuntimeError("FFmpeg exited with an error")
                except BaseException as exc:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    with contextlib.suppress(BrokenPipeError):
                        process.stdin.close()
                    errors.seek(0)
                    detail = errors.read(2000).decode("utf-8", "replace")
                    raise RuntimeError(f"GIF encoding failed: {detail or str(exc)}") from exc
        else:
            quantized = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames()]
            quantized[0].save(target, save_all=True, append_images=quantized[1:], duration=scene.delay, loop=0, optimize=False, disposal=1)
        stats = inspect_gif(target)
        if stats["distinct_frames"] < 2:
            raise ValueError("Output has no visible animation; increase motion or check layer placement")
        if stats["duration_ms"] != scene.count * scene.delay or stats["loop"] != 0 or stats["size"] != list(scene.size):
            raise ValueError(f"Encoded GIF timing/loop/size mismatch: {stats}")
        target.replace(output)
    if preview:
        preview.parent.mkdir(parents=True, exist_ok=True)
        scene.frame(0).save(preview)
    median = float(np.median(differences))
    warnings = []
    if differences[-1] > max(median * 4, .5):
        warnings.append("Loop seam difference is large relative to typical motion; inspect playback")
    result = dict(ok=True, animation_method="local_layer_composite", native_gif_request=False, network_call_performed=False,
                  encoder=encoder, paths=[str(output)], rendered_frames=scene.count, requested_frame_duration_ms=scene.delay,
                  media=stats, period_pixel_error_max=periodic_error, seam_mean_difference=differences[-1],
                  median_adjacent_difference=median, warnings=warnings, sources=scene.sources, output_sha256=sha256(output))
    sidecar = output.with_suffix(output.suffix + ".cm.json")
    # Keep provenance portable: filenames and hashes, without provider details.
    sidecar.write_text(json.dumps({k: v for k, v in result.items() if k != "paths"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["sidecars"] = [str(sidecar)]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", required=True, help="Scene JSON; image paths are relative to this file")
    parser.add_argument("--out", required=True, help="Destination .gif")
    parser.add_argument("--encoder", choices=("auto", "ffmpeg", "pillow"), default="auto")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg executable name or path")
    parser.add_argument("--preview", help="Optional first-frame .png")
    args = parser.parse_args(argv)
    try:
        path = Path(args.scene).resolve()
        scene = Scene(json.loads(path.read_text(encoding="utf-8-sig")), path.parent)
        result = compose(scene, args.out, args.encoder, args.ffmpeg, args.preview)
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"ok": False, "animation_method": "local_layer_composite", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
